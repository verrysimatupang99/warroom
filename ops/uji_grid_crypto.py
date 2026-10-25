#!/usr/bin/env python3
"""Uji grid + averaging pada SPOT CRYPTO (bukan XAUUSD).

Bedanya dengan uji gold: di spot tidak ada margin call — yang membatasi adalah
modal. Kalau uang habis untuk menambah level, grid berhenti. Itu yang disimulasikan.

Pemakaian: .venv/bin/python ops/uji_grid_crypto.py [interval] [limit]
"""

from __future__ import annotations

import json
import sys
import urllib.request

NODE = "http://100.126.10.74:8790"
KOIN = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "LINKUSDT"]
MODAL = 500.0
MAKS_LEVEL = 8
STEP_ATR = 0.5
TP_ATR = 0.5
PER_LEVEL = MODAL / MAKS_LEVEL
FEE = 0.001  # 0,1% per sisi (khas spot crypto)


def ambil(sym: str, interval: str, limit: int) -> list[dict]:
    url = f"{NODE}/crypto/klines?symbol={sym}&interval={interval}&limit={limit}"
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode())["candles"]


def atr(c: list[dict], p: int = 14) -> list[float]:
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


def jalankan(c: list[dict], a: list[float], stop_pct: float | None) -> dict:
    kas = MODAL
    posisi: list[dict] = []
    puncak = MODAL
    dd = 0.0
    paksa = 0

    for i in range(15, len(c)):
        atr_i = a[i]
        if atr_i <= 0:
            continue
        step = atr_i * STEP_ATR
        hi, close = c[i]["h"], c[i]["c"]

        # TP per posisi: kembalikan pokok + profit, potong fee jual
        sisa = []
        for p in posisi:
            if hi >= p["tp"]:
                kas += p["qty"] * p["tp"] * (1 - FEE)
            else:
                sisa.append(p)
        posisi = sisa

        # tambah level
        if posisi and len(posisi) < MAKS_LEVEL and close <= posisi[-1]["entry"] - step:
            if kas >= PER_LEVEL:
                qty = PER_LEVEL * (1 - FEE) / close
                posisi.append({"entry": close, "qty": qty, "tp": close + step * (TP_ATR / STEP_ATR)})
                kas -= PER_LEVEL

        # buka posisi pertama
        if not posisi and kas >= PER_LEVEL:
            qty = PER_LEVEL * (1 - FEE) / close
            posisi.append({"entry": close, "qty": qty, "tp": close + step * (TP_ATR / STEP_ATR)})
            kas -= PER_LEVEL

        nilai = sum(p["qty"] * close for p in posisi)
        ekuitas = kas + nilai
        puncak = max(puncak, ekuitas)
        if puncak > 0:
            dd = max(dd, 1 - ekuitas / puncak)

        # hard stop: jual semua bila floating loss melewati batas
        floating = nilai - sum(p["qty"] * p["entry"] for p in posisi)
        if stop_pct is not None and floating < -MODAL * stop_pct / 100:
            kas += nilai
            posisi = []
            paksa += 1

    akhir = kas + sum(p["qty"] * c[-1]["c"] for p in posisi)
    return {"ekuitas": akhir, "dd": dd * 100, "paksa": paksa, "terbuka": len(posisi)}


def main() -> None:
    interval = sys.argv[1] if len(sys.argv) > 1 else "1h"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 2000
    print(f"interval {interval} | limit {limit} | modal ${MODAL:.0f} | level maks {MAKS_LEVEL}")
    print(f"\n{'koin':>10}{'candle':>8}{'tanpa stop':>12}{'DD':>7}{'stop 10%':>11}{'DD':>7}{'paksa':>7}")
    for sym in KOIN:
        try:
            c = ambil(sym, interval, limit)
        except Exception as exc:
            print(f"{sym:>10}  gagal: {exc}")
            continue
        a = atr(c)
        r1 = jalankan(c, a, None)
        r2 = jalankan(c, a, 10.0)
        print(
            f"{sym:>10}{len(c):>8}{r1['ekuitas'] - MODAL:>+12.0f}{r1['dd']:>6.0f}%"
            f"{r2['ekuitas'] - MODAL:>+11.0f}{r2['dd']:>6.0f}%{r2['paksa']:>7}"
        )


if __name__ == "__main__":
    main()
