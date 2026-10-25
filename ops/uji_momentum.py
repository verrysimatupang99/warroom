#!/usr/bin/env python3
"""Uji momentum / trend following pada spot crypto (Donchian breakout).

Aturan (tanpa look-ahead — sinyal pakai bar sebelumnya, eksekusi di close):
  - Masuk LONG bila close menembus high tertinggi N bar sebelumnya.
  - Keluar bila close menembus low terendah M bar sebelumnya (trailing).
  - Fee 0,1% per sisi.

Dua mode: seluruh data (in-sample) dan walk-forward (latih 60% → uji 40%).

Pemakaian: .venv/bin/python ops/uji_momentum.py [interval] [limit]
"""

from __future__ import annotations

import json
import sys
import urllib.request

NODE = "http://100.126.10.74:8790"
KOIN = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "LINKUSDT"]
FEE = 0.001
PARAM = [(20, 10), (55, 20), (100, 50), (20, 20)]


def ambil(sym, interval, limit):
    url = f"{NODE}/crypto/klines?symbol={sym}&interval={interval}&limit={limit}"
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode())["candles"]


def jalankan(c, n_masuk, n_keluar, mulai=0, akhir=None):
    """Kembalikan (return%, maxDD%, jumlah trade, win%)."""
    akhir = akhir or len(c)
    modal = 1.0
    posisi = 0.0        # qty aset
    harga_masuk = 0.0
    puncak, dd = modal, 0.0
    trades, menang = 0, 0

    for i in range(max(mulai, n_masuk + 1), akhir):
        close = c[i]["c"]
        hi_lalu = max(x["h"] for x in c[i - n_masuk : i])
        lo_lalu = min(x["l"] for x in c[i - n_keluar : i])

        if posisi == 0.0:
            if close > hi_lalu:
                posisi = modal * (1 - FEE) / close
                harga_masuk = close
                modal = 0.0
        else:
            if close < lo_lalu:
                modal = posisi * close * (1 - FEE)
                trades += 1
                if close > harga_masuk:
                    menang += 1
                posisi = 0.0

        ekuitas = modal + posisi * close
        puncak = max(puncak, ekuitas)
        if puncak > 0:
            dd = max(dd, 1 - ekuitas / puncak)

    ekuitas = modal + posisi * c[akhir - 1]["c"]
    return (ekuitas - 1) * 100, dd * 100, trades, (100 * menang / trades if trades else 0)


def main():
    interval = sys.argv[1] if len(sys.argv) > 1 else "1d"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 2000
    print(f"momentum Donchian | {interval} | {limit} candle | fee {FEE:.1%}/sisi")

    print("\n=== A. Seluruh data (in-sample) ===")
    print(f"{'koin':>10}{'B&H':>8}" + "".join(f"{f'{a}/{b}':>12}" for a, b in PARAM))
    total = {p: 0.0 for p in PARAM}
    for sym in KOIN:
        try:
            c = ambil(sym, interval, limit)
        except Exception as exc:
            print(f"{sym:>10} gagal: {exc}")
            continue
        bh = (c[-1]["c"] / c[0]["c"] - 1) * 100
        baris = f"{sym:>10}{bh:>+7.0f}%"
        for p in PARAM:
            r = jalankan(c, p[0], p[1])
            total[p] += r[0]
            baris += f"{r[0]:>+8.0f}%/{r[2]:>2}"
        print(baris)
    print(f"{'RATA2':>10}{'':>8}" + "".join(f"{total[p] / len(KOIN):>+8.0f}%  " for p in PARAM))

    print("\n=== B. Walk-forward (latih 60% → uji 40%) ===")
    print(f"{'koin':>10}{'pilih':>10}{'uji':>8}{'DD':>6}{'B&H uji':>9}{'DD':>6}{'trade':>7}")
    tot_m, tot_b, n = 0.0, 0.0, 0
    dd_m, dd_b = 0.0, 0.0
    for sym in KOIN:
        try:
            c = ambil(sym, interval, limit)
        except Exception:
            continue
        batas = int(len(c) * 0.60)
        latih = {p: jalankan(c, p[0], p[1], 0, batas)[0] for p in PARAM}
        pilih = max(latih, key=lambda k: latih[k])
        uji, dd, tr, _ = jalankan(c, pilih[0], pilih[1], batas, len(c))
        bh = (c[-1]["c"] / c[batas]["c"] - 1) * 100
        # DD buy & hold pada periode uji
        pk, ddb = c[batas]["c"], 0.0
        for x in c[batas:]:
            pk = max(pk, x["c"])
            ddb = max(ddb, 1 - x["c"] / pk)
        tot_m += uji
        tot_b += bh
        dd_m += dd
        dd_b += ddb * 100
        n += 1
        print(
            f"{sym:>10}{f'{pilih[0]}/{pilih[1]}':>10}{uji:>+7.0f}%{dd:>5.0f}%"
            f"{bh:>+8.0f}%{ddb * 100:>5.0f}%{tr:>7}"
        )
    if n:
        print(
            f"{'RATA2':>10}{'':>10}{tot_m / n:>+7.0f}%{dd_m / n:>5.0f}%"
            f"{tot_b / n:>+8.0f}%{dd_b / n:>5.0f}%"
        )


if __name__ == "__main__":
    main()
