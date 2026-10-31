import logging
#!/usr/bin/env python3
"""Crypto 5-agent pipeline collector — Agent 1 (scan), 4 (whale), 5 (risk).

Pure Python, no LLM. Reuses crypto_signal_collect fetchers/classifiers and adds:

  FASE 0: Order flow scan (reuse + L% real)
  FASE 1: SMC structure 1D/4H/1H (reuse)
  FASE 2: WHALE & POSITIONING (Agent 4 data) — taker buy/sell ratio, OI delta
          24h, whale aggTrades prints (>$100k notional) for candidate pairs,
          funding extremes
  FASE 3: SENTIMENT (Agent 3 data) — Fear & Greed index (alternative.me free)
  FASE 4: RISK & EXPOSURE (Agent 5 data) — spread, ATR(14,1H) volatility,
          open-position count, BTC regime

The composing LLM (Agent 2 setups + Agent 3 news interpretation) turns this
digest into the Telegram post. All prices = Binance USDT perp (fapi).
"""
import contextlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta

from crypto_signal_collect import (
    WATCHLIST, _data, fetch_orderflow, fetch_klines, fresh_check,
    calc_buy_pressure, calc_vol_delta, classify_flow,
    ema, structure, make_tf_label, curl_retry,
)
from whale_scan import Budget, whale_scan, format_block

WIB = timezone(timedelta(hours=7))
WHALE_NOTIONAL_USD = 100_000.0


def atr(highs, lows, closes, period=14):
    """ATR as % of last price — volatility context for risk agent."""
    if len(closes) < period + 1:
        return None
    trs = []
    for i in range(-period, 0):
        trs.append(max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        ))
    return (sum(trs) / period) / closes[-1] * 100


def fetch_taker_ratio(symbol):
    """Aggressive taker buy/sell volume ratio (whale urgency proxy)."""
    d = curl_retry(
        f"https://fapi.binance.com/futures/data/takerlongshortRatio"
        f"?symbol={symbol}&period=1h&limit=2"
    )
    if isinstance(d, list) and d:
        try:
            return float(d[-1].get("buySellRatio", 0))
        except (TypeError, ValueError):
            pass
    return None


def fetch_oi_delta(symbol):
    """OI change % over last 24h from OI history."""
    d = curl_retry(
        f"https://fapi.binance.com/futures/data/openInterestHist"
        f"?symbol={symbol}&period=1h&limit=25"
    )
    if isinstance(d, list) and len(d) >= 20:
        try:
            first = float(d[0]["sumOpenInterest"])
            last = float(d[-1]["sumOpenInterest"])
            if first > 0:
                return (last - first) / first * 100
        except (TypeError, ValueError, KeyError):
            pass
    return None


def fetch_whale_trades(symbol):
    """DEPRECATED — jangan dipakai lagi.

    Versi ini pakai `?startTime&endTime&limit=1000` per window 1 jam, sementara
    Binance mengembalikan 1000 trade PERTAMA dalam window itu. Efeknya klaim
    "4 jam terakhir" cuma menutupi ~0.7 menit (BTC) s/d 3 menit (SOL) per jam
    (~1-5% tape) dan bias ke awal jam.

    Pengganti: `whale_scan.whale_scan()` — flow klines (coverage 100%) +
    paginasi fromId mundur (print besar) + cross-check COIN-M, dengan coverage
    yang dilaporkan apa adanya. Disimpan hanya supaya import lama tidak pecah.
    """
    raise NotImplementedError(
        "fetch_whale_trades() sudah deprecated — pakai whale_scan.whale_scan()"
    )


def _fetch_whale_trades_legacy(symbol):
    """Implementasi lama (arsip referensi, tidak dipanggil)."""
    now_ms = int(time.time() * 1000)
    window_ms = 3600_000  # 1h per request
    n_req = 4             # last 4 hours
    prints = []
    buys = sells = 0.0
    for i in range(n_req, 0, -1):
        start = now_ms - i * window_ms
        end = start + window_ms
        d = curl_retry(
            f"https://fapi.binance.com/fapi/v1/aggTrades?symbol={symbol}"
            f"&startTime={start}&endTime={end}&limit=1000"
        )
        if not isinstance(d, list) or not d:
            continue
        for t in d:
            try:
                px, qty = float(t["p"]), float(t["q"])
                notional = px * qty
                if notional >= WHALE_NOTIONAL_USD:
                    side = "SELL" if t.get("m") else "BUY"  # m=True → buyer is maker → aggressor sold
                    prints.append((notional, side, px))
                    if side == "BUY":
                        buys += notional
                    else:
                        sells += notional
            except (KeyError, TypeError, ValueError):
                continue
    if not prints:
        return 0, "n/a", None
    prints.sort(reverse=True)
    net = "BUY-side" if buys > sells else ("SELL-side" if sells > buys else "mixed")
    top = prints[0]
    return len(prints), net, top


