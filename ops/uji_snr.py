#!/usr/bin/env python3
"""Uji hipotesis SNR: apakah SL yang jatuh di dalam zona S/R lebih sering gagal?

Metode: walk-forward pada candle M5 XAUUSD nyata. Untuk setiap bar, peta zona
dibangun HANYA dari candle sebelumnya (tidak ada look-ahead), lalu satu posisi
hipotetis dibuka dan hasilnya dicatat sampai SL atau TP tersentuh.

Pemakaian:
    .venv/bin/python ops/uji_snr.py            # default 5 hari
    .venv/bin/python ops/uji_snr.py 60d        # 60 hari (validasi Tahap 3)

Tidak mengubah sistem apa pun — hanya mengukur.
"""

from __future__ import annotations

import asyncio
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages/core/src"))

from warroom_core.forex.engine import fetch_klines_direct  # noqa: E402
from warroom_core.forex.snr import peta_snr, sl_terlindungi  # noqa: E402

LOOKBACK = 120      # bar histori untuk membangun peta zona
MAKS_BAR = 60       # horizon simulasi
SL_ATR = 1.5
TP_ATR = 2.0
BUFFER_ATR = 0.3
PERIODE_ATR = 14


def atr_bergulir(candles: list[dict], periode: int = PERIODE_ATR) -> list[float]:
    """ATR Wilder dihitung sekali untuk seluruh seri (O(n)), bukan per bar."""
    n = len(candles)
    out = [0.0] * n
    if n <= periode:
        return out
    tr = [0.0] * n
    for i in range(1, n):
        h, lo = candles[i]["h"], candles[i]["l"]
        pc = candles[i - 1]["c"]
        tr[i] = max(h - lo, abs(h - pc), abs(lo - pc))
    out[periode] = sum(tr[1 : periode + 1]) / periode
    for i in range(periode + 1, n):
        out[i] = (out[i - 1] * (periode - 1) + tr[i]) / periode
    return out


def z_dua_proporsi(k1: int, n1: int, k2: int, n2: int) -> tuple[float, float]:
    p1, p2 = k1 / n1, k2 / n2
    pool = (k1 + k2) / (n1 + n2)
    se = math.sqrt(pool * (1 - pool) * (1 / n1 + 1 / n2))
    if se == 0:
        return 0.0, 1.0
    z = (p1 - p2) / se
    pv = 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))
    return z, pv


def main() -> None:
    rentang = sys.argv[1] if len(sys.argv) > 1 else "5d"
    candles = asyncio.run(fetch_klines_direct("XAUUSD", "5m", rentang))
    if len(candles) < LOOKBACK + MAKS_BAR + 20:
        print(f"data tidak cukup: {len(candles)} candle")
        return
    atr_seri = atr_bergulir(candles)
    print(f"candle: {len(candles)} | rentang: {rentang}")

    hasil: dict[str, list[str]] = {"terlindungi": [], "rentan": []}
    contoh: list[str] = []
    total = len(candles) - MAKS_BAR - LOOKBACK

    for idx, i in enumerate(range(LOOKBACK, len(candles) - MAKS_BAR)):
        if idx and idx % 5000 == 0:
            print(f"  ... {idx}/{total}")
        atr = atr_seri[i]
        if atr <= 0:
            continue
        zonas = peta_snr(candles[i - LOOKBACK : i], atr)
        entry = float(candles[i]["c"])

        for arah, nama in ((1, "LONG"), (-1, "SHORT")):
            sl = entry - arah * SL_ATR * atr
            tp = entry + arah * TP_ATR * atr
            aman, alasan = sl_terlindungi(entry, sl, zonas, BUFFER_ATR * atr)
            keluar = None
            for c in candles[i + 1 : i + 1 + MAKS_BAR]:
                if arah == 1:
                    if c["l"] <= sl:
                        keluar = "SL"
                        break
                    if c["h"] >= tp:
                        keluar = "TP"
                        break
                else:
                    if c["h"] >= sl:
                        keluar = "SL"
                        break
                    if c["l"] <= tp:
                        keluar = "TP"
                        break
            if keluar is None:
                continue
            hasil["terlindungi" if aman else "rentan"].append(keluar)
            if len(contoh) < 2 and not aman:
                contoh.append(f"{nama} @ {entry:.2f} — {alasan}")

    print()
    ringkas: dict[str, tuple[int, int]] = {}
    for k in ("terlindungi", "rentan"):
        arr = hasil[k]
        if not arr:
            print(f"{k:12}: tidak ada sampel")
            continue
        tp = arr.count("TP")
        ringkas[k] = (tp, len(arr))
        eks = (tp / len(arr)) * TP_ATR - (1 - tp / len(arr)) * SL_ATR
        print(
            f"{k:12}: n={len(arr):>6}  TP={tp:>6}  win={100 * tp / len(arr):5.1f}%"
            f"  expectancy={eks / SL_ATR:+.3f} R"
        )

    if len(ringkas) == 2:
        (k1, n1), (k2, n2) = ringkas["terlindungi"], ringkas["rentan"]
        z, pv = z_dua_proporsi(k1, n1, k2, n2)
        print(f"\nselisih win rate: {100 * (k1 / n1 - k2 / n2):+.1f} poin")
        print(f"z = {z:.3f} | p-value = {pv:.4f}")
        print("VERDICT:", "SIGNIFIKAN (p<0,05)" if pv < 0.05 else "belum signifikan")
    if contoh:
        print("\ncontoh SL rentan:")
        for c in contoh:
            print("  -", c)


if __name__ == "__main__":
    main()
