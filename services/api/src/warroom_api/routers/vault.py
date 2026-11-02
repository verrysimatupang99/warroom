"""Router gudang kredensial generik: simpan endpoint + API key platform manapun.

Polymarket SENGAJA diblokir. Kredensial hanya untuk disalin-tempel manual —
tidak ada kode di repo ini yang memakainya untuk login otomatis.
"""
from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from warroom_core.db import session_scope
from warroom_core.db.models import User, VaultCredential
from warroom_core.mt5_crypto import VaultKeyError
from warroom_core.vault_crypto import extra_decode, extra_encode, vault_decrypt, vault_encrypt

from warroom_api import auth

router = APIRouter(prefix="/api/v1/vault", tags=["vault"])

OwnerDep = Annotated[User, Depends(auth.require_role("owner"))]
ViewerDep = Annotated[User, Depends(auth.require_role("viewer"))]

# Polymarket eksplisit diblokir (keputusan owner).
PLATFORM_DIBLOKIR = {"polymarket"}

# Preset platform: nama -> (label, butuh endpoint?, butuh secret?, field ekstra)
PRESET_PLATFORM: dict[str, dict[str, Any]] = {
    # crypto exchange
    "binance": {"label": "Binance", "endpoint": True, "secret": True, "extra": []},
    "binance-futures": {"label": "Binance Futures", "endpoint": True, "secret": True, "extra": []},
    "bybit": {"label": "Bybit", "endpoint": True, "secret": True, "extra": []},
    "okx": {"label": "OKX", "endpoint": True, "secret": True, "extra": ["passphrase"]},
    "kucoin": {"label": "KuCoin", "endpoint": True, "secret": True, "extra": ["passphrase"]},
    "kraken": {"label": "Kraken", "endpoint": False, "secret": True, "extra": []},
    "bitget": {"label": "Bitget", "endpoint": True, "secret": True, "extra": ["passphrase"]},
    "mexc": {"label": "MEXC", "endpoint": True, "secret": True, "extra": []},
    "gateio": {"label": "Gate.io", "endpoint": True, "secret": True, "extra": []},
    "htx": {"label": "HTX (Huobi)", "endpoint": True, "secret": True, "extra": []},
    "coinbase": {"label": "Coinbase Advanced", "endpoint": True, "secret": True, "extra": []},
    "coinbase-exchange": {
        "label": "Coinbase Exchange",
        "endpoint": True,
        "secret": True,
        "extra": [],
    },
    "crypto-com": {"label": "Crypto.com Exchange", "endpoint": True, "secret": True, "extra": []},
    "deribit": {"label": "Deribit", "endpoint": True, "secret": True, "extra": []},
    "bitfinex": {"label": "Bitfinex", "endpoint": True, "secret": True, "extra": []},
    "bingx": {"label": "BingX", "endpoint": True, "secret": True, "extra": []},
    "hyperliquid": {
        "label": "Hyperliquid",
        "endpoint": True,
        "secret": False,
        "extra": ["wallet_address"],
    },
    # broker / data
    "alpaca": {"label": "Alpaca", "endpoint": True, "secret": True, "extra": []},
    "interactive-brokers": {
        "label": "Interactive Brokers",
        "endpoint": True,
        "secret": True,
        "extra": [],
    },
    "oanda": {"label": "OANDA", "endpoint": True, "secret": True, "extra": ["account_id"]},
    "polygon": {"label": "Polygon.io", "endpoint": False, "secret": False, "extra": []},
    "alphavantage": {"label": "Alpha Vantage", "endpoint": False, "secret": False, "extra": []},
    "coingecko": {"label": "CoinGecko", "endpoint": False, "secret": False, "extra": []},
    "coinmarketcap": {"label": "CoinMarketCap", "endpoint": False, "secret": False, "extra": []},
    "glassnode": {"label": "Glassnode", "endpoint": False, "secret": False, "extra": []},
    "messari": {"label": "Messari", "endpoint": False, "secret": False, "extra": []},
    "the-graph": {"label": "The Graph", "endpoint": True, "secret": False, "extra": []},
    "infura": {"label": "Infura", "endpoint": True, "secret": False, "extra": []},
    "alchemy": {"label": "Alchemy", "endpoint": True, "secret": False, "extra": []},
    "quicknode": {"label": "QuickNode", "endpoint": True, "secret": False, "extra": []},
    # lain-lain (endpoint bebas)
    "custom": {"label": "Custom / Lainnya", "endpoint": True, "secret": True, "extra": []},
}


def _normal_platform(nama: str) -> str:
    """Terima nama longgar ('Binance', 'binance-futures') -> kunci preset."""
    return re.sub(r"[^a-z0-9]+", "-", nama.strip().lower()).strip("-")


class CredentialIn(BaseModel):
    platform: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=128)
    endpoint: str | None = Field(default=None, max_length=2048)
    api_key: str | None = Field(default=None, max_length=512)
    api_secret: str | None = Field(default=None, max_length=1024)
    extra: dict[str, str] = Field(default_factory=dict, max_length=16)
    aktif: bool = True


class CredentialUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=128)
    endpoint: str | None = Field(default=None, max_length=2048)
    api_key: str | None = Field(default=None, max_length=512)
    api_secret: str | None = Field(default=None, max_length=1024)
    extra: dict[str, str] | None = None
    aktif: bool | None = None


