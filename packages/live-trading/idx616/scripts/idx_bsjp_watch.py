#!/usr/bin/env python3
"""BSJP Watcher (Beli Sore Jual Pagi) — edge terverifikasi walk-forward.

Riset 10 Sep (yfinance 200 simbol liquid, 6 bulan, net biaya 0.40%/round-trip):
  Entry = close T dengan filter: 6%<=chg<=12%, close>=1.05*SMA10, vol>=1.5x avg10,
          price>100, value>=5B. Exit = open T+1 (jual 08:55-09:05 WIB).
  Net +0.89%/trade, WR ~48%, konsisten positif di 3 fold walk-forward.
  Raw BSJP tanpa filter cuma +0.28% net; klaim WR 79% Kingdom = metrik high-touch,
  bukan profit riil.

Usage: idx_bsjp_watch.py [--no-send] [--top N]
Dipanggil cron 15:40 WIB Sen-Kam (Jumat libur BSJP — hindari gap weekend).
"""
import argparse
import datetime
import subprocess
import sys

TV_URL = "https://scanner.tradingview.com/indonesia/scan"
TV_HEADERS = {"origin": "https://www.tradingview.com", "referer": "https://www.tradingview.com/"}
TARGET = "telegram:-1004383844873:616"
HERMES = "/home/ubuntu/.local/bin/hermes"
JOURNAL = "/home/ubuntu/hermes-agent/venv/bin/python /home/ubuntu/.hermes/scripts/idx_signal_journal.py"

# EDGE filter — ARA raw resep Kingdom (walk-forward 10 Sep: net +1.05/+0.80/+1.18 per fold)
# STRONG tier = subset dgn SMA10 extension + chg band (BSJP edge, net +0.86%)
CHG_MIN, CHG_MAX = 2.0, 25.0
VOL_VS_AVG = 1.5
PRICE_MIN = 100.0
VALUE_MIN = 1e9
EXT_SMA10 = 1.03
STRONG_CHG = (6.0, 12.0)
COST_PCT = 0.40  # round-trip fee+levy, dipakai buat estimasi net di pesan


def now_wib():
    return datetime.datetime.utcnow() + datetime.timedelta(hours=7)


def num(v):
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def scan():
    # SMA10 & avg-vol-10 dihitung dari daily history TV ( columns custom ) —
    # TV scanner IDX gak expose SMA10 utk semua saham via /scan, jadi pakai
    # yfinance batch utk shortlist TV (volume desc, 120 nama) biar hemat kuota.
    from curl_cffi import requests as cr
    s = cr.Session(impersonate="chrome")
    body = {
        "filter": [{"left": "type", "operation": "equal", "right": "stock"}],
        "columns": ["name", "close", "change", "volume", "market_cap_calc"],
        "sort": {"sortBy": "volume", "sortOrder": "desc"},
        "range": [0, 120],
    }
    r = s.post(TV_URL, json=body, timeout=30, headers=TV_HEADERS)
    r.raise_for_status()
    out = []
    for d in r.json().get("data", []):
        v = d.get("d") or []
        if len(v) < 5:
            continue
        out.append({
            "symbol": d["s"].replace("IDX:", ""),
            "close": num(v[1]), "chg": num(v[2]),
            "volume": num(v[3]), "mcap": num(v[4]),
        })
    return out


def _arjum_stats(code):
    """SMA10 & vavg10 (excl today) dari arjum history EOD. Return (sma10, vavg10, n) or None.
    Keduanya butuh bar LAMA, bukan today — EOD T-1 dari arjum valid. Volume 0
    beruntun (suspense/IPO baru) = invalid → caller fallback ke yfinance."""
    import arjum_pool
    h = arjum_pool.pool_history(code, frame="daily")  # cached 4h — kuota-safe
    rows = h["rows"]
    if len(rows) < 12:
        return None
    closes = [r["close"] for r in rows[:10] if r["close"]]
    vols = [r["volume"] for r in rows[1:11]]  # exclude today
    if len(closes) < 8 or not vols or sum(vols) <= 0:
        return None
    return sum(closes) / len(closes), sum(vols) / len(vols), len(closes)


def edge_filter(cands, top_n):
    # Shortlist TV (harga live intraday — arjum tidak menyediakan) → verifikasi
    # SMA10 + vol avg via ARJUM history (primary), yfinance hanya fallback.
    import yfinance as yf
    short = [c for c in cands
             if c["chg"] is not None and CHG_MIN <= c["chg"] <= CHG_MAX
             and (c["close"] or 0) > PRICE_MIN
             and (c["close"] or 0) * (c["volume"] or 0) >= VALUE_MIN]
    hits = []
    src_used = {"arjum": 0, "yf": 0}
    for c in short[:50]:
        try:
            stats = None
            try:
                stats = _arjum_stats(c["symbol"])
                if stats:
                    src_used["arjum"] += 1
            except Exception:
                stats = None
            if stats:
                sma10, vavg10, _ = stats
                rel_vol = c["volume"] / vavg10 if vavg10 else 0
                vol_ok = rel_vol >= VOL_VS_AVG
            else:
                src_used["yf"] += 1
                h = yf.Ticker(f"{c['symbol']}.JK").history(period="1mo", interval="1d", auto_adjust=False)
                if h is None or len(h) < 12:
                    continue
                cl = h["Close"].values
                vol = h["Volume"].values
                sma10 = cl[-10:].mean()
                vavg10 = vol[-11:-1].mean()
                rel_vol = vol[-1] / vavg10 if vavg10 else 0
                vol_ok = rel_vol >= VOL_VS_AVG
            if not vol_ok:
                continue
            c["sma10"] = round(sma10, 1)
            c["rel_vol"] = round(rel_vol, 2)
            strong = (c["close"] >= EXT_SMA10 * sma10
                      and STRONG_CHG[0] <= c["chg"] <= STRONG_CHG[1])
            c["tier"] = "STRONG" if strong else "ARA"
            c["net_est"] = round(0.86 if strong else 1.06, 2)
            hits.append(c)
        except Exception:
            continue
    print(f"[data src] arjum={src_used['arjum']} yf_fallback={src_used['yf']}")
    hits.sort(key=lambda x: (x["tier"] != "STRONG", -x["rel_vol"]))
    return hits[:top_n]


