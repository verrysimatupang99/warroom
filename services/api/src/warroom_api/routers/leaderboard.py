"""Router leaderboard — perbandingan performa strategi lintas pasar.

Angka hanya dari fakta `pasar_akurasi` / `idx_akurasi` (mesin pasar.py); aturan
karantina/beku/biaya dipakai dari `warroom_core.verdict` supaya papan dan verdict
tidak bisa berbeda pendapat. Pasar yang gagal tetap tampil sebagai baris status.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from warroom_core.db import User, session_scope

from warroom_api import auth

router = APIRouter()


@router.get("/api/v1/leaderboard/strategi")
def leaderboard_strategi(user: Annotated[User, Depends(auth.current_user)]) -> dict[str, Any]:
    """Peringkat strategi: ekuitas (R/USD), WR, expectancy R, max DD, biaya, status.

    Fungsi hitung ada di domain (`warroom_core.leaderboard`) — router hanya
    menyambungkan sesi, seperti pola `/verdict`.
    """
    from warroom_core.leaderboard import strategy_leaderboard

    with session_scope() as s:
        return strategy_leaderboard(s)