def _meta(row: VaultCredential) -> dict[str, Any]:
    """Metadata TANPA rahasia — aman untuk list."""
    return {
        "id": row.id,
        "platform": row.platform,
        "label": row.label,
        "endpoint": row.endpoint,
        "aktif": row.active,
        "punya_key": row.api_key_enc is not None,
        "punya_secret": row.api_secret_enc is not None,
        "extra_keys": sorted(extra_decode(row.extra_enc)) if row.extra_enc else [],
        "dibuat": row.created_at.isoformat(),
        "diubah": (row.updated_at or row.created_at).isoformat(),
    }


@router.get("/platform")
def daftar_platform(user: ViewerDep) -> dict[str, Any]:
    """Daftar preset untuk dropdown UI (Polymarket tidak ikut)."""
    return {
        "platform": [
            {
                "id": k,
                "label": v["label"],
                "butuh_endpoint": v["endpoint"],
                "butuh_secret": v["secret"],
                "extra": v["extra"],
            }
            for k, v in PRESET_PLATFORM.items()
        ],
        "diblokir": sorted(PLATFORM_DIBLOKIR),
    }


@router.get("")
def daftar_kredensial(request: Request, user: ViewerDep) -> dict[str, Any]:
    with session_scope() as db:
        rows = db.scalars(
            select(VaultCredential).order_by(VaultCredential.platform, VaultCredential.label)
        ).all()
        return {"items": [_meta(r) for r in rows]}


@router.post("", status_code=201)
def simpan_kredensial(body: CredentialIn, user: OwnerDep) -> dict[str, Any]:
    platform = _normal_platform(body.platform)
    if platform in PLATFORM_DIBLOKIR:
        raise HTTPException(403, f"Platform '{platform}' diblokir dari vault")
    preset = PRESET_PLATFORM.get(platform) or {"endpoint": True, "secret": True, "extra": []}
    if preset["endpoint"] and not body.endpoint:
        raise HTTPException(422, f"Platform {preset['label']} butuh endpoint")
    with session_scope() as db:
        duplikat = db.scalar(
            select(VaultCredential).where(
                VaultCredential.platform == platform, VaultCredential.label == body.label
            )
        )
        if duplikat is not None:
            raise HTTPException(409, "Sudah ada kredensial dengan platform+label ini")
        now = datetime.now(UTC)
        try:
            kunci_enc = vault_encrypt(body.api_key) if body.api_key else None
            rahasia_enc = vault_encrypt(body.api_secret) if body.api_secret else None
            extra_enc = extra_encode(body.extra) if body.extra else None
        except VaultKeyError as exc:
            raise HTTPException(503, str(exc)) from exc
        row = VaultCredential(
            platform=platform,
            label=body.label,
            endpoint=body.endpoint,
            api_key_enc=kunci_enc,
            api_secret_enc=rahasia_enc,
            extra_enc=extra_enc,
            active=body.aktif,
            created_by=user.id,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
        db.flush()
        hasil = _meta(row)
    return hasil


@router.patch("/{kid}")
def ubah_kredensial(kid: int, body: CredentialUpdate, user: OwnerDep) -> dict[str, Any]:
    with session_scope() as db:
        row = db.get(VaultCredential, kid)
        if row is None:
            raise HTTPException(404, "Kredensial tidak ditemukan")
        if body.label is not None:
            row.label = body.label
        if body.endpoint is not None:
            row.endpoint = body.endpoint
        if body.api_key is not None:
            row.api_key_enc = vault_encrypt(body.api_key) if body.api_key else None
        if body.api_secret is not None:
            row.api_secret_enc = vault_encrypt(body.api_secret) if body.api_secret else None
        if body.extra is not None:
            row.extra_enc = extra_encode(body.extra) if body.extra else None
        if body.aktif is not None:
            row.active = body.aktif
        row.updated_at = datetime.now(UTC)
        db.flush()
        hasil = _meta(row)
    return hasil


@router.delete("/{kid}", status_code=204, response_class=Response)
def hapus_kredensial(kid: int, user: OwnerDep) -> None:
    with session_scope() as db:
        row = db.get(VaultCredential, kid)
        if row is None:
            raise HTTPException(404, "Kredensial tidak ditemukan")
        db.delete(row)


@router.get("/{kid}/rahasia")
def lihat_rahasia(kid: int, user: OwnerDep) -> dict[str, Any]:
    """Endpoint eksplisit untuk salin-tempel manual. Jangan pernah dipanggil otomatis."""
    with session_scope() as db:
        row = db.get(VaultCredential, kid)
        if row is None:
            raise HTTPException(404, "Kredensial tidak ditemukan")
        try:
            extra = extra_decode(row.extra_enc) if row.extra_enc else {}
            hasil = {
                "id": row.id,
                "platform": row.platform,
                "label": row.label,
                "endpoint": row.endpoint,
                "api_key": vault_decrypt(row.api_key_enc) if row.api_key_enc else None,
                "api_secret": vault_decrypt(row.api_secret_enc) if row.api_secret_enc else None,
                "extra": extra,
            }
        except Exception as exc:
            raise HTTPException(503, f"Gagal dekripsi: {exc}") from exc
    return hasil
