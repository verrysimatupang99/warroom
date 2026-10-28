"""Kalender ekonomi makro.

Sumber: feed publik ForexFactory (nfs.faireconomy.media), tanpa kredensial.
Diambil dengan cache 30 menit supaya tidak membanjiri sumber dan tidak
memperlambat halaman. Kalau feed mati, endpoint bilang terus terang, bukan
menampilkan tanggal dari ingatan.
"""

from __future__ import annotations

import time
from typing import Any

import httpx
from fastapi import APIRouter, Depends, Query

from warroom_api import auth

router = APIRouter(
    prefix="/api/v1/kalender", tags=["kalender"], dependencies=[Depends(auth.current_user)]
)

SUMBER = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
UA = "Mozilla/5.0 (X11; Linux x86_64) WarRoom/2.0"
CACHE_S = 1800
_cache: dict[str, Any] = {"ts": 0.0, "data": None}
_mata_uang_utama = {"USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD", "CNY"}


async def _ambil() -> list[dict[str, Any]]:
    now = time.time()
    if _cache["data"] is not None and now - _cache["ts"] < CACHE_S:
        return _cache["data"]
    async with httpx.AsyncClient(timeout=12.0, headers={"User-Agent": UA}) as c:
        r = await c.get(SUMBER)
        r.raise_for_status()
        data = r.json()
    if not isinstance(data, list):
        raise ValueError("format feed berubah")
    _cache["data"] = data
    _cache["ts"] = now
    return data


@router.get("/makro")
async def kalender_makro(
    dampak: str = Query("semua", pattern="^(semua|tinggi|utama)$"),
    batas: int = Query(40, ge=1, le=200),
) -> dict[str, Any]:
    """Agenda ekonomi pekan ini.

    dampak=tinggi  : hanya High
    dampak=utama   : High atau Medium untuk mata uang utama
    dampak=semua   : semua kecuali Holiday
    """
    try:
        data = await _ambil()
    except Exception as exc:  # noqa: BLE001
        return {
            "tersedia": False,
            "sumber": SUMBER,
            "pesan": f"Feed kalender tidak bisa diambil: {type(exc).__name__}",
            "agenda": [],
        }

    hasil = []
    for item in data:
        impak = str(item.get("impact") or "")
        if impak.lower() == "holiday":
            continue
        if dampak == "tinggi" and impak.lower() != "high":
            continue
        if dampak == "utama":
            mata = str(item.get("country") or "").upper()
            if impak.lower() not in {"high", "medium"} or mata not in _mata_uang_utama:
                continue
        hasil.append(
            {
                "judul": item.get("title"),
                "mata_uang": item.get("country"),
                "waktu": item.get("date"),
                "dampak": impak,
                "perkiraan": item.get("forecast") or None,
                "sebelumnya": item.get("previous") or None,
            }
        )

    return {
        "tersedia": True,
        "sumber": SUMBER,
        "diambil": int(_cache["ts"]),
        "jumlah": len(hasil),
        "agenda": hasil[:batas],
    }
