"""Riset Gold Reaper: backtest Golden Pullback di data emas dengan biaya Exness realistis.

Skrip ini menjawab satu pertanyaan saja: **apakah strategi ini punya edge setelah
biaya?** Semua keputusan lain (walk-forward split, sensitivitas, Monte Carlo) hanya
ada untuk memastikan jawabannya tidak lahir dari kebetulan.

Jalankan:
    .venv/bin/python -m live_trading.riset_reaper --csv data/hist/PAXGUSDT_1h.csv

Biaya acuan (Exness Standard Cent, dicek 2026-11-02):
- spread emas "from" 0,20 USD, mengambang sampai 0,50+ saat berita
- kontrak standard cent: 1 lot = 10 oz, min 0,01 lot = 0,1 oz
- tanpa komisi (spread-only)
Kita konservatif: pakai 0,35 USD/oz (= 0,35 per 1 oz) sebagai asumsi dasar dan
0,50 USD untuk skenario buruk.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import statistics
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from live_trading.signals.golden_pullback import GoldenPullbackConfig
from live_trading.signals.interpretasi import (
    InterpretasiConfig,
    baca_konteks,
    ema,
    sinyal_dari_bar,
)

SPREAD_USD_PER_OZ = 0.35
SPREAD_BURUK_USD_PER_OZ = 0.50


# --------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------
def muat_ohlc(path: Path) -> dict[str, list[Any]]:
    """Baca CSV (timestamp_ms, open, high, low, close, volume) urut waktu."""
    waktu: list[int] = []
    o: list[float] = []
    h: list[float] = []
    lo: list[float] = []
    c: list[float] = []
    with path.open(newline="") as f:
        rdr = csv.DictReader(f)
        for r in rdr:
            ts = int(r["timestamp"])
            if waktu and ts <= waktu[-1]:
                continue  # buang duplikat/urutan salah, jangan menebak
            waktu.append(ts)
            o.append(float(r["open"]))
            h.append(float(r["high"]))
            lo.append(float(r["low"]))
            c.append(float(r["close"]))
    return {"waktu": waktu, "open": o, "high": h, "low": lo, "close": c}


# --------------------------------------------------------------------------
# Simulasi satu trade
# --------------------------------------------------------------------------
def simulasikan_trade(
    *,
    arah: str,
    entry: float,
    stop: float,
    target: float,
    high: list[float],
    low: list[float],
    mulai: int,
    batas: int,
    spread: float,
) -> dict[str, Any]:
    """Telusuri candle ke depan sampai SL/TP kena atau jendela habis.

    Model biaya yang dipakai: candle dianggap berisi harga **bid**. Kita beli di
    ask (= bid + spread) sehingga entry efektif lebih buruk sebesar satu spread
    penuh untuk long, dan lebih buruk untuk short dengan cara yang sama. Karena
    stop & target didefinisikan di harga bid, kita hanya menggeser entry:

        entry_efektif = entry + spread   (long)
        entry_efektif = entry - spread   (short)

    Ini membuat jumlah R yang dihasilkan lebih kecil dan jarak ke stop lebih
    sempit — keduanya merugikan strategi, sesuai prinsip skrip ini.

    Aturan pesimistis lain:
    - bila SL dan TP tersentuh di candle yang sama, anggap **SL** yang kena.
    - tidak ada trailing stop, tidak ada partial take-profit.
    """
    if arah == "long":
        entry_efektif = entry + spread
    else:
        entry_efektif = entry - spread

    risiko = abs(entry_efektif - stop)
    if risiko <= 0:
        return {"hasil": "tidak_valid", "r": 0.0, "exit": entry, "index": mulai}

    # `batas` eksklusif: candle indeks `batas` milik blok berikutnya (walk-forward).
    for j in range(mulai + 1, min(batas, len(high))):
        if arah == "long":
            kena_sl = low[j] <= stop
            kena_tp = high[j] >= target
        else:
            kena_sl = high[j] >= stop
            kena_tp = low[j] <= target

        if kena_sl:
            # Menang saat ragu: kalau SL & TP kena di candle yang sama, ambil yang rugi.
            return {"hasil": "sl", "r": -1.0, "exit": stop, "index": j}
        if kena_tp:
            rr = abs(target - entry_efektif) / risiko
            return {"hasil": "tp", "r": rr, "exit": target, "index": j}
    return {"hasil": "terbuka", "r": 0.0, "exit": entry, "index": batas}


def biaya_r(entry: float, stop: float, spread: float) -> float:
    """Spread dalam satuan R — inti dari pertanyaan apakah edge bertahan."""
    risiko = abs(entry - stop)
    if risiko <= 0:
        return math.inf
    return spread / risiko


# --------------------------------------------------------------------------
# Backtest penuh
# --------------------------------------------------------------------------
def jalankan(
    data: dict[str, list[Any]],
    *,
    ci: InterpretasiConfig,
    cg: GoldenPullbackConfig,
    spread: float,
    mulai: int = 0,
    selesai: int | None = None,
) -> list[dict[str, Any]]:
    close = data["close"]
    high = data["high"]
    low = data["low"]
    open_ = data["open"]
    waktu = data["waktu"]
    n = len(close)
    akhir = n if selesai is None else min(selesai, n)
    mulai_efektif = max(mulai, ci.warmup)

    e = ema(close, ci.trend_ema)
    trades: list[dict[str, Any]] = []
    i = mulai_efektif
    while i < akhir - 1:
        bar = {"close": close[i], "open": open_[i], "high": high[i], "low": low[i]}
        ctx = baca_konteks(
            bar,
            high=high,
            low=low,
            close=close,
            open_=open_,
            ema_garis=e,
            i=i,
            cfg=ci,
        )
        setup = sinyal_dari_bar(ctx, cfg_interpretasi=ci, cfg_golden=cg)
        if setup is None:
            i += 1
            continue
        entry = float(setup["entry"])
        stop = float(setup["stop"])
        target = float(setup["target"])
        hasil = simulasikan_trade(
            arah=str(setup["direction"]),
            entry=entry,
            stop=stop,
            target=target,
            high=high,
            low=low,
            mulai=i,
            batas=akhir,
            spread=spread,
        )
        # Jangan buka posisi baru selama posisi sebelumnya masih berjalan.
        lanjut = hasil["index"] if hasil["hasil"] in {"tp", "sl"} else i + 1
        if hasil["hasil"] in {"tp", "sl"}:
            biaya = biaya_r(entry, stop, spread)
            trades.append(
                {
                    "time": datetime.fromtimestamp(waktu[i] / 1000, UTC).isoformat(),
                    "index": i,
                    "arah": setup["direction"],
                    "entry": entry,
                    "stop": stop,
                    "target": target,
                    "risiko_usd": round(abs(entry - stop), 4),
                    "hasil": hasil["hasil"],
                    "r_kotor": round(float(hasil["r"]), 4),
                    "biaya_r": round(biaya, 4),
                    "r_bersih": round(float(hasil["r"]) - biaya, 4),
                }
            )
        i = lanjut
    return trades


# --------------------------------------------------------------------------
# Metrik
# --------------------------------------------------------------------------
def metrik(trades: list[dict[str, Any]], *, risiko_fraksi: float = 0.01) -> dict[str, Any]:
    """Hitung metrik dengan risiko 1% ekuitas per trade (acuan risiko tetap)."""
    if not trades:
        return {"n": 0}
    rs = [t["r_bersih"] for t in trades]
    menang = [r for r in rs if r > 0]
    kalah = [r for r in rs if r <= 0]
    total = sum(rs)
    gross_win = sum(menang)
    gross_loss = abs(sum(kalah))

    # Kurva ekuitas pada risiko tetap 1% — bukan supersizing, hanya untuk DD.
    ekuitas = 1.0
    puncak = 1.0
    dd = 0.0
    for r in rs:
        ekuitas *= 1 + risiko_fraksi * r
        puncak = max(puncak, ekuitas)
        dd = max(dd, (puncak - ekuitas) / puncak)

    sd = statistics.pstdev(rs) if len(rs) > 1 else 0.0
    t_stat = (statistics.fmean(rs) / (sd / math.sqrt(len(rs)))) if sd > 0 else None

    # Sharpe disederhanakan pada basis per-trade, bukan tahunan.
    sharpe = (statistics.fmean(rs) / sd) if sd > 0 else None

    return {
        "n": len(rs),
        "win_rate": round(len(menang) / len(rs), 4),
        "r_kotor_total": round(sum(t["r_kotor"] for t in trades), 3),
        "biaya_rata_r": round(statistics.fmean(t["biaya_r"] for t in trades), 4),
        "r_bersih_total": round(total, 3),
        "expectancy_r": round(total / len(rs), 4),
        "profit_factor": round(gross_win / gross_loss, 3) if gross_loss > 0 else None,
        "max_dd_pct": round(dd * 100, 2),
        "t_stat": round(t_stat, 2) if t_stat is not None else None,
        "sharpe_per_trade": round(sharpe, 3) if sharpe else None,
    }


def mc_bootstrap(rs: list[float], *, iterasi: int = 2000, seed: int = 42) -> dict[str, Any]:
    """Bootstrap: seberapa yakin kita bahwa expectancy > 0?

    Bukan Monte Carlo "acak urutan trade" (yang tidak mengubah total R), melainkan
    resampling dengan pengembalian — pertanyaan yang benar: bila pasar mengulang
    data ini dengan kebetulan sedikit berbeda, bisakah kita tetap untung?
    """
    if len(rs) < 10:
        return {"catatan": "butuh ≥10 trade"}
    rng = random.Random(seed)
    n = len(rs)
    means = []
    for _ in range(iterasi):
        sampel = [rs[rng.randrange(n)] for _ in range(n)]
        means.append(statistics.fmean(sampel))
    means.sort()
    return {
        "iterasi": iterasi,
        "expectancy_p05": round(means[int(0.05 * iterasi)], 4),
        "expectancy_p50": round(means[int(0.50 * iterasi)], 4),
        "expectancy_p95": round(means[int(0.95 * iterasi)], 4),
        "prob_expectancy_positif": round(sum(1 for m in means if m > 0) / iterasi, 4),
    }


def walk_forward(
    data: dict[str, list[Any]],
    *,
    ci: InterpretasiConfig,
    cg: GoldenPullbackConfig,
    spread: float,
    lipatan: int = 5,
) -> list[dict[str, Any]]:
    """Pecah data kronologis menjadi `lipatan` blok; tiap blok = satu out-of-sample.

    Tidak ada parameter yang dioptimasi di sini — itu disengaja. Mengoptimasi tanpa
    OOS yang benar-benar tersegel adalah cara paling umum menipu diri sendiri.
    """
    n = len(data["close"])
    hasil = []
    for k in range(lipatan):
        a = int(n * k / lipatan)
        b = int(n * (k + 1) / lipatan)
        trades = jalankan(data, ci=ci, cg=cg, spread=spread, mulai=a, selesai=b)
        m = metrik(trades)
        m["blok"] = k + 1
        m["periode"] = (
            datetime.fromtimestamp(data["waktu"][a] / 1000, UTC).date().isoformat()
            + " → "
            + datetime.fromtimestamp(data["waktu"][min(b, n - 1)] / 1000, UTC).date().isoformat()
        )
        hasil.append(m)
    return hasil


def sensitivitas(
    data: dict[str, list[Any]],
    *,
    basis: InterpretasiConfig,
    cg: GoldenPullbackConfig,
    spread: float,
) -> list[dict[str, Any]]:
    """Ubah satu parameter; edge yang asli bertahan, yang kebetulan hancur."""
    hasil = []
    for lb in (30, 40, 50, 60):
        for rr in (1.5, 2.0, 2.5, 3.0):
            ci = InterpretasiConfig(
                lookback=lb, trend_ema=basis.trend_ema, warmup=max(60, lb, basis.trend_ema)
            )
            cfg = GoldenPullbackConfig(
                zone_start=cg.zone_start,
                zone_end=cg.zone_end,
                minimum_rr=rr,
            )
            trades = jalankan(data, ci=ci, cg=cfg, spread=spread)
            m = metrik(trades)
            hasil.append({"lookback": lb, "rr": rr, **m})
    return hasil


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Riset Gold Reaper")
    p.add_argument("--csv", type=Path, required=True)
    p.add_argument("--spread", type=float, default=SPREAD_USD_PER_OZ)
    p.add_argument("--out", type=Path, default=Path("docs/riset-reaper-hasil.json"))
    p.add_argument("--lipatan", type=int, default=5)
    args = p.parse_args(argv)

    data = muat_ohlc(args.csv)
    if len(data["close"]) < 5000:
        print(f"data terlalu pendek: {len(data['close'])} candle", file=sys.stderr)
        return 2

    ci = InterpretasiConfig()
    cg = GoldenPullbackConfig()

    trades = jalankan(data, ci=ci, cg=cg, spread=args.spread)
    penuh = metrik(trades)
    b_all = mc_bootstrap([t["r_bersih"] for t in trades])
    wf = walk_forward(data, ci=ci, cg=cg, spread=args.spread, lipatan=args.lipatan)
    sens = sensitivitas(data, basis=ci, cg=cg, spread=args.spread)
    buruk = metrik(jalankan(data, ci=ci, cg=cg, spread=SPREAD_BURUK_USD_PER_OZ))

    keluaran = {
        "dijalankan": datetime.now(UTC).isoformat(),
        "sumber": str(args.csv),
        "periode": (
            datetime.fromtimestamp(data["waktu"][0] / 1000, UTC).isoformat()
            + " → "
            + datetime.fromtimestamp(data["waktu"][-1] / 1000, UTC).isoformat()
        ),
        "candle": len(data["close"]),
        "asumsi": {
            "spread_usd": args.spread,
            "spread_buruk_usd": SPREAD_BURUK_USD_PER_OZ,
            "risiko_per_trade": 0.01,
            "interpretasi": asdict(ci),
            "golden": asdict(cg),
            "entry_rule": "SL+TP satu candle -> hitung SL (pesimistis)",
            "no_overlap": True,
        },
        "penuh": penuh,
        "monte_carlo": b_all,
        "spread_buruk": buruk,
        "walk_forward": wf,
        "sensitivitas": sens,
        "trades_ringkas": [
            {k: t[k] for k in ("time", "arah", "entry", "stop", "r_bersih", "hasil")} for t in trades[:20]
        ],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(keluaran, indent=2, ensure_ascii=False))

    print(json.dumps({k: keluaran[k] for k in ("periode", "candle", "penuh", "monte_carlo")}, indent=2))
    print("\nWALK-FORWARD:")
    for w in wf:
        print(
            f"  blok {w['blok']} {w['periode']}: "
            f"n={w.get('n')} exp={w.get('expectancy_r')} pf={w.get('profit_factor')}"
        )
    print(f"\nDisimpan: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
