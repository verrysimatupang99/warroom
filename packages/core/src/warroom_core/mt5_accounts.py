"""Identitas akun MT5 untuk telemetri multi-akun.

Satu terminal MT5 = satu akun. Supaya akun cent HSFX tidak menimpa telemetri Reaper,
snapshot disimpan per akun: akun utama memakai key `ringkas` (kompatibel dengan UI lama),
akun lain memakai `ringkas:<account>`.
"""

from __future__ import annotations

import os

PRIMARY_ACCOUNT = (os.environ.get("WARROOM_MT5_PRIMARY_ACCOUNT") or "416510164").strip()


def snapshot_key(account: str | None) -> str:
    akun = str(account or "").strip()
    if not akun or akun == PRIMARY_ACCOUNT:
        return "ringkas"
    return f"ringkas:{akun}"
