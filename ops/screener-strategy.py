#!/usr/bin/env python3
"""CLI screener: setup strategy live untuk tiap simbol.

Contoh:
    python ops/screener-strategy.py --config strategi/breakout_donchian_crypto.yaml
    python ops/screener-strategy.py --config strategi/x.yaml --simbol BTCUSDT,PEPEUSDT
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages" / "core" / "src"))

from warroom_core.strategi_config import muat_config  # noqa: E402
from warroom_core.strategi_config.provider import provider_untuk  # noqa: E402
from warroom_core.strategi_config.screener import scan_satu  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--simbol", default="", help="override simbol (koma)")
    args = ap.parse_args()

    cfg = muat_config(Path(args.config))
    provider = provider_untuk(cfg.market)
    simbol = [s.strip() for s in args.simbol.split(",") if s.strip()] or cfg.simbol

    print(f"Screener: {cfg.nama} [{cfg.id}] — {cfg.market} {cfg.waktu}")
    print(f"{'SIMBOL':<12} {'ARAH':<7} {'CLOSE':>12}  KONDISI")
    print("-" * 60)
    ada_setup = False
    for s in simbol:
        try:
            setup = scan_satu(cfg, s, provider)
        except Exception as e:  # noqa: BLE001
            print(f"{s:<12} {'GAGAL':<7} -  {e}")
            continue
        if setup is None:
            continue
        if setup.arah != "-":
            ada_setup = True
            kondisi = " & ".join(setup.alasan) if setup.alasan else "-"
            print(f"{setup.simbol:<12} {setup.arah.upper():<7} {setup.close:>12.4g}  {kondisi}")
        else:
            print(f"{setup.simbol:<12} {'-':<7} {setup.close:>12.4g}  (tidak match)")
    if not ada_setup:
        print("\nTidak ada setup aktif saat ini.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
