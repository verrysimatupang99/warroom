#!/usr/bin/env python3
"""Paper trader momentum — menjalankan strategi yang sudah lolos uji.

Strategi (sama persis dengan backtest yang lolos):
  - Masuk LONG bila close > high tertinggi 55 bar.
  - Trailing stop 3 x ATR dari harga tertinggi sejak masuk.
  - Risiko 2% ekuitas per trade, fee 0,1% per sisi.

Tiap koin punya sub-akun sendiri (modal awal sama), seperti di backtest portofolio.
Tidak ada order nyata — hanya pencatatan.

State: /var/lib/warroom/momentum_paper.json
Trade: /var/lib/warroom/momentum_trades.csv
"""

from __future__ import annotations

import csv
import json
import os
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Sumber data: Binance USD-M futures, dipanggil langsung dari host ini.
# Sebelumnya kode ini menembak node internal lewat alamat Tailscale
# Tailscale lama yang sudah tidak ada, sehingga unit selalu gagal
# dengan Connection refused. Node itu tidak lagi dipakai di infrastruktur.
FAPI = os.environ.get("WARROOM_FAPI", "https://fapi.binance.com").rstrip("/")
STATE = Path("/var/lib/warroom/momentum_paper.json")
TRADES = Path("/var/lib/warroom/momentum_trades.csv")
N_MASUK = 55
ATR_MULT = 3.0
RISIKO = 0.02
FEE = 0.001
MODAL_KOIN = 500.0
LIMIT = 200
N_KOIN = 40


def ambil(url: str) -> Any:
    with urllib.request.urlopen(url, timeout=40) as r:
        return json.loads(r.read().decode())


def universe(jumlah: int = N_KOIN) -> list[str]:
    """Koin USDT perpetual yang aktif, diurutkan menurut volume 24 jam."""
    info = ambil(f"{FAPI}/fapi/v1/exchangeInfo")
    sah = {
        s["symbol"]
        for s in info["symbols"]
        if s.get("quoteAsset") == "USDT"
        and s.get("status") == "TRADING"
        and s.get("contractType") == "PERPETUAL"
    }
    ticker = [t for t in ambil(f"{FAPI}/fapi/v1/ticker/24hr") if t.get("symbol") in sah]
    ticker.sort(key=lambda t: float(t.get("quoteVolume") or 0), reverse=True)
    return [t["symbol"] for t in ticker[:jumlah]]


def klines(simbol: str) -> list[dict[str, Any]]:
    """Klines harian Binance, dibentuk ulang ke dict yang dipakai strategi."""
    mentah = ambil(f"{FAPI}/fapi/v1/klines?symbol={simbol}&interval=1d&limit={LIMIT}")
    return [
        {
            "t": r[0],
            "o": float(r[1]),
            "h": float(r[2]),
            "l": float(r[3]),
            "c": float(r[4]),
            "v": float(r[5]),
        }
        for r in mentah
    ]


def atr(c: list[dict], p: int = 14) -> float:
    if len(c) <= p:
        return 0.0
    tr = []
    for i in range(1, len(c)):
        h, lo, pc = c[i]["h"], c[i]["l"], c[i - 1]["c"]
        tr.append(max(h - lo, abs(h - pc), abs(lo - pc)))
    a = sum(tr[:p]) / p
    for x in tr[p:]:
        a = (a * (p - 1) + x) / p
    return a


def muat() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {}


def simpan(st: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, indent=1))


def catat(baris: dict) -> None:
    baru = not TRADES.exists()
    with TRADES.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(baris))
        if baru:
            w.writeheader()
        w.writerow(baris)


def main() -> None:
    uni = universe()
    st = muat()
    sekarang = datetime.now(UTC).isoformat(timespec="seconds")
    ringkas = {"dibuka": 0, "ditutup": 0, "dilewati": 0, "galat": 0}

    for sym in uni:
        try:
            c = klines(sym)
            if len(c) < N_MASUK + 2:
                ringkas["dilewati"] += 1
                continue
        except Exception:
            ringkas["galat"] += 1
            continue

        a = atr(c)
        close = c[-1]["c"]
        hi_lalu = max(x["h"] for x in c[-N_MASUK - 1 : -1])
        pos = st.setdefault(sym, {"kas": MODAL_KOIN, "qty": 0.0, "entry": 0.0, "puncak": 0.0})
        pos["harga"] = close
        pos["diperbarui"] = sekarang

        if pos["qty"] > 0:
            pos["puncak"] = max(pos["puncak"], close)
            stop = pos["puncak"] - ATR_MULT * a
            if close < stop:
                hasil = pos["qty"] * close * (1 - FEE)
                pos["kas"] += hasil
                pnl = (close - pos["entry"]) / pos["entry"] * 100
                catat({
                    "waktu": sekarang, "koin": sym, "aksi": "JUAL",
                    "harga": f"{close:.8g}", "qty": f"{pos['qty']:.8g}",
                    "pnl_pct": f"{pnl:+.2f}", "alasan": "trailing_stop",
                })
                pos["qty"] = 0.0
                pos["entry"] = 0.0
                pos["puncak"] = 0.0
                ringkas["ditutup"] += 1
        elif close > hi_lalu and a > 0:
            ekuitas = pos["kas"]
            qty_ideal = (ekuitas * RISIKO) / (ATR_MULT * a)
            biaya = qty_ideal * close
            if biaya > ekuitas:
                biaya = ekuitas
                qty = biaya * (1 - FEE) / close
            else:
                qty = qty_ideal * (1 - FEE)
            pos["kas"] -= biaya
            pos["qty"] = qty
            pos["entry"] = close
            pos["puncak"] = close
            catat({
                "waktu": sekarang, "koin": sym, "aksi": "BELI",
                "harga": f"{close:.8g}", "qty": f"{qty:.8g}",
                "pnl_pct": "", "alasan": "breakout_55",
            })
            ringkas["dibuka"] += 1

    simpan(st)

    total = 0.0
    terbuka = 0
    for p in st.values():
        harga = p.get("harga") or p["entry"] or 0.0
        total += p["kas"] + p["qty"] * harga
        if p["qty"] > 0:
            terbuka += 1

    modal = MODAL_KOIN * len(st) if st else 1
    print(f"{sekarang} | buka {ringkas['dibuka']} tutup {ringkas['ditutup']} "
          f"lewat {ringkas['dilewati']} galat {ringkas['galat']}")
    print(f"ekuitas ${total:,.2f} dari modal ${modal:,.0f} "
          f"({(total / modal - 1) * 100:+.2f}%) | posisi terbuka: {terbuka}/{len(st)}")


if __name__ == "__main__":
    main()
