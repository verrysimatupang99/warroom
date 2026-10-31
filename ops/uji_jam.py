#!/usr/bin/env python3
"""Uji filter jam pada XAUUSD: apakah jam tertentu punya expectancy lebih baik?

Metode sama dengan uji SNR: walk-forward, entry sintetis (SL 1,5 ATR, TP 2,0 ATR),
hasil dikelompokkan per jam server. Tidak mengubah sistem apa pun.

Pemakaian: .venv/bin/python ops/uji_jam.py [rentang]   (default 60d)
"""

from __future__ import annotations

import asyncio
import math
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages/core/src"))

from warroom_core.forex.engine import fetch_klines_direct  # noqa: E402

MAKS_BAR = 60
SL_ATR = 1.5
TP_ATR = 2.0


def atr_seri(c: list[dict], p: int = 14) -> list[float]:
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


def main() -> None:
    rentang = sys.argv[1] if len(sys.argv) > 1 else "60d"
    c = asyncio.run(fetch_klines_direct("XAUUSD", "5m", rentang))
    if len(c) < MAKS_BAR + 30:
        print("data tidak cukup:", len(c))
        return
    atr = atr_seri(c)
    print(f"candle: {len(c)} | rentang: {rentang}")

    per_jam: dict[int, list[int]] = defaultdict(list)  # jam -> [1=TP, 0=SL]
    for i in range(20, len(c) - MAKS_BAR):
        a = atr[i]
        if a <= 0:
            continue
        jam = (c[i]["t"] // 3600) % 24
        for arah in (1, -1):
            entry = c[i]["c"]
            sl = entry - arah * SL_ATR * a
            tp = entry + arah * TP_ATR * a
            for k in c[i + 1 : i + 1 + MAKS_BAR]:
                if arah == 1:
                    if k["l"] <= sl:
                        per_jam[jam].append(0)
                        break
                    if k["h"] >= tp:
                        per_jam[jam].append(1)
                        break
                else:
                    if k["h"] >= sl:
                        per_jam[jam].append(0)
                        break
                    if k["l"] <= tp:
                        per_jam[jam].append(1)
                        break

    print(f"\n{'jam':>4}{'n':>7}{'win%':>7}{'expR':>8}")
    semua: list[int] = []
    for j in sorted(per_jam):
        v = per_jam[j]
        semua += v
        w = sum(v) / len(v)
        print(f"{j:>4}{len(v):>7}{100 * w:>6.1f}%{(w * TP_ATR - (1 - w) * SL_ATR) / SL_ATR:>+8.3f}")
    w0 = sum(semua) / len(semua)
    print(f"{'ALL':>4}{len(semua):>7}{100 * w0:>6.1f}%{(w0 * TP_ATR - (1 - w0) * SL_ATR) / SL_ATR:>+8.3f}")

    terbaik = max(per_jam, key=lambda j: sum(per_jam[j]) / len(per_jam[j]))
    v = per_jam[terbaik]
    w = sum(v) / len(v)
    p1 = sum(v) / len(v)
    p2 = w0
    pool = (sum(v) + sum(semua)) / (len(v) + len(semua))
    se = math.sqrt(pool * (1 - pool) * (1 / len(v) + 1 / len(semua)))
    pv = 2 * (1 - 0.5 * (1 + math.erf(abs((p1 - p2) / se) / math.sqrt(2)))) if se else 1.0
    print(f"\njam terbaik: {terbaik} (win {100 * w:.1f}%, n={len(v)}) | p vs semua = {pv:.4f}")


if __name__ == "__main__":
    main()
