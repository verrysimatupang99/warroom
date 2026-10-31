#!/usr/bin/env python3
"""Uji sistem grid + averaging pada XAUUSD nyata.

Menjawab pertanyaan: apakah grid/avg benar-benar menghasilkan, dan berapa
drawdown yang harus ditanggung? Dijalankan pada candle M5 historis, bukan
order nyata.

Aturan yang disimulasikan:
  - Buka 1 posisi saat flat (arah LONG, beli saat turun).
  - Setiap harga turun `step` dari entry terakhir, tambah 1 level (maks N level).
  - Tiap posisi punya TP sendiri: entry + step.
  - Opsi hard stop: tutup semua bila floating loss melewati batas.

Pemakaian: .venv/bin/python ops/uji_grid.py [rentang]
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages/core/src"))

from warroom_core.forex.engine import fetch_klines_direct  # noqa: E402

LOT = 0.01          # 1 oz -> $1 per $1 gerakan
STEP_ATR = 0.5      # jarak antar level
MAKS_LEVEL = 8
ATR_P = 14


def atr_seri(c: list[dict], p: int = ATR_P) -> list[float]:
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


def jalankan(c: list[dict], atr: list[float], maks_loss_pct: float | None) -> dict:
    saldo = 500.0
    posisi: list[dict] = []          # {entry, tp}
    puncak = saldo
    dd_maks = 0.0
    ditutup_paksa = 0
    siklus = 0

    for i in range(ATR_P + 1, len(c)):
        a = atr[i]
        if a <= 0:
            continue
        step = a * STEP_ATR
        hi, close = c[i]["h"], c[i]["c"]

        # 1. TP per posisi
        masih = []
        for p in posisi:
            if hi >= p["tp"]:
                saldo += (p["tp"] - p["entry"]) * LOT * 100
            else:
                masih.append(p)
        posisi = masih

        # 2. Tambah level bila turun
        if posisi and len(posisi) < MAKS_LEVEL:
            terakhir = posisi[-1]["entry"]
            if close <= terakhir - step:
                posisi.append({"entry": close, "tp": close + step})

        # 3. Buka posisi pertama bila flat
        if not posisi:
            posisi.append({"entry": close, "tp": close + step})
            siklus += 1

        # 4. Hard stop
        floating = sum((close - p["entry"]) * LOT * 100 for p in posisi)
        if maks_loss_pct is not None and floating < -saldo * maks_loss_pct / 100:
            saldo += floating
            posisi = []
            ditutup_paksa += 1

        ekuitas = saldo + floating
        puncak = max(puncak, ekuitas)
        if puncak > 0:
            dd_maks = max(dd_maks, 1 - ekuitas / puncak)
        if ekuitas <= 0:
            return {
                "saldo": ekuitas, "ekuitas": ekuitas, "dd": 100.0,
                "paksa": ditutup_paksa, "siklus": siklus, "terbuka": 0,
                "ruin": i,
            }

    akhir = saldo + sum((c[-1]["c"] - p["entry"]) * LOT * 100 for p in posisi)
    return {
        "saldo": saldo, "ekuitas": akhir, "dd": dd_maks * 100,
        "paksa": ditutup_paksa, "siklus": siklus, "terbuka": len(posisi),
        "ruin": None,
    }


def main() -> None:
    rentang = sys.argv[1] if len(sys.argv) > 1 else "60d"
    c = asyncio.run(fetch_klines_direct("XAUUSD", "5m", rentang))
    print(f"candle: {len(c)} | rentang: {rentang} | level maks: {MAKS_LEVEL}")
    atr = atr_seri(c)
    print(f"\n{'skenario':>20}{'ekuitas':>10}{'return':>9}{'maxDD':>8}{'paksa':>7}{'siklus':>7}{'bangkrut':>9}")
    for label, batas in (
        ("tanpa hard stop", None),
        ("hard stop 10%", 10.0),
        ("hard stop 5%", 5.0),
        ("hard stop 2%", 2.0),
    ):
        r = jalankan(c, atr, batas)
        ret = (r["ekuitas"] / 500 - 1) * 100
        if r["ruin"] is not None:
            import datetime as _dt

            hari = _dt.datetime.utcfromtimestamp(c[r["ruin"]]["t"]).strftime("%d %b")
            ruin = f"ya ({hari})"
        else:
            ruin = "tidak"
        print(
            f"{label:>20}{r['ekuitas']:>10.2f}{ret:>8.1f}%{r['dd']:>7.1f}%"
            f"{r['paksa']:>7}{r['siklus']:>7}{ruin:>9}"
        )


if __name__ == "__main__":
    main()
