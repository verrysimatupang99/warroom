"""Kolektor crypto — data publik Binance perp + OKX swap (pengganti MEXC, 10 Okt).

Ini lapisan **data**, bukan mesin sinyal. Mesin SMC warisan (``crypto/scripts``)
masih jalan apa adanya dan dipakai sebagai pembanding sampai port-nya selesai.
Yang di sini menjawab pertanyaan yang lebih sempit tapi krusial: *pair mana yang
layak dilihat*, dengan angka yang bisa diverifikasi ulang.

Metrik per pair:
* ``funding``  — biaya pendanaan 8 jam (positif ekstrem = long crowded);
* ``oi``       — open interest kontrak;
* ``chg24h``   — perubahan harga 24 jam;
* ``taker``    — rasio taker buy / total dari klines (agresi beli vs jual).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from ..config import Settings
from . import make_client

DEFAULT_PAIRS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "LINKUSDT", "SUIUSDT")


def okx_inst(pair: str) -> str:
    """MEXC "BTC_USDT" / "BTCUSDT" -> OKX "BTC-USDT-SWAP" (default SWAP).

    Aturan: buang "_", lalu bila berakhir USDT dan belum ada "-", sisipkan
    pemisah dan akhiran SWAP. Sudah berbentuk OKX -> dibiarkan apa adanya.
    """
    p = str(pair).upper().strip()
    if "-" in p:
        return p
    p = p.replace("_", "")
    if p.endswith("USDT") and len(p) > 4:
        return f"{p[:-4]}-USDT-SWAP"
    return p


def taker_ratio(klines: list[list[Any]]) -> float | None:
    """Rasio taker buy terhadap total volume pada deret kline Binance.

    Kolom 9 = ``takerBuyBaseAssetVolume``; kolom 5 = ``volume``.
    >1.2 berarti agresi beli, <0.8 agresi jual (ambang yang sama dengan warisan).
    """
    if not klines:
        return None
    buy = sum(float(k[9]) for k in klines)
    total = sum(float(k[5]) for k in klines)
    if total <= 0:
        return None
    return round(buy / total * 2, 3)


@dataclass
class CryptoCollector:
    settings: Settings
    client: httpx.Client | None = None

    def __post_init__(self) -> None:
        self._client = self.client or make_client(timeout=20.0)

    def _get(self, base: str, path: str, params: dict[str, Any] | None = None) -> Any:
        r = self._client.get(f"{base}{path}", params=params)
        r.raise_for_status()
        return r.json()

    def pair_snapshot(self, pair: str, klines: int = 24) -> dict[str, Any]:
        fapi = self.settings.binance_fapi
        snap: dict[str, Any] = {"pair": pair}

        prem = self._get(fapi, "/fapi/v1/premiumIndex", {"symbol": pair})
        snap["funding"] = round(float(prem.get("lastFundingRate") or 0) * 100, 4)

        oi = self._get(fapi, "/fapi/v1/openInterest", {"symbol": pair})
        snap["oi"] = round(float(oi.get("openInterest") or 0), 2)

        tick = self._get(fapi, "/fapi/v1/ticker/24hr", {"symbol": pair})
        snap["price"] = float(tick.get("lastPrice") or 0)
        snap["chg24h"] = round(float(tick.get("priceChangePercent") or 0), 2)
        snap["quote_vol"] = round(float(tick.get("quoteVolume") or 0) / 1e6, 1)
        snap["observed_at_ms"] = int(tick.get("closeTime") or 0)

        kl = self._get(fapi, "/fapi/v1/klines", {"symbol": pair, "interval": "1h", "limit": klines})
        snap["taker"] = taker_ratio(kl)
        return snap

    def digest(self, pairs: tuple[str, ...] = DEFAULT_PAIRS) -> list[dict[str, Any]]:
        out = []
        for p in pairs:
            try:
                out.append(self.pair_snapshot(p))
            except Exception as exc:  # noqa: BLE001 — satu pair gagal jangan bunuh sisanya
                out.append({"pair": p, "error": type(exc).__name__})
        return out

    def okx_check(self, pair: str = "BTC-USDT-SWAP") -> dict[str, Any]:
        """Verifikasi jalur data OKX hidup dari mesin ini (pengganti MEXC, 10 Okt).

        OKX memakai `-` (BTC-USDT-SWAP), sumber lama memakai `_` (BTC_USDT). Simbol
        dinormalkan lewat `okx_inst()` supaya pemanggil boleh pakai gaya lama.
        """
        inst = okx_inst(pair)
        d = self._get(self.settings.okx_api, "/api/v5/market/ticker", {"instId": inst})
        data = (d.get("data") or [{}])[0]
        return {
            "symbol": inst,
            "last": data.get("last"),
            "funding": None,  # funding diambil endpoint terpisah (public/funding-rate)
            "ok": str(d.get("code")) == "0" and bool(data),
        }
