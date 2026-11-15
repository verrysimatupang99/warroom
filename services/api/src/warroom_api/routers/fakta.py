"""Router fakta & area — penulis fakta, baca per-area, sumber data, satu fakta.

Diekstrak dari app.py (P1-2, langkah 5). Refactor murni: path (termasuk rute
dinamis per-AREA_KEYS), status kode, dan auth dependency tidak berubah.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from warroom_core.db import Fact, User, session_scope
from warroom_core.db.session import SASession

from warroom_api import auth
from warroom_api.areas import AREA_KEYS, areas_summary, facts_for_area

router = APIRouter()


class FactBody(BaseModel):
    kind: str
    key: str
    value: Any
    source: str
    observed_at: datetime
    ttl_s: int = Field(ge=0)
    hash: str = ""


class FactsBody(BaseModel):
    facts: list[FactBody]


def _riwayat_kunci(s: SASession, kind: str, key: str, n: int) -> list[dict[str, Any]]:
    """N versi terbaru satu kunci fakta (untuk menarik riwayat di UI)."""
    rows = s.scalars(
        select(Fact).where(Fact.kind == kind, Fact.key == key).order_by(Fact.observed_at.desc()).limit(n)
    ).all()
    now = datetime.now(UTC)
    return [
        {
            "fact_id": f.id,
            "value": f.value_json,
            "source": f.source,
            "observed_at": f.observed_at.isoformat(),
            "ttl_s": f.ttl_s,
            "status": "segar" if (now - f.observed_at).total_seconds() <= f.ttl_s else "basi",
        }
        for f in rows
    ]


# --- penulis fakta (operator) -------------------------------------------------------


@router.post("/api/v1/facts")
def publish_facts(
    body: FactsBody, user: Annotated[User, Depends(auth.require_role("operator"))]
) -> dict[str, Any]:
    saved = 0
    with session_scope() as s:
        for f in body.facts:
            s.add(
                Fact(
                    kind=f.kind,
                    key=f.key,
                    value_json=f.value,
                    source=f.source,
                    observed_at=f.observed_at,
                    ttl_s=f.ttl_s,
                    hash=f.hash,
                )
            )
            saved += 1
    return {"saved": saved, "by": user.username}


# --- baca per-area (P1-T6) ----------------------------------------------------------


@router.get("/api/v1/areas/{area}")
def area_detail(
    area: str,
    user: Annotated[User, Depends(auth.current_user)],
    riwayat: int = Query(0, ge=0, le=50, description="sertakan N versi lama per kunci"),
) -> dict[str, Any]:
    """Fakta satu area lengkap dengan metadata (`fact_id`, sumber, umur, status).

    Area tak dikenal tidak melempar 500 — balasannya menyebut daftar area yang ada.
    """
    with session_scope() as s:
        info = facts_for_area(s, area)
        if not info.get("dikenal", False):
            return info
        if riwayat:
            for f in info["facts"]:
                f["riwayat"] = _riwayat_kunci(s, f["kind"], f["key"], riwayat)
        return info


@router.get("/api/v1/areas")
def areas(user: Annotated[User, Depends(auth.current_user)]) -> dict[str, Any]:
    with session_scope() as s:
        return {"areas": areas_summary(s)}


@router.get("/api/v1/sumber")
def sumber_data(user: Annotated[User, Depends(auth.current_user)]) -> dict[str, Any]:
    """Daftar SUMBER DATA tiap pasar — satu tempat, biar tidak ada tebakan.

    Revisi pemilik 10 Okt: "Crypto OKX" (ganti MEXC total).
    Revisi pemilik 7 Okt: "sumber data: Crypto MEXC; IDX Stock Arjum; Forex TVC;
    Polymarket Dokumentasi PM; Meme: Meteora=Solana, Robinhood=Uniswap". Daftar ini
    dipakai UI (halaman market + Sistem) supaya pembaca tahu angka ini datang dari mana.
    """
    return {
        "sumber": [
            {"pasar": "forex", "label": "Forex & Gold", "sumber": "Exness MT5 (#452009427)",
             "keterangan": "Eksekusi Real Cent XAUUSDc via GOLD_Reaper_Hexa di Instabox (box-2aacb3) + Yahoo Finance."},
            {"pasar": "polymarket", "label": "Polymarket", "sumber": "Poly-Agent + Gamma",
             "keterangan": "Arm D favorit 0,70–0,95 & self-tuning AI Agent 5m BTC/ETH."},
            {"pasar": "idx", "label": "Saham IDX", "sumber": "Stock Arjum + Yahoo",
             "keterangan": "IHSG live + screener, broker summary & akumulasi via idx-edge (stock.arjum.com)."},
            {"pasar": "crypto", "label": "Crypto", "sumber": "OKX",
             "keterangan": (
                 "Harga & depth dari OKX (venue paper). "
                 "Sinyal = SMC multi-timeframe + momentum 40 koin."
             )},
        ],
        "sumber_atom": [
            {"nama": "Exness MT5 (#452009427)", "dipakai": "telemetri & eksekusi live Real Cent XAUUSDc"},
            {"nama": "Poly-Agent + Gamma", "dipakai": "evaluasi 4 arm & settlement 5m Polymarket"},
            {"nama": "Stock Arjum (idx-edge)", "dipakai": "IDX screener, broker flow & akumulasi"},
            {"nama": "OKX", "dipakai": "harga & eksekusi paper crypto"},
            {"nama": "Yahoo Finance", "dipakai": "candle cadangan XAUUSD, DXY & IHSG (^JKSE)"},
        ],
    }


@router.get("/api/v1/facts/{kind}/{key}")
def fact_satu(
    kind: str,
    key: str,
    user: Annotated[User, Depends(auth.current_user)],
    riwayat: int = Query(1, ge=1, le=50, description="jumlah nilai terbaru"),
) -> dict[str, Any]:
    with session_scope() as s:
        rows = s.scalars(
            select(Fact)
            .where(Fact.kind == kind, Fact.key == key)
            .order_by(Fact.observed_at.desc())
            .limit(riwayat)
        ).all()
    if not rows:
        raise HTTPException(status_code=404, detail=f"fakta {kind}/{key} belum ada")
    now = datetime.now(UTC)
    return {
        "kind": kind,
        "key": key,
        "facts": [
            {
                "fact_id": f.id,
                "value": f.value_json,
                "source": f.source,
                "observed_at": f.observed_at.isoformat(),
                "ttl_s": f.ttl_s,
                "status": "segar" if (now - f.observed_at).total_seconds() <= f.ttl_s else "basi",
            }
            for f in rows
        ],
    }


def _area_endpoint(area: str):
    def _baca(user: Annotated[User, Depends(auth.current_user)]) -> dict[str, Any]:
        with session_scope() as s:
            return facts_for_area(s, area)

    return _baca


# Rute per-area didaftarkan dinamis: `/api/v1/{area}` untuk tiap AREA_KEYS.
# Tetap di dalam modul ini supaya pendaftarannya terjadi saat router di-include.
for _area in AREA_KEYS:
    router.get(f"/api/v1/{_area}", name=f"area_{_area}")(_area_endpoint(_area))
