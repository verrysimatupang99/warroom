"""Kolektor screener IDX lewat TradingView — tanpa kunci, tanpa sesi.

Diverifikasi langsung dari Webdock (27 Sep): `POST scanner.tradingview.com/indonesia/scan`
→ 200, 845 ticker IDX, lengkap dengan volume, market cap, dan indikator.

Catatan penting yang ditemukan dengan menguji, bukan mengasumsikan:
- `RSI|21` **tidak didukung** (mengembalikan null). Yang tersedia `RSI` = periode 14.
- `EMA8|1` / `EMA21|1` **tidak mengembalikan nilai EMA sebelumnya** (isinya sama dengan
  harga close). Artinya "cross yang baru terjadi" **tidak bisa** dideteksi dari scanner ini.
  Karena itu modul ini melaporkan **keadaan** (EMA8 di atas/bawah EMA21), bukan "cross baru" —
  dan tidak boleh disebut "cross" di UI. Sumber riwayat harga IDX masih dicari:
  Yahoo Finance diblok (429), IDX resmi diblok Cloudflare dari IP ini (403).
"""

from __future__ import annotations

from typing import Any

TV_URL = "https://scanner.tradingview.com/indonesia/scan"

BASE_COLUMNS = [
    "name",
    "close",
    "change",
    "volume",
    "market_cap_basic",
    "RSI",
    "EMA8",
    "EMA21",
    "ATR",
    "Recommend.All",
]

HEADERS = {"origin": "https://www.tradingview.com", "referer": "https://www.tradingview.com/"}


def _post(body: dict[str, Any]) -> dict[str, Any]:
    """TradingView memblokir klien biasa; curl_cffi meniru TLS Chrome."""
    try:
        from curl_cffi import requests as cr
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("butuh curl_cffi: uv pip install curl_cffi") from exc

    r = cr.post(TV_URL, json=body, impersonate="chrome", timeout=30, headers=HEADERS)
    r.raise_for_status()
    return r.json()


def screen(
    *,
    min_volume: int = 5_000_000,
    min_price: float = 50.0,
    limit: int = 20,
    sort_by: str = "volume",
    uptrend_only: bool = False,
    rsi_below: float | None = None,
) -> list[dict[str, Any]]:
    """Saring saham IDX. ``uptrend_only`` = EMA8 di atas EMA21 (keadaan, bukan cross)."""
    filters: list[dict[str, Any]] = [
        {"left": "type", "operation": "equal", "right": "stock"},
        {"left": "volume", "operation": "greater", "right": min_volume},
        {"left": "close", "operation": "greater", "right": min_price},
    ]
    if uptrend_only:
        filters.append({"left": "EMA8", "operation": "greater", "right": "EMA21"})
    if rsi_below is not None:
        filters.append({"left": "RSI", "operation": "less", "right": rsi_below})

    body = {
        "filter": filters,
        "options": {"lang": "id"},
        "markets": ["indonesia"],
        "symbols": {"query": {"types": []}},
        "columns": BASE_COLUMNS,
        "sort": {"sortBy": sort_by, "sortOrder": "desc"},
        "range": [0, limit],
    }
    data = _post(body)

    out: list[dict[str, Any]] = []
    for row in data.get("data", []):
        d = dict(zip(BASE_COLUMNS, row["d"], strict=False))
        ema8, ema21 = d.get("EMA8"), d.get("EMA21")
        if ema8 is not None and ema21 is not None:
            state = "naik" if ema8 > ema21 else "turun"
        else:
            state = "n/a"
        out.append(
            {
                "ticker": d.get("name"),
                "close": d.get("close"),
                "change_pct": d.get("change"),
                "volume": d.get("volume"),
                "market_cap": d.get("market_cap_basic"),
                "rsi14": d.get("RSI"),
                "ema8": ema8,
                "ema21": ema21,
                "ema_state": state,  # keadaan, BUKAN cross
                "atr": d.get("ATR"),
                "tv_recommend": d.get("Recommend.All"),
            }
        )
    return out


def summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    naik = [r for r in rows if r["ema_state"] == "naik"]
    return {
        "jumlah": len(rows),
        "ema_naik": len(naik),
        "ema_turun": len(rows) - len(naik),
        "rows": rows,
    }
