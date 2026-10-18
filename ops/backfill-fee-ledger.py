#!/usr/bin/env python3
"""Backfill fee_usd untuk baris ledger crypto yang ditutup sebelum 16 Okt 2026.

Kenapa skrip ini ada
--------------------
Commit e5f6fd5 (15 Okt 22:08 UTC) mulai menulis `cost_bps` + `fee_usd` ke baris
ledger saat posisi ditutup. 12 baris sebelum itu hanya menyimpan r/status/
closed_at — tanpa ukuran posisi, sehingga fee TIDAK bisa dihitung ulang dari
ledger saja (butuh size_usd x cost_bps).

Sumber angka
------------
Event `trade.opened` di tabel `events` Postgres menyimpan payload posisi penuh
(signal_id, size_usd, cost_bps) untuk SETIAP trade, termasuk yang lama. Fee
dihitung dengan rumus yang sama persis seperti produksi:

    fee_usd = round(size_usd * cost_bps / 10_000, 6)

Rumus itu divalidasi ulang terhadap 12 baris yang fee-nya sudah tercatat oleh
kode: 12/12 cocok persis sampai 6 desimal. Jadi ini rekonstruksi angka nyata,
bukan estimasi.

Properti skrip
--------------
- Idempoten: baris yang sudah punya fee_usd tidak disentuh.
- Hanya MENAMBAH field cost_bps + fee_usd; field lain tidak diubah.
- Menulis field `fee_sumber` agar asal angkanya bisa diaudit di kemudian hari.
- Berhenti bila ada baris yang datanya tidak ditemukan (tidak mengarang nol).
- Tulis atomik (tmp + os.replace) supaya ledger tidak pernah separuh.

Pakai:
    python3 ops/backfill-fee-ledger.py [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

STATE = Path("/home/admin/live-trading/state/crypto_equity.jsonl")
SUMBER = "trade.opened (events.payload_json)"


def ambil_opened() -> dict[str, dict]:
    """Baca semua event trade.opened dari Postgres lewat psql (baca-saja)."""
    hasil = subprocess.run(
        [
            "sudo", "-n", "-u", "postgres", "psql", "-d", "warroom", "-tAc",
            "select payload_json::text from events where type='trade.opened'",
        ],
        capture_output=True, text=True, check=False, timeout=120,
    )
    if hasil.returncode != 0:
        sys.exit(f"GAGAL membaca events: {hasil.stderr.strip()[:300]}")
    peta: dict[str, dict] = {}
    for baris in hasil.stdout.splitlines():
        baris = baris.strip()
        if not baris:
            continue
        try:
            d = json.loads(baris)
        except json.JSONDecodeError:
            continue
        sid = d.get("signal_id")
        if sid:
            peta[sid] = d
    return peta


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    baris = [json.loads(x) for x in STATE.read_text(encoding="utf-8").splitlines() if x.strip()]
    lama = [b for b in baris if b.get("r") is not None and b.get("fee_usd") is None]
    if not lama:
        print("tidak ada baris tanpa fee — tidak ada yang dikerjakan")
        return 0

    opened = ambil_opened()
    diisi, tanpa_data = 0, []
    total = 0.0
    for b in baris:
        if b.get("r") is None or b.get("fee_usd") is not None:
            continue
        o = opened.get(b.get("signal_id"))
        size, bps = (o or {}).get("size_usd"), (o or {}).get("cost_bps")
        if size is None or bps is None:
            tanpa_data.append(b.get("signal_id"))
            continue
        fee = round(float(size) * float(bps) / 10_000.0, 6)
        b["cost_bps"] = float(bps)
        b["fee_sumber"] = SUMBER
        b["fee_usd"] = fee
        diisi += 1
        total += fee
        print(
            f"  {b['signal_id']} {b['pair']:10s} size=${float(size):7.2f} "
            f"bps={float(bps):6.2f} -> fee=${fee:.6f}"
        )

    if tanpa_data:
        sys.exit(f"BATAL: {len(tanpa_data)} baris tanpa sumber data: {tanpa_data}")

    print(f"\n{diisi} baris diisi, total fee ${total:.6f}")
    if args.dry_run:
        print("--dry-run: tidak ada yang ditulis")
        return 0

    fd, tmp = tempfile.mkstemp(dir=str(STATE.parent), prefix=".crypto_equity.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for b in baris:
                f.write(json.dumps(b, ensure_ascii=False) + "\n")
        os.replace(tmp, STATE)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    print(f"ditulis: {STATE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
