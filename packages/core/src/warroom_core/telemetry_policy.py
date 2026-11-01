"""Kebijakan telemetri yang sudah dipensiunkan.

Keputusan owner 1 Nov 2026: telemetri akun demo `416510164` (EA lama) tidak lagi
diharapkan. Fakta lamanya tetap tersimpan sebagai arsip, tetapi tidak boleh lagi
dihitung sebagai "basi", memicu alert, atau menahan readiness. Sumber pengganti
(akun live) belum terhubung.

Format env `WARROOM_RETIRED_FACTS`: daftar `kind:key` dipisah koma. `key` boleh
mengandung titik dua (mis. `ringkas:452009427`), jadi pemisahan hanya pada titik
dua pertama.
"""

from __future__ import annotations

import os

__all__ = ["RETIRED_DEFAULT", "is_retired", "retired_pairs"]

RETIRED_DEFAULT = "mt5_snapshot:ringkas,mt5_snapshot:ringkas:452009427"


def retired_pairs() -> frozenset[tuple[str, str]]:
    mentah = os.environ.get("WARROOM_RETIRED_FACTS", RETIRED_DEFAULT)
    hasil: set[tuple[str, str]] = set()
    for item in mentah.split(","):
        item = item.strip()
        if not item or ":" not in item:
            continue
        kind, key = item.split(":", 1)
        if kind.strip() and key.strip():
            hasil.add((kind.strip(), key.strip()))
    return frozenset(hasil)


def is_retired(kind: str, key: str) -> bool:
    return (kind, key) in retired_pairs()
