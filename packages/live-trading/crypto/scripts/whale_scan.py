import logging
#!/usr/bin/env python3
"""Whale scanner — 3 lapis, semua gratis & tanpa API key.

KENAPA DIBUAT
-------------
Versi lama pakai `?startTime&endTime&limit=1000` per window 1 jam. Binance
mengembalikan 1000 trade PERTAMA dalam window itu, jadi klaim "4 jam terakhir"
sebenarnya hanya menutupi ~0.7 menit (BTC) s/d 3 menit (SOL) per jam alias
~1-5% tape. Angkanya terlihat meyakinkan padahal sampelnya sempit dan bias ke
awal jam.

TIGA LAPIS
----------
1. FLOW (klines 5m x48)  -> 1 request, coverage 100%, NET taker buy vs sell.
   Ini arah yang TIDAK bias. Dipakai sebagai dasar penilaian flow.
2. PRINT (aggTrades fromId mundur) -> cari order individual >= $100k beserta
   LEVEL harganya. Budget terbatas, jadi coverage DILAPORKAN apa adanya.
3. CROSS-CHECK (COIN-M / dapi) -> order book & populasi trader berbeda.
   Coverage per request jauh lebih murah (BTC: 1000 trade = ~6.5 menit vs
   0.64 menit di USDT-perp), jadi konfirmasi venue kedua jadi praktis.

CATATAN TEKNIS
--------------
- Notional COIN-M WAJIB dikoreksi: dapi qty dalam contract, bukan koin.
  notional = qty x contractSize (BTCUSD_PERP=100, ETHUSD_PERP=10, dst).
  Tanpa koreksi, angka whale bisa membengkak ~100x (px*qty).
- Rate limit: aggTrades limit=1000 = weight 20; plafon Binance 2400/menit
  (pool fapi+dapi dibagi per IP). Budget default 140 request (~50s) aman.
- 429 / error apa pun -> scan berhenti rapi, bukan diam-diam mengembalikan 0.
"""
import json
import subprocess
import time

WHALE_NOTIONAL_USD = 100_000.0
PAGE = 1000
WINDOW_HOURS = 4.0
MAX_REQ_PER_PAIR = 22
MAX_REQ_TOTAL = 140
SLEEP_BETWEEN = 0.12

FAPI = "https://fapi.binance.com"
DAPI = "https://dapi.binance.com"

_csize_cache = {}


class Budget:
    """Budget request bersama antar-pair supaya tidak kena 429."""

    def __init__(self, total=MAX_REQ_TOTAL):
        self.total = total
        self.used = 0
        self.exhausted = False

    def take(self, n=1):
        if self.used + n > self.total:
            self.exhausted = True
            return False
        self.used += n
        return True

    def remaining(self):
        return max(0, self.total - self.used)


def _curl_json(url, timeout=20, retries=2):
    for attempt in range(retries + 1):
        try:
            r = subprocess.run(["curl", "-s", "-m", str(timeout), url],
                               capture_output=True, text=True, timeout=timeout + 8)
            if r.stdout:
                return json.loads(r.stdout)
        except Exception:
            logging.getLogger(__name__).debug("operasi dilewati", exc_info=True)
        if attempt < retries:
            time.sleep(0.4)
    return None


# ------------------------------------------------------------------ lapis 1
def fetch_flow(symbol, interval="5m", limit=48):
    """NET taker flow dari klines — coverage ~100% dalam 1 request.

    Field kline Binance: [openTime,o,h,l,c,volume,closeTime,quoteVolume,
    count,takerBuyBaseVol,takerBuyQuoteVol,ignore]
    taker BUY  = agresor beli (market buy)
    taker SELL = total - taker buy
    """
    d = _curl_json(f"{FAPI}/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}")
    if not isinstance(d, list) or not d:
        return None
    try:
        quote = sum(float(c[7]) for c in d)
        tb = sum(float(c[10]) for c in d)
        tr = sum(int(c[8]) for c in d)
        first_t = int(d[0][0])
        last_t = int(d[-1][6])
    except (IndexError, TypeError, ValueError):
        return None
    sell = quote - tb
    return {
        "buy_usd": tb, "sell_usd": sell, "total_usd": quote,
        "net_usd": tb - sell, "ratio": (tb / sell) if sell else None,
        "side": "BUY" if tb > sell else ("SELL" if sell > tb else "mixed"),
        "trades": tr, "hours": round((last_t - first_t) / 3600_000, 1),
        "from": first_t, "to": last_t,
    }


