"""Kolektor Hyperliquid — data publik, tanpa kunci.

Diverifikasi langsung (27 Sep): `POST https://api.hyperliquid.xyz/info`
- `metaAndAssetCtxs` → 200, 178 perp aktif (mark, funding, open interest)
- `l2Book` → 200, order book
- `candleSnapshot` → 200, riwayat candle
- `leaderboard` → 422 (tidak ada endpoint kohort publik; itu agregasi Hyperdash)

Perannya di sistem kita: **confluence, bukan gate.** Funding ekstrem dan OI memberi konteks
positioning — sama seperti Agent 6 di sistem asalnya, yang secara eksplisit tidak boleh
mengubah keputusan setup.
"""

from __future__ import annotations

from typing import Any

import httpx

from ..config import Settings

INFO_URL = "https://api.hyperliquid.xyz/info"


def perp_contexts(settings: Settings, client: httpx.Client | None = None) -> list[dict[str, Any]]:
    """Konteks semua perp aktif: mark, funding per jam, dan OI dalam USD."""
    own = client is None
    c = client or httpx.Client(timeout=20.0)
    try:
        r = c.post(INFO_URL, json={"type": "metaAndAssetCtxs"})
        r.raise_for_status()
        payload = r.json()
    finally:
        if own:
            c.close()

    universe, ctxs = payload[0]["universe"], payload[1]
    rows: list[dict[str, Any]] = []
    for meta, ctx in zip(universe, ctxs, strict=False):
        if meta.get("isDelisted"):
            continue
        try:
            mark = float(ctx.get("markPx") or 0)
            funding = float(ctx.get("funding") or 0)
            oi = float(ctx.get("openInterest") or 0)
        except (TypeError, ValueError):
            continue
        rows.append(
            {
                "coin": meta.get("name"),
                "mark": mark,
                "funding_hourly_pct": funding * 100.0,
                "funding_annual_pct": funding * 100.0 * 24 * 365,
                "oi_coins": oi,
                "oi_usd": oi * mark,
                "max_leverage": meta.get("maxLeverage"),
            }
        )
    return rows


def context_for(coin: str, client: httpx.Client | None = None) -> dict[str, Any] | None:
    """Konteks satu koin (mis. BTC dari BTCUSDT). ``None`` kalau tidak ada di Hyperliquid.

    Dipakai sebagai **konteks tampilan** saja. Aturan hierarki tetap: struktur & risk gate
    yang memutuskan; konteks tidak pernah mengubah tier, POI, SL, atau TP.
    """
    nama = coin.upper().removesuffix("USDT").removesuffix("USD").removesuffix("_USDT")
    own = client is None
    c = client or httpx.Client(timeout=15.0)
    try:
        payload = c.post(INFO_URL, json={"type": "metaAndAssetCtxs"}).json()
    except Exception:  # noqa: BLE001
        return None
    finally:
        if own:
            c.close()

    universe, ctxs = payload[0]["universe"], payload[1]
    for meta, ctx in zip(universe, ctxs, strict=False):
        if meta.get("name") != nama or meta.get("isDelisted"):
            continue
        mark = float(ctx.get("markPx") or 0)
        funding = float(ctx.get("funding") or 0)
        oi = float(ctx.get("openInterest") or 0)
        return {
            "coin": nama,
            "mark": mark,
            "funding_hourly_pct": funding * 100.0,
            "funding_annual_pct": funding * 100.0 * 24 * 365,
            "oi_usd": oi * mark,
        }
    return None


def snapshot(settings: Settings, top: int = 10, client: httpx.Client | None = None) -> dict[str, Any]:
    """Ringkasan siap-tampil: OI terbesar + funding paling ekstrem (dua ujung).

    Funding ekstrem = satu sisi pasar terlalu ramai. Itu **konteks**, bukan alasan entry:
    di sistem asalnya, konteks tidak pernah membatalkan atau mengizinkan setup.
    """
    rows = perp_contexts(settings, client)
    by_oi = sorted(rows, key=lambda r: r["oi_usd"], reverse=True)
    by_funding = sorted(rows, key=lambda r: r["funding_hourly_pct"])
    return {
        "total_perp": len(rows),
        "top_by_oi": by_oi[:top],
        "funding_most_negative": by_funding[:5],
        "funding_most_positive": list(reversed(by_funding[-5:])),
    }
