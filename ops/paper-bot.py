#!/usr/bin/env python3
"""CLI paper bot: jalankan satu siklus eksekusi kertas untuk config strategy.

Contoh:
    python ops/paper-bot.py --config strategi/breakout_donchian_crypto.yaml
State & ledger disimpan di /var/lib/warroom/paper-config/.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages" / "core" / "src"))

from warroom_core.strategi_config import muat_config  # noqa: E402
from warroom_core.strategi_config.paper_bot import jalankan_paper_bot  # noqa: E402
from warroom_core.strategi_config.provider import provider_untuk  # noqa: E402

STATE_DIR = Path("/var/lib/warroom/paper-config")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--modal", type=float, default=100.0, help="modal per trade (USD)")
    ap.add_argument("--maks-posisi", type=int, default=5)
    args = ap.parse_args()

    cfg = muat_config(Path(args.config))
    provider = provider_untuk(cfg.market)
    STATE_DIR.mkdir(parents=True, exist_ok=True)

    ringkasan = jalankan_paper_bot(cfg, provider, STATE_DIR, args.modal, args.maks_posisi)
    print(f"Paper bot [{ringkasan['config']}] — posisi aktif: {ringkasan['posisi_aktif']}")
    if ringkasan["dibuka"]:
        print("  DIBUKA:")
        for b in ringkasan["dibuka"]:
            print(f"    + {b}")
    if ringkasan["ditutup"]:
        print("  DITUTUP:")
        for t in ringkasan["ditutup"]:
            print(f"    - {t['simbol']} {t['arah']} {t['alasan_exit']} "
                  f"{t['hasil_r']:+.2f}R (${t['pnl_usd']:+.2f})")
    if not ringkasan["dibuka"] and not ringkasan["ditutup"]:
        print("  (tidak ada perubahan posisi)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
