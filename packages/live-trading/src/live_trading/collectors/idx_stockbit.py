"""Kolektor bandarmologi IDX lewat API Stockbit (exodus) — butuh token sesi.

Bentuk respons di modul ini **bukan tebakan**: diambil dari hasil reverse engineering yang
sudah ada (`apk_re/stockbit_client.py` di Tencent, dibaca read-only), termasuk nama field
aslinya (`brokers_buy[].netbs_broker_code/blot/bval/freq`, `bandar_detector`, dan
`broker_distribution` dengan rantai `distribute_to`).

Token: JWT bearer masa berlaku ~24 jam, diambil manual dari browser (login Stockbit
dilindungi reCAPTCHA — **jangan diotomasi**). Simpan di `secrets/stockbit_token`.
Tidak ada token tersimpan di repo ini, dan tidak boleh ada.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..config import Settings

EXODUS = "https://exodus.stockbit.com"
TOKEN_FILENAME = "stockbit_token"

PERIODS = {
    "latest": "BROKER_SUMMARY_PERIOD_LATEST",
    "yesterday": "BROKER_SUMMARY_PERIOD_YESTERDAY",
    "7d": "BROKER_SUMMARY_PERIOD_LAST_7_DAYS",
    "3m": "BROKER_SUMMARY_PERIOD_LAST_3_MONTHS",
    "ytd": "BROKER_SUMMARY_PERIOD_YEAR_TO_DATE",
}

HEADERS = {
    "accept": "application/json",
    "origin": "https://stockbit.com",
    "referer": "https://stockbit.com/",
    "user-agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
    ),
}


def secrets_dir(settings: Settings) -> Path:
    return Path(getattr(settings, "secrets_dir", Path(settings.home) / "secrets"))


def load_token(settings: Settings) -> str | None:
    """Token dari berkas, atau None. Tidak pernah dari kode, tidak pernah di-log."""
    p = secrets_dir(settings) / TOKEN_FILENAME
    if p.is_file():
        t = p.read_text(encoding="utf-8").strip()
        if t:
            return t.replace("Bearer ", "")
    return None


def _get(path: str, params: dict[str, Any], token: str | None) -> dict[str, Any]:
    if not token:
        return {
            "error": "token_belum_ada",
            "petunjuk": (
                f"Simpan bearer JWT Stockbit di {TOKEN_FILENAME} (masa berlaku ~24 jam). "
                "Login Stockbit dilindungi reCAPTCHA — ambil manual, jangan diotomasi."
            ),
        }
    try:
        from curl_cffi import requests as cr
    except ImportError as exc:  # pragma: no cover
        return {"error": f"butuh curl_cffi: {exc}"}

    h = dict(HEADERS)
    h["authorization"] = f"Bearer {token}"
    r = cr.get(f"{EXODUS}{path}", params=params, headers=h, timeout=30, impersonate="chrome")
    if r.status_code != 200:
        return {"error": f"HTTP {r.status_code}", "body": r.text[:200]}
    return r.json()


def broker_summary(symbol: str, period: str = "latest", token: str | None = None) -> dict[str, Any]:
    """Net buy/sell per broker + deteksi bandar. Ini isi "bandarmologi"-nya."""
    res = _get(
        f"/marketdetectors/{symbol.upper()}",
        {
            "transaction_type": "TRANSACTION_TYPE_NET",
            "market_board": "MARKET_BOARD_REGULER",
            "investor_type": "INVESTOR_TYPE_ALL",
            "limit": 25,
            "period": PERIODS.get(period, PERIODS["latest"]),
        },
        token,
    )
    if "error" in res:
        return res

    d = (res.get("body") or {}).get("data") or {}
    bs = d.get("broker_summary") or {}
    bd = d.get("bandar_detector") or {}

    def side(key: str, val_field: str, lot_field: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for b in (bs.get(key) or [])[:8]:
            out.append(
                {
                    "broker": b.get("netbs_broker_code"),
                    "type": b.get("type"),
                    "net_lot": b.get(lot_field),
                    "net_idr": b.get(val_field),
                    "freq": b.get("freq"),
                }
            )
        return out

    return {
        "symbol": symbol.upper(),
        "periode": period,
        "jendela": [d.get("from"), d.get("to")],
        "bandar": {
            "accdist": bd.get("broker_accdist"),
            "total_buyer": bd.get("total_buyer"),
            "total_seller": bd.get("total_seller"),
        },
        "pembeli": side("brokers_buy", "bval", "blot"),
        "penjual": side("brokers_sell", "sval", "slot"),
    }


def broker_distribution(
    symbol: str,
    period: str = "LAST_7_DAYS",
    data_type: str = "VALUE",
    investor: str = "ALL",
    token: str | None = None,
) -> dict[str, Any]:
    """Rantai distribusi broker→broker: siapa menyalurkan ke siapa.

    Ini bagian paling berbobot untuk pertanyaan "siapa sedang mengumpulkan": bukan cuma
    broker mana yang net beli, tapi ke mana barangnya berpindah.
    """
    res = _get(
        "/order-trade/broker/distribution",
        {
            "symbol": symbol.upper(),
            "data_type": f"BROKER_DISTRIBUTION_DATA_TYPE_{data_type}",
            "investor_type": f"INVESTOR_TYPE_{investor}",
            "market_board": "MARKET_TYPE_REGULER",  # prefiks beda dari marketdetectors
            "period": f"TB_PERIOD_{period}",
        },
        token,
    )
    if "error" in res:
        return res

    d = (res.get("body") or {}).get("data") or {}
    bucket = "by_value" if d.get("by_value") else "by_volume"
    out: dict[str, Any] = {
        "symbol": symbol.upper(),
        "jendela": [d.get("start_date"), d.get("end_date")],
        "satuan": bucket,
    }
    for key in ("top_broker_buy", "top_broker_sell"):
        rows = []
        for b in ((d.get(bucket) or {}).get(key) or [])[:5]:
            det = b.get("detail") or {}
            rows.append(
                {
                    "broker": det.get("code"),
                    "type": det.get("type"),
                    "amount": det.get("amount"),
                    "menyalur_ke": [
                        {"broker": x.get("code"), "amount": x.get("amount")}
                        for x in (b.get("distribute_to") or [])[:3]
                    ],
                }
            )
        out[key] = rows
    return out


def bandar_view(symbol: str, period: str = "7d", token: str | None = None) -> dict[str, Any]:
    """Gabungan: ringkasan net per broker + rantai distribusi."""
    return {
        "ringkasan": broker_summary(symbol, "latest", token),
        "distribusi": broker_distribution(
            symbol,
            {"latest": "YESTERDAY", "7d": "LAST_7_DAYS", "3m": "LAST_3_MONTHS"}.get(period, "LAST_7_DAYS"),
            token=token,
        ),
    }