# ------------------------------------------------------------------ lapis 2/3
def contract_size(symbol):
    if symbol in _csize_cache:
        return _csize_cache[symbol]
    d = _curl_json(f"{DAPI}/dapi/v1/exchangeInfo", timeout=25)
    if isinstance(d, dict):
        for s in d.get("symbols", []):
            try:
                _csize_cache[s["symbol"]] = float(s.get("contractSize") or 100)
            except (TypeError, ValueError):
                _csize_cache[s["symbol"]] = 100.0
    return _csize_cache.get(symbol, 100.0)


def coinm_symbol(usdt_symbol):
    """BTCUSDT -> BTCUSD_PERP bila tersedia di COIN-M."""
    if not usdt_symbol.endswith("USDT"):
        return None
    if not _csize_cache:
        contract_size("BTCUSD_PERP")
    cand = f"{usdt_symbol[:-4]}USD_PERP"
    return cand if cand in _csize_cache else None


def scan_tape(host, symbol, budget, window_hours=WINDOW_HOURS,
              max_req=MAX_REQ_PER_PAIR, coin_margined=False):
    """Paginasi MUNDUR via fromId sampai window tercakup atau budget habis."""
    out = {"n_prints": 0, "net_side": "n/a", "top": None, "buy_usd": 0.0,
           "sell_usd": 0.0, "coverage_min": 0.0, "coverage_pct": 0.0,
           "complete": False, "requests": 0, "trades": 0, "ok": False,
           "partial": False}
    csz = contract_size(symbol) if coin_margined else None
    base = f"{host}/{'dapi' if coin_margined else 'fapi'}/v1/aggTrades"

    if not budget.take():
        return out
    head = _curl_json(f"{base}?symbol={symbol}&limit=1")
    out["requests"] += 1
    if not isinstance(head, list) or not head:
        return out
    try:
        cur = int(head[-1]["a"])
        newest_t = int(head[-1]["T"])
    except (KeyError, TypeError, ValueError):
        return out

    oldest_t = newest_t
    target_ms = window_hours * 3600_000
    prints = []
    n_gen = 0
    while n_gen < max_req:
        if not budget.take():
            out["partial"] = True
            break
        d = _curl_json(f"{base}?symbol={symbol}&fromId={max(cur - PAGE, 0)}&limit={PAGE}")
        out["requests"] += 1
        n_gen += 1
        if not isinstance(d, list) or not d:
            break
        for t in d:
            try:
                px, qty = float(t["p"]), float(t["q"])
                notional = qty * csz if coin_margined else px * qty
            except (KeyError, TypeError, ValueError):
                continue
            if notional >= WHALE_NOTIONAL_USD:
                prints.append((notional, "SELL" if t.get("m") else "BUY", px))
        out["trades"] += len(d)
        try:
            oldest_t = int(d[0]["T"])
            cur = int(d[0]["a"])
        except (KeyError, TypeError, ValueError):
            break
        if newest_t - oldest_t >= target_ms:
            break
        time.sleep(SLEEP_BETWEEN)

    cover = (newest_t - oldest_t) / 60000.0
    out["coverage_min"] = round(cover, 1)
    out["coverage_pct"] = round(100 * cover / (window_hours * 60), 1)
    out["complete"] = cover >= window_hours * 60 * 0.97
    out["ok"] = True
    out["n_prints"] = len(prints)
    buys = sum(p[0] for p in prints if p[1] == "BUY")
    sells = sum(p[0] for p in prints if p[1] == "SELL")
    out["buy_usd"], out["sell_usd"] = buys, sells
    out["net_side"] = "BUY-side" if buys > sells else ("SELL-side" if sells > buys else "mixed")
    if prints:
        prints.sort(reverse=True)
        out["top"] = prints[0]
    return out


