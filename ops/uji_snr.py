#!/usr/bin/env python3
"""Uji hipotesis SNR: apakah SL yang jatuh di dalam zona S/R lebih sering gagal?

Metode: walk-forward pada candle M5 XAUUSD nyata. Untuk setiap bar, peta zona
dibangun HANYA dari candle sebelumnya (tidak ada look-ahead), lalu satu posisi
hipotetis dibuka dan hasilnya dicatat sampai SL atau TP tersentuh.

Tidak mengubah sistem apa pun — hanya mengukur.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages/core/src"))

from warroom_core.forex.engine import calculate_indicators, fetch_klines_direct  # noqa: E402
from warroom_core.forex.snr import peta_snr, sl_terlindungi  # noqa: E402

LOOKBACK = 120      # bar histori untuk membangun peta zona
MAKS_BAR = 60       # horizon simulasi
SL_ATR = 1.5
TP_ATR = 2.0
BUFFER_ATR = 0.3


def main() -> None:
    candles = asyncio.run(fetch_klines_direct("XAUUSD", "5m", "5d"))
    if len(candles) < LOOKBACK + MAKS_BAR + 20:
        print(f"data tidak cukup: {len(candles)} candle")
        return
    print(f"candle: {len(candles)}")

    hasil: dict[str, list[str]] = {"terlindungi": [], "rentan": []}
    contoh: list[str] = []

    for i in range(LOOKBACK, len(candles) - MAKS_BAR):
        hist = candles[:i]
        ind = calculate_indicators(hist)
        atr = ind.get("atr14") or ind.get("atr") or 0.0
        if not atr or atr <= 0:
            continue
        zonas = peta_snr(hist[-LOOKBACK:], atr)
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
            if len(contoh) < 3 and not aman:
                contoh.append(f"{nama} @ {entry:.2f} — {alasan}")

    print()
    for k in ("terlindungi", "rentan"):
        arr = hasil[k]
        if not arr:
            print(f"{k:12}: tidak ada sampel")
            continue
        tp = arr.count("TP")
        print(f"{k:12}: n={len(arr):>5}  TP={tp:>5}  win={100 * tp / len(arr):5.1f}%")

    a, b = hasil["terlindungi"], hasil["rentan"]
    if a and b:
        wa, wb = a.count("TP") / len(a), b.count("TP") / len(b)
        print(f"\nselisih win rate: {100 * (wa - wb):+.1f} poin persentase")
    if contoh:
        print("\ncontoh SL rentan:")
        for c in contoh:
            print("  -", c)


if __name__ == "__main__":
    main()