def fetch_fear_greed():
    """Fear & Greed index (alternative.me, free, no key)."""
    try:
        out = subprocess.run(
            ["curl", "-s", "--max-time", "10", "https://api.alternative.me/fng/?limit=2"],
            capture_output=True, text=True, timeout=15,
        ).stdout
        d = json.loads(out)
        cur = d["data"][0]
        prev = d["data"][1] if len(d["data"]) > 1 else None
        return {
            "value": int(cur["value"]),
            "label": cur["value_classification"],
            "prev": int(prev["value"]) if prev else None,
        }
    except Exception:
        return None


def main():
    now = datetime.now(WIB).strftime("%d %b %Y, %H:%M WIB")
    lines = ["=== CRYPTO 5-AGENT PIPELINE DIGEST (BINANCE PERP) ===", f"Collected: {now}"]
    lines.append("Harga semua dari Binance USDT perp (fapi). Agent 1/4/5 = data di bawah; "
                 "Agent 2 (setups) + Agent 3 (news) = tugas LLM.")

    # ---------- AGENT 1: scan (order flow + SMC) ----------
    print("[A1] fetching order flow...", file=sys.stderr)
    for sym in WATCHLIST:
        fetch_orderflow(sym)

    lines.append("\n=== AGENT 1 — MARKET SCAN: ORDER FLOW ===")
    candidates = []
    for sym in WATCHLIST:
        bp = calc_buy_pressure(sym)
        vd = calc_vol_delta(sym)
        funding = _data["fundings"].get(sym, 0.0)
        oi = _data["ois"].get(sym, 0.0)
        top_ratio = None
        ls = curl_retry(
            f"https://fapi.binance.com/futures/data/topLongShortAccountRatio"
            f"?symbol={sym}&period=1h&limit=1"
        )
        if isinstance(ls, list) and ls:
            try:
                top_ratio = float(ls[-1].get("longShortRatio", 0))
            except (TypeError, ValueError):
                top_ratio = None
        long_pct = round(100 * top_ratio / (1 + top_ratio), 1) if top_ratio and top_ratio > 0 else 50.0

        flow = classify_flow(bp, vd, long_pct, funding=funding, use_fallback=True)
        if "Mild" in flow or "AGGRESSIVE" in flow or "Strong" in flow:
            candidates.append(sym)
        vd_str = f"{vd:+.1f}%" if vd is not None else "n/a"
        lines.append(
            f"  {sym:12s} | bp {bp:+5.1f}% | volΔ6h {vd_str:>7s} | fund {funding:+.4f}% "
            f"| L={long_pct:5.1f}% | {flow}"
        )

    # SMC structure
    print(f"[A1] SMC klines for {len(WATCHLIST)} pairs...", file=sys.stderr)
    lines.append("\n=== AGENT 1 — MARKET SCAN: SMC STRUCTURE ===")
    for sym in WATCHLIST:
        price_info = _data["prices"].get(sym) or {}
        price = price_info.get("price") or _data["of_last_price"].get(sym, 0)
        if not price:
            lines.append(f"--- {sym} | price n/a ---")
            continue
        chg = price_info.get("chg24h")
        chg_l = f" | 24h {chg:+.2f}%" if chg else ""
        lines.append(f"--- {sym} | ${price:,.6g}{chg_l} ---")
        tf_config = {"1d": (100, 48), "4h": (100, 8), "1h": (60, 2)}
        for interval, (limit, max_age) in tf_config.items():
            key = f"{sym}_{interval}"
            entry = _data["klines"].get(key)
            if interval == "1h" and entry is not None and len(entry["closes"]) >= 60:
                pass
            else:
                entry = fetch_klines(sym, interval, limit)
            label = {"1d": "1D", "4h": "4H", "1h": "1H"}[interval]
            if not entry or not fresh_check(key, max_age):
                lines.append(f"  [{label}] n/a")
                continue
            closes = entry["closes"][:]
            closes[-1] = price
            e50 = ema(closes[:-1], 50)
            pos = "above" if e50 and price > e50 else ("below" if e50 else "n/a")
            rng_hi, rng_lo = max(entry["highs"][-30:]), min(entry["lows"][-30:])
            if rng_hi == rng_lo:
                pd_, zone = 0.5, "equilibrium"
            else:
                pd_ = (price - rng_lo) / (rng_hi - rng_lo)
                zone = "premium" if pd_ > 0.6 else ("discount" if pd_ < 0.4 else "equilibrium")
            lines.append(f"  [{label}] {make_tf_label(structure(entry['highs'], entry['lows']), pos, zone, pd_, len(closes))}")

    # ---------- AGENT 4: whale & positioning ----------
    print(f"[A4] whale/positioning for candidates {candidates}...", file=sys.stderr)
    lines.append("\n=== AGENT 4 — WHALES & POSITIONING (kandidat + BTC) ===")
    if not candidates:
        lines.append("  (tidak ada pair Mild/Aggressive — whale scan skip, BTC-only)")
        whale_targets = ["BTCUSDT"]
    else:
        whale_targets = list(dict.fromkeys(candidates + ["BTCUSDT"]))[:8]

    # Budget request dibagi rata antar-target (rate limit Binance 2400 weight/menit,
    # aggTrades limit=1000 = 20 weight). Lewat budget -> scan berhenti rapi dan
    # coverage dilaporkan apa adanya, bukan diklaim penuh.
    wb = Budget()
    n_targets = max(len(whale_targets), 1)
    for idx, sym in enumerate(whale_targets):
        sisa_pair = n_targets - idx
        # alokasi dinamis: sisa budget dibagi sisa pair, minimal 6 request
        per_pair = max(6, wb.remaining() // sisa_pair)
        tk = fetch_taker_ratio(sym)
        oid = fetch_oi_delta(sym)
        funding = _data["fundings"].get(sym, 0.0)
        tk_s = f"{tk:.2f}" if tk is not None else "n/a"
        oid_s = f"{oid:+.1f}%" if oid is not None else "n/a"
        lines.append(f"  {sym} | taker B/S 1h {tk_s} | OIΔ24h {oid_s} | fund {funding:+.4f}%")
        try:
            res = whale_scan(sym, wb, cross_check=True, quota=per_pair)
            for ln in format_block(res, indent="    ").split("\n"):
                lines.append(ln)
        except Exception as exc:
            lines.append(f"    whale scan gagal: {type(exc).__name__}: {str(exc)[:90]}")
    lines.append(f"  (budget whale: {wb.used}/{wb.total} request untuk {n_targets} pair)")
    lines.append("  CARA BACA: 'flow' dari klines = arah NET taker 4 jam, coverage 100%, ini yang "
                 "paling tidak bias. 'print' dari tape aggTrades = order individual >$100k "
                 "beserta level harga, TAPI coverage terbatas (lihat persennya) — kalau coverage "
                 "<50%, jangan jadikan dasar tunggal; utamakan 'flow'. 'COIN-M' = cross-check di "
                 "order book berbeda (SEPAKAT = sinyal lebih kuat, BEDA arah = ragu).")
    lines.append("  Interpretasi: taker B/S >1.2 = agresi beli, <0.8 = agresi jual. "
                 "OI naik + harga naik = long buildup; OI naik + harga turun = short buildup.")

    # ---------- AGENT 3 data: sentiment ----------
    print("[A3] fear & greed...", file=sys.stderr)
    lines.append("\n=== AGENT 3 — SENTIMENT DATA ===")
    fg = fetch_fear_greed()
    if fg:
        trend = ""
        if fg["prev"] is not None:
            d = fg["value"] - fg["prev"]
            trend = f" (kemarin {fg['prev']}, {'naik' if d > 0 else 'turun'} {abs(d)})"
        lines.append(f"  Fear & Greed: {fg['value']}/100 — {fg['label']}{trend}")
    else:
        lines.append("  Fear & Greed: n/a (fetch gagal)")
    btcdom = None
    try:
        out = subprocess.run(
            ["curl", "-s", "--max-time", "8",
             "https://api.coingecko.com/api/v3/global"],
            capture_output=True, text=True, timeout=12,
        ).stdout
        g = json.loads(out)["data"]["market_cap_percentage"]
        btcdom = g.get("btc")
    except Exception:
        logging.getLogger(__name__).debug("operasi dilewati", exc_info=True)
    if btcdom:
        lines.append(f"  BTC dominance: {btcdom:.1f}% (alt season jika < 45 & turun)")
    lines.append("  Funding agregat: lihat kolom fund di AGENT 4 (positif ekstrem >0.05% = long crowded).")

    # ---------- AGENT 5: risk & exposure ----------
    print("[A5] risk metrics...", file=sys.stderr)
    lines.append("\n=== AGENT 5 — RISK & EXPOSURE ===")
    # open positions
    open_syms = []
    try:
        wl = json.load(open(os.path.expanduser("~/.hermes/crypto-watchlist.json")))
        open_syms = [it.get("pair") for it in (wl.get("items") or [])
                     if it.get("status") in ("still_open", "tp1_hit_runner")]
    except Exception:
        logging.getLogger(__name__).debug("operasi dilewati", exc_info=True)
    lines.append(f"  Posisi open user: {len(open_syms)}" + (f" ({', '.join(open_syms)})" if open_syms else " — clean"))
    # BTC regime
    btc = _data["prices"].get("BTCUSDT") or {}
    chg = btc.get("chg24h")
    if chg is not None:
        lines.append(f"  BTC 24h: {chg:+.2f}% — {'risk-on' if chg > 1 else ('risk-off' if chg < -1 else 'netral')}; alt berkorelasi BTC, hindari 2 posisi searah saat |chg|>3%")
    # ATR + spread for candidates
    if candidates:
        lines.append("  Volatilitas kandidat (ATR14 1H sebagai % harga) & spread:")
        for sym in candidates:
            entry = _data["klines"].get(f"{sym}_1h")
            a = None
            if entry and len(entry["closes"]) >= 15:
                a = atr(entry["highs"], entry["lows"], entry["closes"])
            ba = _data["of_bid_ask"].get(sym)
            sp = (ba[1] - ba[0]) / ba[0] * 100 if ba else None
            a_s = f"{a:.2f}%" if a is not None else "n/a"
            s_s = f"{sp:.3f}%" if sp is not None else "n/a"
            lines.append(f"    {sym:12s} ATR {a_s:>6s} | spread {s_s}")
        lines.append("  Rule of thumb: SL struktur 1H idealnya 0.5–2x ATR1H; TP2=2R realistis jika ATR ≥ jarak TP2/12 jam.")
    else:
        lines.append("  (tidak ada kandidat — metrik pair skip)")

    # ---------- AGENT 6: on-chain (DefiLlama) + positioning (Binance) ----------
    # Konfirmasi saja, BUKAN gate. Datalog ke state/onchain_enrich.jsonl untuk evaluasi edge.
    try:
        from onchain_enrich import build_section
        a6_symbols = candidates if candidates else ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
        lines.append(build_section(a6_symbols))
    except Exception as exc:  # jangan pernah menggagalkan pipeline karena enrichment
        lines.append("\n=== AGENT 6 — ON-CHAIN & POSITIONING (konfirmasi, BUKAN gate entry) ===")
        lines.append(f"  n/a (gagal: {type(exc).__name__})")

    # ---------- AGENT 6b: akumulasi whale wallet-level (Hyperliquid) ----------
    # Baca state saja (cron hl-whale-accum-653 yang refresh tiap 10 menit),
    # jadi tidak ada request tambahan di sini. Konfirmasi, BUKAN gate.
    try:
        from hl_whale_accum import run_brief
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            run_brief()
        out = buf.getvalue().strip()
        if out:
            lines.append("\n=== AGENT 6b — AKUMULASI WHALE WALLET-LEVEL (HYPERLIQUID, konfirmasi saja) ===")
            lines.append(out)
    except Exception:
        logging.getLogger(__name__).debug("operasi dilewati", exc_info=True)

    print("\n".join(lines))


if __name__ == "__main__":
    sys.exit(main())