def whale_scan(usdt_symbol, budget, window_hours=WINDOW_HOURS, cross_check=True,
               quota=MAX_REQ_PER_PAIR):
    """Flow (100% coverage) + tape print + cross-check COIN-M dalam SATU kuota.

    quota = total request yang boleh dipakai pair ini (flow + tape + cross-check),
    supaya satu pair tidak menghabiskan jatah pair lain. Pembagian internal:
    tape 60%, cross-check sisanya (di-skip kalau kurang dari 3 request).
    """
    quota = max(4, quota)
    flow = fetch_flow(usdt_symbol)
    budget.take()  # kline dihitung 1 request
    sisa = quota - 1
    tape_max = max(3, int(sisa * 0.6))
    cross_max = sisa - tape_max

    primary = scan_tape(FAPI, usdt_symbol, budget, window_hours=window_hours,
                        max_req=tape_max)
    cross = None
    if cross_check and cross_max >= 3:
        cm = coinm_symbol(usdt_symbol)
        if cm:
            cross = scan_tape(DAPI, cm, budget, window_hours=window_hours,
                              max_req=min(cross_max, budget.remaining()),
                              coin_margined=True)
    return {"flow": flow, "primary": primary, "cross": cross}


def format_block(res, indent="  "):
    """Format multi-baris yang jujur soal coverage dan limitasi."""
    out = []
    flow = res.get("flow")
    p = res.get("primary") or {}
    c = res.get("cross")

    if flow:
        out.append(f"{indent}flow 4j (klines, coverage 100%): net {flow['side']}-side, "
                   f"buy ${flow['buy_usd']/1e6:,.0f}M vs sell ${flow['sell_usd']/1e6:,.0f}M "
                   f"(rasio {flow['ratio']:.2f})" if flow.get("ratio") is not None
                   else f"{indent}flow: n/a")

    if not p.get("ok"):
        out.append(f"{indent}print >$100k: GAGAL ambil tape (budget habis / network)")
    else:
        if p["n_prints"]:
            head = (f"{p['n_prints']} print >$100k, net {p['net_side']}, "
                    f"top ${p['top'][0]/1000:,.0f}k {p['top'][1]} @ {p['top'][2]:.6g}")
        else:
            head = "tidak ada print >$100k"
        if p["complete"]:
            cov = f"coverage penuh {WINDOW_HOURS:.0f}j"
        else:
            cov = f"coverage {p['coverage_pct']:.0f}% dr {WINDOW_HOURS:.0f}j (budget {p['requests']} req)"
        out.append(f"{indent}print USDT-perp: {head} [{cov}]")

    if c and c.get("ok"):
        if c["n_prints"]:
            cc = (f"COIN-M {c['n_prints']} print net {c['net_side']} "
                  f"[coverage {c['coverage_pct']:.0f}%]")
        else:
            cc = f"COIN-M tidak ada print >$100k [coverage {c['coverage_pct']:.0f}%]"
        if p.get("n_prints") and c["n_prints"]:
            cc += " — SEPAKAT ✓" if p["net_side"] == c["net_side"] else " — BEDA arah ⚠"
        out.append(f"{indent}{cc}")
    return "\n".join(out)


if __name__ == "__main__":
    import sys
    syms = sys.argv[1:] or ["BTCUSDT", "SOLUSDT"]
    b = Budget()
    for s in syms:
        res = whale_scan(s, b)
        print(f"\n{s}:")
        print(format_block(res))
    print(f"\nBudget: {b.used}/{b.total} request")
