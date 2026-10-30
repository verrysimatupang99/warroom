"""Koreksi deal append-only: perubahan dicatat, baris asli tidak pernah diubah.

Latar: `deals.csv` adalah bukti eksekusi. Kalau angkanya salah (mis. BE padahal SL),
mengedit baris asli menghapus jejak dan membuat rekonsiliasi tidak bisa diaudit.
Koreksi ditulis ke berkas terpisah; pembaca menerapkan koreksi terbaru per
(ticket, field), sambil menyimpan daftar koreksi di baris hasil.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

KOREKSI_DEFAULT = Path("/var/lib/warroom/deal_corrections.csv")
KOLOM = ["ts", "ticket", "field", "old", "new", "reason", "source"]


def baca_koreksi(path: Path = KOREKSI_DEFAULT) -> list[dict[str, str]]:
    if not path.exists():
        return []
    try:
        with path.open(newline="", encoding="utf-8", errors="replace") as f:
            return [dict(r) for r in csv.DictReader(f)]
    except OSError:
        return []


def terapkan(
    rows: list[dict[str, Any]], koreksi: list[dict[str, str]]
) -> list[dict[str, Any]]:
    """Terapkan koreksi terbaru per (ticket, field). Baris asli tidak diubah."""
    if not koreksi:
        return rows
    terakhir: dict[tuple[str, str], dict[str, str]] = {}
    for k in koreksi:
        ticket = str(k.get("ticket") or "").strip()
        field = str(k.get("field") or "").strip()
        if ticket and field:
            terakhir[(ticket, field)] = k
    if not terakhir:
        return rows

    hasil = []
    for row in rows:
        ticket = str(row.get("ticket") or "").strip()
        salinan = dict(row)
        jejak = []
        for (t, field), k in terakhir.items():
            if t != ticket or field not in salinan:
                continue
            lama = salinan[field]
            baru = k.get("new", "")
            if str(lama) == str(baru):
                continue
            salinan[field] = baru
            jejak.append(
                {
                    "field": field,
                    "old": lama,
                    "new": baru,
                    "reason": k.get("reason", ""),
                    "ts": k.get("ts", ""),
                    "source": k.get("source", ""),
                }
            )
        if jejak:
            salinan["_koreksi"] = jejak
        hasil.append(salinan)
    return hasil
