#!/usr/bin/env python3
"""Momentum pada 40 koin sebagai PORTOFOLIO (bukan satu koin all-in).

Trend follower sungguhan menyebar risiko ke banyak pasar. Di sini tiap koin
mendapat porsi modal yang sama, lalu kurva ekuitas digabung — itu yang
menentukan drawdown portofolio yang sebenarnya.

Aturan per koin:
  - Masuk LONG bila close > high tertinggi 55 bar.
  - Trailing stop 3 x ATR (Chandelier).
  - Risiko 2% ekuitas per trade.
  - Fee 0,1% per sisi.

Pemakaian: .venv/bin/python ops/uji_momentum_portofolio.py [interval] [limit]
"""

from __future__ import annotations

import json
import sys
import urllib.request

NODE = "http://100.126.10.74:8790"
FEE = 0.001
N_MASUK = 55
RISIKO = 0.02
ATR_MULT = 3.0
BAGI = 0.60


def ambil(url):
    with urllib.request.urlopen(url, timeout=40) as r:
        return json.loads(r.read().decode())


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


def kurva(c, a, mulai, akhir):
    """Kembalikan daftar ekuitas (mulai 1.0) sepanjang periode."""
    ek, qty, puncak_h = 1.0, 0.0, 0.0
    out = []
    for i in range(max(mulai, N_MASUK + 1), akhir):
        close, atr_i = c[i]["c"], a[i]
        if atr_i > 0:
            hi_lalu = max(x["h"] for x in c[i - N_MASUK : i])
            stop = puncak_h - ATR_MULT * atr_i if qty > 0 else 0.0
            if qty == 0.0 and close > hi_lalu:
                qty_ideal = (ek * RISIKO) / (ATR_MULT * atr_i)
                biaya = qty_ideal * close
                if biaya > ek:
                    biaya = ek
                    qty = biaya * (1 - FEE) / close
                else:
                    qty = qty_ideal * (1 - FEE)
                puncak_h = close
                ek -= biaya
            elif qty > 0:
                puncak_h = max(puncak_h, close)
                if close < stop:
                    ek += qty * close * (1 - FEE)
                    qty, puncak_h = 0.0, 0.0
        out.append(ek + qty * close)
    return out


def main():
    interval = sys.argv[1] if len(sys.argv) > 1 else "1d"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 2000
    uni = ambil(f"{NODE}/crypto/universe")["symbols"]
    print(f"portofolio {len(uni)} koin | {interval} | {limit} candle | risiko {RISIKO:.0%}/trade")
    print(f"uji out-of-sample: {1 - BAGI:.0%} data terakhir\n")

    hasil: list[tuple[str, float]] = []
    kurva_semua: list[list[float]] = []
    gagal = 0
    for sym in uni:
        try:
            c = ambil(f"{NODE}/crypto/klines?symbol={sym}&interval={interval}&limit={limit}")["candles"]
            if len(c) < 300:
                gagal += 1
                continue
        except Exception:
            gagal += 1
            continue
        a = atr_seri(c)
        batas = int(len(c) * BAGI)
        k = kurva(c, a, batas, len(c))
        if not k:
            gagal += 1
            continue
        hasil.append((sym, (k[-1] - 1) * 100))
        kurva_semua.append(k)

    if not hasil:
        print("tidak ada data")
        return

    hasil.sort(key=lambda x: -x[1])
    positif = sum(1 for _, r in hasil if r > 0)
    print(f"koin diuji: {len(hasil)} | gagal: {gagal} | positif: {positif} "
          f"({100 * positif / len(hasil):.0f}%)")
    print(f"return rata-rata: {sum(r for _, r in hasil) / len(hasil):+.0f}%")
    print(f"terbaik: {hasil[0][0]} {hasil[0][1]:+.0f}% | terburuk: {hasil[-1][0]} {hasil[-1][1]:+.0f}%")

    # kurva portofolio: rata-rata ekuitas semua koin (selaraskan di UJUNG, bukan awal)
    pnj = min(len(k) for k in kurva_semua)
    port = [sum(k[-pnj + i] for k in kurva_semua) / len(kurva_semua) for i in range(pnj)]
    puncak, dd = port[0], 0.0
    for v in port:
        puncak = max(puncak, v)
        dd = max(dd, 1 - v / puncak)
    print(f"\nPORTOFOLIO: return {(port[-1] - 1) * 100:+.1f}% | max DD {dd * 100:.1f}%")
    print(f"rasio return/DD: {abs((port[-1] - 1) * 100) / (dd * 100) if dd else 0:.2f}")

    print("\n10 terbaik:")
    for s, r in hasil[:10]:
        print(f"  {s:>12} {r:>+7.0f}%")
    print("5 terburuk:")
    for s, r in hasil[-5:]:
        print(f"  {s:>12} {r:>+7.0f}%")


if __name__ == "__main__":
    main()
