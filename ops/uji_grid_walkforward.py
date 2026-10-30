#!/usr/bin/env python3
"""Walk-forward: apakah filter rezim tetap membantu di data yang BELUM PERNAH dilihat?

Bagi seri jadi dua: latih (60% awal) dan uji (40% akhir). Ambang dipilih dari
data latih saja, lalu diterapkan ke data uji. Kalau hasil uji tetap lebih baik
dari tanpa filter, berarti bukan curve fitting.

Pemakaian: .venv/bin/python ops/uji_grid_walkforward.py [interval] [limit]
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request

NODE = os.environ.get("WARROOM_TENCENT_BASE", "").rstrip("/")
KOIN = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "LINKUSDT"]
MODAL = 500.0
MAKS_LEVEL = 8
STEP_ATR = 0.5
PER_LEVEL = MODAL / MAKS_LEVEL
FEE = 0.001
AMBANG = [None, 4.0, 3.0, 2.0, 1.5, 1.0, 0.5]
BAGI = 0.60


def ambil(sym, interval, limit):
    url = f"{NODE}/crypto/klines?symbol={sym}&interval={interval}&limit={limit}"
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode())["candles"]


def ema(vals, p):
    out = [0.0] * len(vals)
    if len(vals) < p:
        return out
    k = 2 / (p + 1)
    out[p - 1] = sum(vals[:p]) / p
    for i in range(p, len(vals)):
        out[i] = vals[i] * k + out[i - 1] * (1 - k)
    return out


def atr(c, p=14):
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


def jalankan(c, a, e50, e200, ambang, mulai, akhir):
    """Jalankan grid dari bar `mulai` sampai `akhir` dengan modal segar."""
    kas, posisi = MODAL, []
    puncak, dd = MODAL, 0.0
    for i in range(mulai, akhir):
        if a[i] <= 0:
            continue
        step = a[i] * STEP_ATR
        hi, close = c[i]["h"], c[i]["c"]
        sisa = []
        for p in posisi:
            if hi >= p["tp"]:
                kas += p["qty"] * p["tp"] * (1 - FEE)
            else:
                sisa.append(p)
        posisi = sisa
        tren = abs(e50[i] - e200[i]) / a[i] if e200[i] > 0 else 0.0
        if ambang is None or tren <= ambang:
            if posisi and len(posisi) < MAKS_LEVEL and close <= posisi[-1]["entry"] - step:
                if kas >= PER_LEVEL:
                    qty = PER_LEVEL * (1 - FEE) / close
                    posisi.append({"entry": close, "qty": qty, "tp": close + step})
                    kas -= PER_LEVEL
            if not posisi and kas >= PER_LEVEL:
                qty = PER_LEVEL * (1 - FEE) / close
                posisi.append({"entry": close, "qty": qty, "tp": close + step})
                kas -= PER_LEVEL
        nilai = sum(p["qty"] * close for p in posisi)
        ek = kas + nilai
        puncak = max(puncak, ek)
        if puncak > 0:
            dd = max(dd, 1 - ek / puncak)
    akhir_ek = kas + sum(p["qty"] * c[akhir - 1]["c"] for p in posisi)
    return (akhir_ek / MODAL - 1) * 100, dd * 100


def main():
    interval = sys.argv[1] if len(sys.argv) > 1 else "1d"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 2000
    print(f"walk-forward | latih {BAGI:.0%} awal, uji {1 - BAGI:.0%} akhir | {limit} candle")
    print(f"\n{'koin':>10}{'pilih':>8}{'latih':>8}{'uji':>8}{'uji tanpa':>10}{'selisih':>9}")
    total_ada, total_tanpa, n = 0.0, 0.0, 0
    for sym in KOIN:
        try:
            c = ambil(sym, interval, limit)
        except Exception as exc:
            print(f"{sym:>10}  gagal: {exc}")
            continue
        a = atr(c)
        cl = [x["c"] for x in c]
        e50, e200 = ema(cl, 50), ema(cl, 200)
        batas = int(len(c) * BAGI)
        # pilih ambang terbaik di data latih
        hasil_latih = {t: jalankan(c, a, e50, e200, t, 200, batas)[0] for t in AMBANG}
        pilih = max(hasil_latih, key=lambda t: hasil_latih[t])
        # uji di data yang belum dilihat
        uji_ada = jalankan(c, a, e50, e200, pilih, batas, len(c))[0]
        uji_tanpa = jalankan(c, a, e50, e200, None, batas, len(c))[0]
        total_ada += uji_ada
        total_tanpa += uji_tanpa
        n += 1
        label = "tanpa" if pilih is None else f"<={pilih}"
        print(
            f"{sym:>10}{label:>8}{hasil_latih[pilih]:>+7.0f}%{uji_ada:>+7.0f}%"
            f"{uji_tanpa:>+9.0f}%{uji_ada - uji_tanpa:>+8.0f}%"
        )
    if n:
        r_ada, r_tanpa = total_ada / n, total_tanpa / n
        print(f"\n{'RATA-RATA':>10}{'':>8}{'':>8}{r_ada:>+7.0f}%{r_tanpa:>+9.0f}%{r_ada - r_tanpa:>+8.0f}%")


if __name__ == "__main__":
    main()
