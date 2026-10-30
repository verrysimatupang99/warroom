#!/usr/bin/env python3
"""Cetak status DoD forward test (20 trade tertutup / 30 hari).

Membaca apa adanya dari `deals.csv` dan `fills.csv`. Tidak menghitung dari telemetri
dan tidak menebak: berkas kosong berarti nol trade, bukan "EA tidak trading".

Contoh:
    tools/forwardtest_status.py
    tools/forwardtest_status.py --json
    tools/forwardtest_status.py --mulai 2026-10-30 --hari-ini 2026-11-05
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages" / "core" / "src"))

from warroom_core.deal_koreksi import KOREKSI_DEFAULT  # noqa: E402
from warroom_core.forwardtest import (  # noqa: E402
    DEALS_DEFAULT,
    FILLS_DEFAULT,
    JENDELA_HARI,
    MULAI_DEFAULT,
    TARGET_TRADE,
    ringkas,
    teks,
)


def _tanggal(teks_tanggal: str) -> date:
    try:
        return date.fromisoformat(teks_tanggal)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"tanggal harus YYYY-MM-DD: {teks_tanggal}") from exc


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Status forward test War Room (baca-saja)")
    p.add_argument("--deals", type=Path, default=DEALS_DEFAULT, help="path deals.csv")
    p.add_argument("--fills", type=Path, default=FILLS_DEFAULT, help="path fills.csv")
    p.add_argument("--koreksi", type=Path, default=KOREKSI_DEFAULT, help="path koreksi deal")
    p.add_argument("--mulai", type=_tanggal, default=MULAI_DEFAULT, help="tanggal mulai (YYYY-MM-DD)")
    p.add_argument("--hari-ini", type=_tanggal, default=None, help="tanggal acuan (uji/replay)")
    p.add_argument("--target", type=int, default=TARGET_TRADE, help="target trade tertutup")
    p.add_argument("--jendela", type=int, default=JENDELA_HARI, help="jendela hari")
    p.add_argument("--json", action="store_true", help="keluarkan JSON, bukan teks")
    args = p.parse_args(argv)

    hasil = ringkas(
        deals_path=args.deals,
        fills_path=args.fills,
        koreksi_path=args.koreksi,
        mulai=args.mulai,
        hari_ini=args.hari_ini,
        target=args.target,
        jendela_hari=args.jendela,
    )
    if args.json:
        print(json.dumps(hasil, indent=2, ensure_ascii=False))
    else:
        print(teks(hasil))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
