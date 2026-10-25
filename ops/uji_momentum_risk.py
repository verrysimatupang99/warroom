#!/usr/bin/env python3
"""Momentum versi realistis: risk-based sizing + trailing stop ATR.

Versi sebelumnya all-in (100% modal per posisi) sehingga drawdown 56%.
Trend follower sungguhan memakai risiko tetap per posisi (mis. 2% ekuitas)
dengan stop berbasis ATR. Itu yang diuji di sini.

Aturan:
  - Masuk LONG bila close > high tertinggi N bar sebelumnya.
  - Stop awal & trailing: 3 x ATR dari harga tertinggi sejak masuk (Chandelier).
  - Ukuran posisi = (ekuitas x risiko%) / (3 x ATR), dibatasi ekuitas.
  - Fee 0,1% per sisi.

Pemakaian: .venv/bin/python ops/uji_momentum_risk.py [interval] [limit]
"""

from __future__ import annotations

import json
import sys
import urllib.request

NODE = "http://100.126.10.74:8790"
KOIN = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "LINKUSDT"]
FEE = 0.001
N_MASUK = 55
RISIKO = 0.02      # 2% ekuitas per trade
ATR_MULT = 3.0


def ambil(sym, interval, limit):
    url = f"{NODE}/crypto/klines?symbol={sym}&interval={interval}&limit={limit}"
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode())["candles"]


def atr_seri(c, p=14):
    n = len(c)
    out = [0.0] * n
    if n <= p:
        return out
    tr = [0.0] * n
    for i in range(1, n):
        h, lo, pc = c[i]["h"], c[i]["l"], c[i - 1]["c"]
        tr[i] = max(h - lo, abs(h - pc), abs(lo - pc))
    out[p] = sum(tr[1 : p + 1]) / p
    for i in range(p + 1, n):
        out[i] = (out[i - 1] * (p - 1) + tr[i]) / p
    return out


def jalankan(c, a, mulai=0, akhir=None):
    akhir = akhir or len(c)
    ekuitas = 1.0
    qty = 0.0
    puncak_harga = 0.0
    puncak_eq, dd = 1.0, 0.0
    trades, menang = 0, 0
    biaya_masuk = 0.0

    for i in range(max(mulai, N_MASUK + 1), akhir):
        close, atr_i = c[i]["c"], a[i]
        if atr_i <= 0:
            continue
        hi_lalu = max(x["h"] for x in c[i - N_MASUK : i])
        stop = puncak_harga - ATR_MULT * atr_i if qty > 0 else 0.0

        if qty == 0.0 and close > hi_lalu:
            risiko_usd = ekuitas * RISIKO
            qty_ideal = risiko_usd / (ATR_MULT * atr_i)   # unit aset
            biaya = qty_ideal * close                      # USD yang dibutuhkan
            if biaya > ekuitas:                            # batasi ke kas tersedia
                biaya = ekuitas
                qty = biaya * (1 - FEE) / close
            else:
                qty = qty_ideal * (1 - FEE)
            biaya_masuk = close
            puncak_harga = close
            ekuitas -= biaya
        elif qty > 0:
            puncak_harga = max(puncak_harga, close)
            if close < stop:
                ekuitas += qty * close * (1 - FEE)
                trades += 1
                if close > biaya_masuk:
                    menang += 1
                qty = 0.0
                puncak_harga = 0.0

        total = ekuitas + qty * close
        puncak_eq = max(puncak_eq, total)
        if puncak_eq > 0:
            dd = max(dd, 1 - total / puncak_eq)

    total = ekuitas + qty * c[akhir - 1]["c"]
    return (total - 1) * 100, dd * 100, trades, (100 * menang / trades if trades else 0)


def main():
    interval = sys.argv[1] if len(sys.argv) > 1 else "1d"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 2000
    print(
        f"momentum risk-based | risiko {RISIKO:.0%}/trade | stop {ATR_MULT}xATR | N={N_MASUK}"
    )
    print(
        f"\n{'koin':>10}{'penuh':>9}{'DD':>6}{'trade':>7}{'win':>6}"
        f"{'  | uji OOS':>12}{'DD':>6}{'trade':>7}"
    )
    tm, td, n = 0.0, 0.0, 0
    for sym in KOIN:
        try:
            c = ambil(sym, interval, limit)
        except Exception as exc:
            print(f"{sym:>10} gagal: {exc}")
            continue
        a = atr_seri(c)
        r_all = jalankan(c, a)
        batas = int(len(c) * 0.60)
        r_oos = jalankan(c, a, batas, len(c))
        tm += r_oos[0]
        td += r_oos[1]
        n += 1
        print(
            f"{sym:>10}{r_all[0]:>+8.0f}%{r_all[1]:>5.0f}%{r_all[2]:>7}{r_all[3]:>5.0f}%"
            f"{r_oos[0]:>+11.0f}%{r_oos[1]:>5.0f}%{r_oos[2]:>7}"
        )
    if n:
        print(f"{'RATA2':>10}{'':>8}{'':>5}{'':>7}{'':>6}{tm / n:>+11.0f}%{td / n:>5.0f}%")


if __name__ == "__main__":
    main()
