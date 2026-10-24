import logging
#!/usr/bin/env python3
"""Silent watchdog: hourly evaluation of crypto watchlist (topic 653).

no_agent cron job — reads ~/.hermes/crypto-watchlist.json, fetches current
Binance perp prices, checks TP1/TP2/SL touches for open items, updates the
JSON in place, prints alert lines ONLY when a level is hit (empty stdout =
silent, watchdog pattern). No LLM involved.

Override watchlist path via env CRYPTO_WATCHLIST_PATH (testing only).
"""
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta

WIB = timezone(timedelta(hours=7))
PATH = os.environ.get(
    "CRYPTO_WATCHLIST_PATH",
    os.path.expanduser("~/.hermes/crypto-watchlist.json"),
)


def fmt(price):
    if price is None:
        return "?"
    if price >= 1000:
        return f"{price:,.1f}"
    if price >= 1:
        return f"{price:.4f}".rstrip("0").rstrip(".")
    return f"{price:.6f}".rstrip("0").rstrip(".")


def fetch_price(symbol):
    try:
        out = subprocess.run(
            ["curl", "-s", "--max-time", "10",
             f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={symbol}"],
            capture_output=True, text=True, timeout=15,
        ).stdout
        return float(json.loads(out)["price"])
    except Exception:
        return None


def mid_entry(zone):
    try:
        lo, hi = [float(x) for x in str(zone).split("-")]
        return (lo + hi) / 2
    except Exception:
        return None


def num(v):
    try:
        return float(v) if v not in (None, "", "null") else None
    except (TypeError, ValueError):
        return None


EXECUTED = True   # set per-item di main(): False kalau sinyal di-skip (paper)


def manage_tp1(pair, be_level, tp2):
    """TP1 kena -> partial 50% + SL digeser ke BE. Aturan user 26 Sep (binding).

    Kalau lotnya nggak bisa dibelah (1 lot = ukuran terkecil di OKX), cukup
    set BE. APA PUN hasilnya harus dilaporkan — jangan diam kalau gagal, karena
    posisi tanpa proteksi itu masalah uang beneran.

    Return (ok, pesan).
    """
    if not EXECUTED:
        return True, ("PAPER TRADE (tanpa eksekusi OKX — signal di-skip atas "
                      "keputusan user). Tidak ada posisi untuk di-manage; hasil "
                      "TP/SL tetap dicatat di jurnal.")
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import okx_client as mx
        try:
            from crypto_auto_exec import okx_symbol
        except Exception:
            okx_symbol = lambda x: x
    except Exception as exc:
        return False, f"GAGAL import okx_client ({type(exc).__name__})"

    sym = okx_symbol(pair)
    try:
        pos = [p for p in (mx.positions(sym) or []) if abs(float(p.get("holdVol") or 0)) > 0]
        if not pos:
            return False, "tidak ada posisi OKX untuk pair ini (entry manual?) — set BE manual"
        p = pos[0]
        hold = int(float(p["holdVol"]))
        mx.cancel_stop_orders(sym)

        closed = 0
        partial_note = ""
        if hold >= 2:
            half = hold // 2
            r = mx.close_volume(sym, p, half)
            if r.get("success"):
                closed, hold = half, hold - half
                partial_note = f"partial {closed} lot ditutup"
            else:
                partial_note = f"partial GAGAL ({str(r)[:60]})"
        else:
            partial_note = f"partial TIDAK BISA ({hold} lot = ukuran terkecil)"

        be_note = "BE GAGAL"
        if be_level:
            for attempt in range(1, 5):
                res = mx.place_stop_order(sym, p, sl=be_level, tp=tp2, vol=hold)
                if res.get("success"):
                    be_note = f"SL {be_level:g} (BE) + TP {tp2:g} terpasang utk {hold} lot"
                    break
                time.sleep(4)
            else:
                return False, (f"{partial_note} · {be_note} — POSISI TANPA SL, "
                               f"perlu tindakan manual!")
        else:
            be_note = "level BE tidak diketahui — SL tidak diubah"

        # verifikasi ulang di exchange, bukan cuma percaya respons
        try:
            lst = mx.req("GET", "/api/v1/private/stoporder/list/orders", params=f"symbol={sym}")
            aktif = [s for s in (lst.get("data") or []) if s.get("state") == 1]
            ver = "verified" if aktif else "TIDAK terverifikasi"
        except Exception:
            ver = "verifikasi gagal"
        return True, f"{partial_note} · {be_note} · {ver}"
    except Exception as exc:
        return False, f"ERROR {type(exc).__name__}: {str(exc)[:90]}"


def main():
    if not os.path.exists(PATH):
        return
    try:
        data = json.load(open(PATH))
    except Exception:
        return
    items = data.get("items") or []
    if not items:
        return

    now = datetime.now(WIB).isoformat(timespec="seconds")
    alerts = []

    for it in items:
        st = it.get("status")
        if st not in ("still_open", "tp1_hit_runner"):
            continue
        symbol = str(it.get("pair", "")).replace("_", "")
        # PENTING: watchlist menulis arah di field `direction`, BUKAN `arah`.
        # Membaca `arah` saja -> nilainya "" -> "NONE" -> semua perbandingan
        # arah==LONG gagal -> TP/SL tidak pernah terdeteksi (watchdog buta).
        arah = str(it.get("arah") or it.get("direction") or "").upper()
        price = fetch_price(symbol)
        if not price:
            continue

        tp1, tp2, sl = num(it.get("tp1")), num(it.get("tp2")), num(it.get("sl"))
        entry = mid_entry(it.get("entry_zone", ""))
        pnl = it.get("pnl_pct")
        if entry:
            pnl = ((price - entry) / entry * 100) if arah == "LONG" \
                else ((entry - price) / entry * 100)

        # Intrabar check: use last 2 closed 1H candles' high/low so wick
        # breaches (e.g. low 0.1709 vs SL 0.1710) are caught, not just the
        # spot price at :05.
        lo_seen, hi_seen = price, price
        # Lookback sejak signal diposting, BUKAN cuma 2 candle terakhir. Kalau
        # cron sempat kelewat atau harga balik turun dari level TP, touch-nya
        # jadi hilang dari jendela -> aturan partial+BE nggak pernah jalan.
        limit = 2
        try:
            da = datetime.fromisoformat(str(it.get("date_added")).replace("Z", "+00:00"))
            if da.tzinfo is None:
                da = da.replace(tzinfo=WIB)
            jam = int((datetime.now(WIB) - da).total_seconds() // 3600) + 3
            limit = max(2, min(120, jam))
        except Exception:
            limit = 2
        try:
            out = subprocess.run(
                ["curl", "-s", "--max-time", "10",
                 f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval=1h&limit={limit}"],
                capture_output=True, text=True, timeout=15,
            ).stdout
            rows = json.loads(out)
            if isinstance(rows, list) and rows:
                # last row is the currently-forming candle — include its extremes too
                lo_seen = min([float(r[3]) for r in rows] + [price])
                hi_seen = max([float(r[2]) for r in rows] + [price])
        except Exception:
            logging.getLogger(__name__).debug("operasi dilewati", exc_info=True)

        def hit_tp(level):
            """TP itu limit order yang MENGGANTUNG di exchange — begitu levelnya
            kesentuh, order keisi. Jadi touch = hit.

            Guard lama "harus harga masih di level" SALAH untuk TP: waktu harga
            balik turun sebelum eval jam-an jalan, TP1 yang sudah kena jadi
            dianggap belum kena, dan aturan partial 50% + BE tidak pernah jalan.
            """
            if level is None:
                return False
            return (arah == "LONG" and hi_seen >= level) or (arah == "SHORT" and lo_seen <= level)

        def hit_sl(level):
            return level is not None and (
                (arah == "LONG" and lo_seen <= level)
                or (arah == "SHORT" and hi_seen >= level)
            )

        sid = it.get("signal_id", "")
        # Trade PAPER (exec_skip / tidak dieksekusi) tetap dilacak TP/SL-nya dan
        # dihitung di jurnal — tapi jangan pernah coba manage posisi nyata.
        global EXECUTED
        EXECUTED = not (it.get("exec_skip") or it.get("executed") is False)
        label = f"{it.get('pair')} {arah} {sid}"
        paper_tag = ""
        if not EXECUTED:
            label += " [PAPER — tanpa eksekusi]"
            paper_tag = "PAPER (tanpa eksekusi OKX). "
        ts = datetime.now(WIB).strftime("%d/%b %H:%M").replace("/", "/")
        if hit_tp(tp2):
            it["status"] = "closed_TP2"
            it["notes"] = paper_tag + f"TP2 hit @ {price} (auto hourly eval {ts})."
            alerts.append(
                f"🏆 {label}: TP2 HIT @ {fmt(price)} ({pnl:+.2f}% dr entry) — full target, posisi wajib close — SELESAI, hapus dari radar entry"
            )
        elif st == "still_open" and hit_tp(tp1):
            # ATURAN USER 26 Sep (binding): tiap TP1 kena -> partial 50% + SL ke BE.
            # Kalau lotnya nggak bisa dibelah -> BE saja. Hasilnya WAJIB dilaporkan.
            ok_m, msg_m = manage_tp1(it.get("pair", ""), entry, tp2)
            it["status"] = "closed_TP1"
            it["notes"] = (paper_tag + f"TP1 hit @ {price} (auto hourly eval {ts}). "
                           f"{'OK' if ok_m else 'PERLU MANUAL'}: {msg_m}")
            it["tp1_management"] = {"ts": now, "ok": ok_m, "detail": msg_m}
            alerts.append(
                f"{'🎯' if ok_m else '🚨'} {label}: TP1 HIT @ {fmt(price)} ({pnl:+.2f}%) → "
                f"{msg_m}"
                + ("" if ok_m else " — CEK POSISI MANUAL SEKARANG!")
            )
        elif hit_sl(sl):
            it["status"] = "closed_SL"
            it["notes"] = paper_tag + f"SL hit @ {price} (auto hourly eval {ts})."
            alerts.append(
                f"🛑 {label}: SL HIT @ {fmt(price)} ({pnl:+.2f}%) — posisi stop, jangan average — SELESAI"
            )

    try:
        json.dump(data, open(PATH, "w"), indent=2)
    except Exception:
        logging.getLogger(__name__).debug("operasi dilewati", exc_info=True)

    # sinkron ledger equity (append trade tertutup baru) — idempoten
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import crypto_equity
        n = crypto_equity.sync()
        if n:
            print(f"📈 equity ledger: +{n} trade tertutup tercatat")
    except Exception:
        logging.getLogger(__name__).debug("operasi dilewati", exc_info=True)

    if alerts:
        print("⏱ CRYPTO AUTO-EVAL (hourly) — " + now)
        for a in alerts:
            print("  " + a)


if __name__ == "__main__":
    main()
