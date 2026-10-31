#!/usr/bin/env python3
"""Grid + filter rezim: hanya jalankan grid saat pasar TIDAK sedang tren.

Hipotesis: kekalahan grid terjadi di tren kuat (SOL +123% B&H vs grid +62%).
Kalau grid dipause saat tren terdeteksi, drawdown dan hasil bisa membaik.

Deteksi tren: |EMA cepat - EMA lambat| / ATR. Makin besar, makin kuat trennya.

Pemakaian: .venv/bin/python ops/uji_grid_rezim.py [interval] [limit]
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


def ambil(sym: str, interval: str, limit: int) -> list[dict]:
    url = f"{NODE}/crypto/klines?symbol={sym}&interval={interval}&limit={limit}"
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode())["candles"]


def ema(vals: list[float], p: int) -> list[float]:
    out = [0.0] * len(vals)
    if len(vals) < p:
        return out
    k = 2 / (p + 1)
    out[p - 1] = sum(vals[:p]) / p
    for i in range(p, len(vals)):
        out[i] = vals[i] * k + out[i - 1] * (1 - k)
    return out


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


def jalankan(c, a, e50, e200, ambang: float | None) -> dict:
    kas, posisi = MODAL, []
    puncak, dd = MODAL, 0.0

    for i in range(200, len(c)):
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

        # filter rezim: hitung kekuatan tren
        tren = abs(e50[i] - e200[i]) / a[i] if e200[i] > 0 else 0.0
        boleh = ambang is None or tren <= ambang

        if boleh:
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
        ekuitas = kas + nilai
        puncak = max(puncak, ekuitas)
        if puncak > 0:
            dd = max(dd, 1 - ekuitas / puncak)

    akhir = kas + sum(p["qty"] * c[-1]["c"] for p in posisi)
    return {"ekuitas": akhir, "dd": dd * 100}


def main() -> None:
    interval = sys.argv[1] if len(sys.argv) > 1 else "1d"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 2000
    ambang_list: list[float | None] = [None, 4.0, 2.0, 1.0]
    print(f"interval {interval} | {limit} candle | filter: |EMA50-EMA200|/ATR")
    print(f"\n{'koin':>10}" + "".join(f"{('tanpa' if t is None else f'<={t}'):>13}" for t in ambang_list))
    total: dict[str, float] = {str(t): 0.0 for t in ambang_list}
    for sym in KOIN:
        try:
            c = ambil(sym, interval, limit)
        except Exception as exc:
            print(f"{sym:>10}  gagal: {exc}")
            continue
        a = atr(c)
        closes = [x["c"] for x in c]
        e50, e200 = ema(closes, 50), ema(closes, 200)
        baris = f"{sym:>10}"
        for t in ambang_list:
            r = jalankan(c, a, e50, e200, t)
            ret = (r["ekuitas"] / MODAL - 1) * 100
            total[str(t)] += ret
            baris += f"{ret:>+8.0f}%/{r['dd']:>3.0f}%"
        print(baris)
    print(f"\n{'RATA-RATA':>10}" + "".join(f"{total[str(t)] / len(KOIN):>+8.0f}%     " for t in ambang_list))


if __name__ == "__main__":
    main()