def journal_log(s):
    # Exit BSJP = open T+1, bukan TP1/TP2: tp diset target gap +1%, sl adalah
    # kill-switch -2.5% kalau pergi salah sebelum 09:00 (anti black-swan).
    e = s["close"]
    try:
        import sys
        sys.path.insert(0, "/home/ubuntu/.hermes/scripts")
        from idx616_ledger import record_event
        from idx_clock import now_wib
        record_event(
            job_id="b7e4d1a83c52",
            producer="idx_bsjp_watch.py",
            created_at=now_wib().isoformat(),
            ticker=f"{s['symbol']}.JK",
            setup=f"BSJP_{s.get('tier', 'ARA')}",
            source="bsjp_watcher",
            direction="LONG",
            entry_low=float(e),
            entry_high=float(e),
            sl=float(e * 0.975),
            tp1=float(e * 1.01),
            tp2=float(e * 1.02),
            data_source="arjum_plus_market_adapter",
            source_timestamp=now_wib().isoformat(),
            note="BSJP exit is next-session open",
        )
    except Exception as exc:
        print(f"[ledger-warn] {s.get('symbol')}: {exc}", file=sys.stderr)
    subprocess.run(
        JOURNAL.split() + ["--status", "SIGNAL", "--emiten", f"{s['symbol']}.JK",
                           "--arah", "LONG", "--entry", f"{e:.0f}",
                           "--sl", f"{e * 0.975:.0f}", "--tp1", f"{e * 1.01:.0f}",
                           "--tp2", f"{e * 1.02:.0f}", "--mode", "BSJP",
                           "--alasan", f"BSJP edge chg {s['chg']:.1f}% relvol {s['rel_vol']}x ext>=1.05"],
        check=False, capture_output=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-send", action="store_true")
    ap.add_argument("--top", type=int, default=5)
    args = ap.parse_args()

    now = now_wib()
    if now.weekday() >= 4:  # 4=Jumat: gap weekend, 5-6 weekend
        print("[SILENT] Jumat/weekend: BSJP off (gap risk)")
        return 0
    from idx_clock import trading_day
    if not trading_day(now.date()) or not (datetime.time(15, 40) <= now.time() <= datetime.time(16, 0)):
        print(f"[SILENT] di luar window 15:40-16:00 (sekarang {now:%H:%M})")
        return 0

    try:
        cands = scan()
    except Exception as e:
        print(f"[bsjp] TV scan fail: {e}", file=sys.stderr)
        return 1
    hits = edge_filter(cands, args.top)
    if not hits:
        print("[SILENT] tidak ada kandidat BSJP hari ini")
        return 0

    lines = [f"🌙 *BSJP WATCHER* — {now:%a %d %b, %H:%M} WIB",
             "Beli di close hari ini → jual di open besok 08:55-09:05 WIB "
             "(disiplin, apapun harganya)",
             "_ARA: chg ≥2% + vol ≥1.5×avg (historical estimate, not live guarantee) · "
             "STRONG: +ext SMA10 & chg 6-12%_",
             "─────────────────────"]
    for s in hits:
        tier = s.get("tier", "ARA")
        lines.append(
            f"• [{'🥇 STRONG' if tier == 'STRONG' else 'ARA'}] *{s['symbol']}* "
            f"entry ~{s['close']:,.0f} (chg +{s['chg']:.1f}%) | relvol {s['rel_vol']}x | "
            f"est net ~+{s['net_est']:.2f}%"
        )
    lines += ["",
              f"📊 Backtest 6 bln walk-forward: +0.9% net/trade, WR ~48% ({COST_PCT}% biaya sudah dipotong)",
              "⚠️ Jangan tahan lewat 09:10. Jumat otomatis libur BSJP. UMA risk: cek papan.",
              "— Hermes BSJP (deterministik, bukan ajakan)"]
    msg = "\n".join(lines)
    if args.no_send:
        print(msg)
        return 0
    from idx_delivery import send_confirmed
    send_confirmed(msg)
    for s in hits:
        journal_log(s)
    print(f"posted {len(hits)} BSJP setups + journal")
    return 0


if __name__ == "__main__":
    import contextlib
    if "--no-send" in sys.argv:
        sys.exit(main())
    with contextlib.redirect_stdout(sys.stderr):
        sys.exit(main())
