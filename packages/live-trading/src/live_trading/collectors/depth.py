"""Kedalaman pasar (L2): berapa lot yang benar-benar bisa diisi pada harga tertentu?

Kenapa modul ini ada
--------------------
Uji sisi maker (`docs/uji-sisi-maker-20260928.md`) menyimpulkan edge live-trading
**bersyarat pada dua hal**: biaya 0 bps DAN kedalaman fill ≤5 bps. Yang kedua itu
selama ini **diasumsikan dari candle**, bukan diukur. Pada penetrasi 15 bps edge-nya
hilang sepenuhnya (−0,011R) — jadi asumsi ini menentukan hidup-matinya strategi.

Modul ini mengubah asumsi itu jadi angka:
  * ambil snapshot buku order (bids/asks) dari Binance futures;
  * hitung berapa notional yang bisa diisi kalau kita memasang limit pada harga X;
  * laporkan kedalaman dalam bps dari mid, dan berapa lot yang tertelan pada tiap level.

Yang **tidak** dilakukan modul ini: menyimpulkan apakah order kita akan terisi. Antrean
(queue position) tidak terlihat dari snapshot — kita hanya tahu ada berapa lot di level
itu, bukan berapa yang sudah mengantre di depan kita. Itu dinyatakan eksplisit di
`depth_at`, bukan disembunyikan.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..config import Settings
from . import make_client


@dataclass
class BookLevel:
    price: float
    size: float

    @property
    def notional(self) -> float:
        return self.price * self.size


@dataclass
class DepthReport:
    """Ringkasan kedalaman satu sisi buku pada beberapa ambang bps dari mid."""

    pair: str
    side: str                       # "bid" (kita beli di sini kalau limit buy) atau "ask"
    mid: float
    best: float                     # harga terbaik sisi itu
    levels: list[dict[str, Any]]    # [{bps, price, notional_usd, cum_notional_usd}]
    total_notional_usd: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "pair": self.pair, "side": self.side, "mid": self.mid, "best": self.best,
            "levels": self.levels, "total_notional_usd": round(self.total_notional_usd, 2),
        }


def parse_book(payload: dict[str, Any]) -> tuple[list[BookLevel], list[BookLevel]]:
    """Ubah payload `/fapi/v1/depth` jadi (bids, asks) terurut harga terbaik dulu."""
    bids = [BookLevel(float(p), float(s)) for p, s in (payload.get("bids") or [])]
    asks = [BookLevel(float(p), float(s)) for p, s in (payload.get("asks") or [])]
    bids.sort(key=lambda level: -level.price)      # bid terbaik = harga tertinggi
    asks.sort(key=lambda level: level.price)       # ask terbaik = harga terendah
    return bids, asks


def mid_price(bids: list[BookLevel], asks: list[BookLevel]) -> float | None:
    """Mid = rata-rata bid dan ask terbaik. None kalau salah satu sisi kosong."""
    if not bids or not asks:
        return None
    return (bids[0].price + asks[0].price) / 2.0


def depth_at(levels: list[BookLevel], mid: float, max_bps: float) -> list[dict[str, Any]]:
    """Notional kumulatif yang tersedia pada tiap level, diukur dari `mid`.

    `bps` = jarak harga level itu dari mid, dalam basis poin. Untuk sisi bid, level di
    bawah mid; untuk ask, di atas. Tanda selalu positif (jarak), supaya bisa dibandingkan
    antar sisi.

    BATAS YANG HARUS DISADARI: ini kedalaman **yang terlihat di buku**, bukan jaminan
    order kita terisi. Kalau ada 10 lot di level itu dan 10 lot sudah mengantre di depan
    kita, kita tidak dapat apa-apa. Snapshot tidak memuat informasi antrean.
    """
    out: list[dict[str, Any]] = []
    cum = 0.0
    for lvl in levels:
        if mid <= 0:
            break
        bps = abs(lvl.price - mid) / mid * 10000.0
        if bps > max_bps:
            break
        cum += lvl.notional
        out.append({
            "bps": round(bps, 2),
            "price": lvl.price,
            "notional_usd": round(lvl.notional, 2),
            "cum_notional_usd": round(cum, 2),
        })
    return out


def depth_report(payload: dict[str, Any], pair: str, max_bps: float = 20.0) -> dict[str, Any]:
    """Laporan kedalaman dua sisi untuk satu snapshot buku."""
    bids, asks = parse_book(payload)
    mid = mid_price(bids, asks)
    if mid is None:
        return {"pair": pair, "error": "buku kosong (salah satu sisi tidak ada)"}
    bid_levels = depth_at(bids, mid, max_bps)
    ask_levels = depth_at(asks, mid, max_bps)
    return {
        "pair": pair,
        "mid": round(mid, 8),
        "bid": DepthReport(pair, "bid", mid, bids[0].price, bid_levels,
                           bid_levels[-1]["cum_notional_usd"] if bid_levels else 0.0).as_dict(),
        "ask": DepthReport(pair, "ask", mid, asks[0].price, ask_levels,
                           ask_levels[-1]["cum_notional_usd"] if ask_levels else 0.0).as_dict(),
    }


def notional_at_bps(report: dict[str, Any], side: str, bps: float) -> float:
    """Notional kumulatif yang tersedia pada `bps` tertentu — untuk uji cepat."""
    block = report.get(side) or {}
    best = 0.0
    for lvl in block.get("levels") or []:
        if lvl["bps"] <= bps:
            best = lvl["cum_notional_usd"]
        else:
            break
    return best


@dataclass
class DepthCollector:
    """Ambil snapshot buku order dari Binance futures (publik, tanpa kunci)."""

    settings: Settings
    client: Any = None

    def __post_init__(self) -> None:
        self._client = self.client or make_client(timeout=15.0)

    def book(self, pair: str, limit: int = 100) -> dict[str, Any]:
        r = self._client.get(f"{self.settings.binance_fapi}/fapi/v1/depth",
                             params={"symbol": pair, "limit": limit})
        r.raise_for_status()
        return r.json()

    def report(self, pair: str, limit: int = 100, max_bps: float = 20.0) -> dict[str, Any]:
        try:
            payload = self.book(pair, limit=limit)
        except Exception as exc:  # noqa: BLE001 — satu pair gagal jangan bunuh sisanya
            return {"pair": pair, "error": f"{type(exc).__name__}: {exc}"}
        return depth_report(payload, pair, max_bps=max_bps)

    def reports(self, pairs: tuple[str, ...], limit: int = 100,
                max_bps: float = 20.0) -> list[dict[str, Any]]:
        return [self.report(p, limit=limit, max_bps=max_bps) for p in pairs]
