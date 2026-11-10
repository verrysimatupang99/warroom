#!/usr/bin/env python3
"""CLI backtest strategy config atas data historis crypto.

Contoh:
    python ops/backtest-strategy.py --config strategi/breakout_crypto.yaml
    python ops/backtest-strategy.py --config strategi/breakout_crypto.yaml --simbol ETHUSDT
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages" / "core" / "src"))

from warroom_core.strategi_config import baca_candles, jalankan_backtest, muat_config  # noqa: E402

HIST_DIR = Path("/home/admin/warroom/data/hist")


def _format_hasil(r) -> str:
    pf = "inf" if r.profit_factor == float("inf") else f"{r.profit_factor:.2f}"
    return (
        f"=== {r.simbol} ===\n"
        f"  candle: {r.total_candle} | trade: {r.total_trade} "
        f"(W {r.menang} / L {r.rugi})\n"
        f"  winrate: {r.winrate_pct}%\n"
        f"  profit factor: {pf}\n"
        f"  total R: {r.total_r} | expectansi: {r.expectansi_r}R/trade\n"
        f"  max drawdown: {r.max_drawdown_r}R\n"
        f"  rata menang: +{r.rata_r_menang}R | rata rugi: {r.rata_r_rugi}R"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, help="path config strategy YAML")
    ap.add_argument("--simbol", default="", help="override simbol (koma) — default pakai config")
    args = ap.parse_args()

    cfg = muat_config(Path(args.config))
    print(f"Strategy: {cfg.nama} [{cfg.id}] — {cfg.market} {cfg.waktu}")
    simbol = [s.strip() for s in args.simbol.split(",") if s.strip()] or cfg.simbol

    for s in simbol:
        csv_path = HIST_DIR / f"{s}_{cfg.waktu}.csv"
        candles = baca_candles(csv_path)
        if not candles:
            print(f"  {s}: TIDAK ADA DATA ({csv_path})")
            continue
        hasil = jalankan_backtest(cfg, s, candles)
        print()
        print(_format_hasil(hasil))
        if hasil.trades:
            t = hasil.trades[0]
            print(f"  contoh trade: {t.arah} @{t.entry:.2f} SL {t.sl:.2f} TP {t.tp:.2f} "
                  f"-> {t.alasan_exit} {t.hasil_r:+.2f}R")
    return 0


if __name__ == "__main__":
    sys.exit(main())
