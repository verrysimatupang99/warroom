"""Bootstrap Monte Carlo dari deret R — dipakai untuk mengukur risiko, bukan meramal.

DeepSeek memakai 10.000 bootstrap untuk P(profit) dan drawdown; War Room sebelumnya
hanya punya satu jalur equity. Modul ini murni dan deterministik lewat `seed`, supaya
angka di jurnal bisa direproduksi.
"""

from __future__ import annotations

import random
from typing import Any

N_DEFAULT = 10_000
SEED_DEFAULT = 42


def bootstrap(
    nilai: list[float],
    *,
    n: int = N_DEFAULT,
    seed: int = SEED_DEFAULT,
) -> dict[str, Any]:
    """Resample R dengan pengembalian; kembalikan distribusi total R dan max drawdown."""
    data = [float(x) for x in nilai if x is not None]
    if not data:
        return {"n_sampel": 0, "n_simulasi": 0}
    if n <= 0:
        raise ValueError("n simulasi harus > 0")
    rng = random.Random(seed)
    panjang = len(data)
    totals: list[float] = []
    dd: list[float] = []
    profit = 0
    for _ in range(n):
        sampel = [data[rng.randrange(panjang)] for _ in range(panjang)]
        ekuitas = 0.0
        puncak = 0.0
        drawdown = 0.0
        for r in sampel:
            ekuitas += r
            puncak = max(puncak, ekuitas)
            drawdown = max(drawdown, puncak - ekuitas)
        totals.append(ekuitas)
        dd.append(drawdown)
        if ekuitas > 0:
            profit += 1
    totals.sort()
    dd.sort()

    def persen(arr: list[float], p: float) -> float:
        idx = min(len(arr) - 1, max(0, int(round((len(arr) - 1) * p))))
        return round(arr[idx], 3)

    return {
        "n_sampel": panjang,
        "n_simulasi": n,
        "seed": seed,
        "p_profit": round(profit / n * 100, 1),
        "total_p5": persen(totals, 0.05),
        "total_p50": persen(totals, 0.50),
        "total_p95": persen(totals, 0.95),
        "maxdd_p95": persen(dd, 0.95),
    }
