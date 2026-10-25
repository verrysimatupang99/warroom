#!/usr/bin/env python3
"""Apakah momentum melindungi saat pasar bear?

Rezim ditentukan dari BTC: di bawah SMA200 = bear, di atas = bull.
Lalu kinerja momentum dan buy & hold dipisah per rezim.

Pemakaian: .venv/bin/python ops/uji_momentum_rezim.py [interval] [limit]
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


def kurva(c, a, mulai):
    ek, qty, puncak_h = 1.0, 0.0, 0.0
    out = {}
    for i in range(max(mulai, N_MASUK + 1), len(c)):
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
        out[c[i]["t"]] = ek + qty * close
    return out


def main():
    interval = sys.argv[1] if len(sys.argv) > 1 else "1d"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 2000
    btc = ambil(f"{NODE}/crypto/klines?symbol=BTCUSDT&interval={interval}&limit={limit}")["candles"]
    uni = ambil(f"{NODE}/crypto/universe")["symbols"]

    # rezim dari BTC: close vs SMA200
    closes = [x["c"] for x in btc]
    sma, rezim = {}, {}
    jml = 0.0
    for i, x in enumerate(btc):
        jml += closes[i]
        if i >= 200:
            jml -= closes[i - 200]
        if i >= 200:
            sma[x["t"]] = jml / 200
            rezim[x["t"]] = "bull" if closes[i] > sma[x["t"]] else "bear"

    hari_bear = sum(1 for v in rezim.values() if v == "bear")
    print(f"rezim BTC (SMA200): {len(rezim)} hari | bear {hari_bear} | bull {len(rezim) - hari_bear}")

    # kumpulkan return harian per rezim
    agg: dict[str, list[float]] = {"momentum_bear": [], "momentum_bull": [], "bh_bear": [], "bh_bull": []}
    n_koin = 0
    for sym in uni:
        try:
            c = ambil(f"{NODE}/crypto/klines?symbol={sym}&interval={interval}&limit={limit}")["candles"]
            if len(c) < 400:
                continue
        except Exception:
            continue
        a = atr_seri(c)
        k = kurva(c, a, 200)
        harga = {x["t"]: x["c"] for x in c}
        ts = [x["t"] for x in c if x["t"] in k and x["t"] in rezim]
        if len(ts) < 300:
            continue
        n_koin += 1
        for j in range(1, len(ts)):
            t0, t1 = ts[j - 1], ts[j]
            r_mom = k[t1] / k[t0] - 1
            r_bh = harga[t1] / harga[t0] - 1
            r = rezim[t1]
            agg[f"momentum_{r}"].append(r_mom)
            agg[f"bh_{r}"].append(r_bh)

    print(f"koin dianalisa: {n_koin}\n")
    print(f"{'rezim':>8}{'hari':>8}{'momentum':>12}{'B&H':>10}{'selisih':>10}")
    for r in ("bear", "bull"):
        mm = agg[f"momentum_{r}"]
        bb = agg[f"bh_{r}"]
        if not mm:
            continue
        tot_m = sum(mm) / len(mm) * 100
        tot_b = sum(bb) / len(bb) * 100
        print(f"{r:>8}{len(mm):>8}{tot_m:>11.3f}%{tot_b:>9.3f}%{tot_m - tot_b:>+9.3f}%")
    print("\n(angka = rata-rata return harian, bukan total)")


if __name__ == "__main__":
    main()
