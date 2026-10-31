#!/usr/bin/env python3
"""Catat koreksi deal secara append-only (baris asli tidak diubah).

Contoh:
    tools/koreksi_deal.py --ticket 123 --field net --new 8.50 \
        --reason "statement MT5: profit+swap+komisi" --source admin

Koreksi dibaca oleh jurnal, tracker, dan rekonsiliasi. Baris lama tetap ada untuk audit.
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core" / "src"))

from warroom_core.deal_koreksi import (  # noqa: E402
    KOLOM,
    KOREKSI_DEFAULT,
    baca_koreksi,
)
from warroom_core.forwardtest import DEALS_DEFAULT, baca_csv  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Koreksi deal append-only")
    p.add_argument("--ticket", required=True, help="ticket deal di deals.csv")
    p.add_argument("--field", required=True, help="kolom yang dikoreksi, mis. net")
    p.add_argument("--new", required=True, help="nilai baru")
    p.add_argument("--reason", required=True, help="alasan koreksi (wajib)")
    p.add_argument("--source", default="admin", help="sumber koreksi (admin/statement)")
    p.add_argument("--deals", type=Path, default=DEALS_DEFAULT)
    p.add_argument("--koreksi", type=Path, default=KOREKSI_DEFAULT)
    args = p.parse_args(argv)

    deals, ada = baca_csv(args.deals)
    if not ada:
        print(f"deals tidak ada: {args.deals}", file=sys.stderr)
        return 2
    baris = next((d for d in deals if str(d.get("ticket") or "").strip() == args.ticket), None)
    if baris is None:
        print(f"ticket {args.ticket} tidak ditemukan di {args.deals}", file=sys.stderr)
        return 2
    if args.field not in baris:
        print(
            f"field {args.field!r} tidak ada. Kolom: {', '.join(baris.keys())}",
            file=sys.stderr,
        )
        return 2
    lama = baris.get(args.field, "")
    if str(lama) == args.new:
        print(f"tidak ada perubahan: {args.field} sudah {lama!r}")
        return 0

    args.koreksi.parent.mkdir(parents=True, exist_ok=True)
    baru = not args.koreksi.exists()
    with args.koreksi.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=KOLOM)
        if baru:
            w.writeheader()
        w.writerow(
            {
                "ts": datetime.now(UTC).isoformat(timespec="seconds"),
                "ticket": args.ticket,
                "field": args.field,
                "old": lama,
                "new": args.new,
                "reason": args.reason,
                "source": args.source,
            }
        )
    print(
        f"koreksi dicatat: ticket={args.ticket} {args.field} {lama!r} -> {args.new!r} "
        f"({len(baca_koreksi(args.koreksi))} total baris)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
