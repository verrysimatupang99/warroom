#!/usr/bin/env python3
"""Rekonsiliasi statement MT5 dengan `deals.csv` (US2.1).

Membandingkan deal `out` di statement broker dengan yang dilaporkan EA, per tiket deal.
Net = profit + swap + commission. Selisih di atas toleransi (default $0,01) → exit 1.

Contoh:
    tools/rekonsiliasi_forwardtest.py --statement statement.htm
    tools/rekonsiliasi_forwardtest.py --statement statement.htm --sejak 2026-10-30
    tools/rekonsiliasi_forwardtest.py --statement statement.htm --json

Exit: 0 cocok, 1 ada selisih, 2 statement tidak terbaca / tidak ada deal `out`.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core" / "src"))

from warroom_core.deal_koreksi import KOREKSI_DEFAULT, baca_koreksi, terapkan  # noqa: E402
from warroom_core.forwardtest import DEALS_DEFAULT, baca_csv  # noqa: E402
from warroom_core.rekonsiliasi_deal import (  # noqa: E402
    TOLERANSI_DEFAULT,
    baca_statement,
    bandingkan,
    teks,
)


def _tanggal(nilai: str) -> date:
    try:
        return date.fromisoformat(nilai)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"tanggal harus YYYY-MM-DD: {nilai}") from exc


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Rekonsiliasi statement MT5 vs deals.csv")
    p.add_argument("--statement", type=Path, required=True, help="statement/report MT5 (.htm)")
    p.add_argument("--deals", type=Path, default=DEALS_DEFAULT, help="path deals.csv")
    p.add_argument("--koreksi", type=Path, default=KOREKSI_DEFAULT, help="path koreksi deal")
    p.add_argument("--sejak", type=_tanggal, default=None, help="batas awal (YYYY-MM-DD)")
    p.add_argument("--sampai", type=_tanggal, default=None, help="batas akhir (YYYY-MM-DD)")
    p.add_argument(
        "--toleransi",
        type=float,
        default=TOLERANSI_DEFAULT,
        help=f"selisih net yang masih dianggap cocok (USD, default {TOLERANSI_DEFAULT})",
    )
    p.add_argument("--json", action="store_true", help="keluarkan JSON, bukan teks")
    args = p.parse_args(argv)

    if not args.statement.exists():
        print(f"statement tidak ada: {args.statement}", file=sys.stderr)
        return 2

    statement = baca_statement(args.statement)
    if not statement:
        print(
            "tidak ada deal 'out' terbaca dari statement. Periksa format/encoding "
            "(laporan MT5 biasanya UTF-16LE) dan pastikan tabelnya memuat kolom "
            "Time/Deal/Symbol/Type/Direction/Volume/Price/Commission/Swap/Profit.",
            file=sys.stderr,
        )
        return 2

    deals, deals_ada = baca_csv(args.deals)
    deals = terapkan(deals, baca_koreksi(args.koreksi))
    if not deals_ada:
        print(f"catatan: {args.deals} belum ada — semua deal statement akan dianggap hilang.",
              file=sys.stderr)

    hasil = bandingkan(
        statement,
        deals,
        toleransi=args.toleransi,
        sejak=args.sejak,
        sampai=args.sampai,
    )
    hasil["deals_ada"] = deals_ada
    hasil["deals_path"] = str(args.deals)
    hasil["statement_path"] = str(args.statement)

    if args.json:
        print(json.dumps(hasil, indent=2, ensure_ascii=False))
    else:
        print(teks(hasil))
    return 0 if hasil["status"] == "cocok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
