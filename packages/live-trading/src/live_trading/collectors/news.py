"""Kolektor berita kripto — RSS publik, tanpa API key.

Kenapa ada: berita menggerakkan pasar lebih cepat dari sinyal teknikal; "apa yang
sedang terjadi" adalah konteks yang sah untuk keputusan. Sumber dipilih yang
**publik & tanpa key** supaya tidak menambah kuota apa pun.

Sumber (keduanya RSS publik, dicek hidup 6 Okt 2026):
    https://cointelegraph.com/rss      (30 item/feed)
    https://decrypt.co/feed            (38 item/feed)

Disiplin yang sama dengan kolektor lain: cache lokal + TTL, dan saat sumber tak
terjangkau pakai cache terakhir **beserta umurnya** — bukan daftar kosong yang
menyamar jadi "tidak ada berita", dan bukan judul karangan.

BATAS YANG DIKODEKAN DI SINI:
- Hanya judul + tautan + waktu + sumber yang diambil. Ringkasan berita TIDAK
  disalin utuh — itu hak cipta penerbit; kita hanya menautkan.
- Item tanpa tanggal sah dibuang (bukan ditebak).
- Urut menurun menurut waktu.
"""

from __future__ import annotations

import json
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import UTC
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

from ..config import Settings, get_settings
from . import make_client

FEEDS: tuple[tuple[str, str], ...] = (
    ("Cointelegraph", "https://cointelegraph.com/rss"),
    ("Decrypt", "https://decrypt.co/feed"),
)
CACHE_NAME = "news_cache.json"
#: Berita bergerak cepat; 20 menit cukup segar untuk konteks, hemat permintaan.
TTL_S = 20 * 60
MAKS_ITEM = 40

_TAG = re.compile(r"<[^>]+>")


def _bersih(teks: Any) -> str:
    """Buang tag HTML dari judul (feed kadang mengirim entity/tag)."""
    return _TAG.sub("", str(teks or "")).strip()


def _ts(teks: Any) -> float | None:
    """Tanggal RSS (RFC 822) → epoch detik. Gagal = None (item dibuang, bukan ditebak)."""
    try:
        dt = parsedate_to_datetime(str(teks))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.timestamp()
    except (TypeError, ValueError, IndexError):
        return None


@dataclass
class Berita:
    judul: str
    tautan: str
    sumber: str
    ts: float
    umur_s: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "judul": self.judul,
            "tautan": self.tautan,
            "sumber": self.sumber,
            "ts": self.ts,
            "umur_s": round(self.umur_s, 1),
        }


def parse_feed(xml: str, sumber: str) -> list[Berita]:
    """RSS 2.0 → daftar Berita. Item tanpa judul/tautan/tanggal dibuang."""
    out: list[Berita] = []
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return out
    for item in root.iter("item"):
        judul = _bersih(item.findtext("title"))
        tautan = _bersih(item.findtext("link"))
        ts = _ts(item.findtext("pubDate"))
        if not judul or not tautan or ts is None:
            continue
        out.append(Berita(judul=judul, tautan=tautan, sumber=sumber, ts=ts))
    return out


@dataclass
class NewsCollector:
    settings: Settings
    feeds: tuple[tuple[str, str], ...] = FEEDS
    _items: list[Berita] = field(default_factory=list, init=False, repr=False)

    @property
    def cache_path(self) -> Path:
        return self.settings.state_dir / "cache" / CACHE_NAME

    def _dari_cache(self) -> list[Berita]:
        try:
            raw = json.loads(self.cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        out = []
        for b in raw.get("items", []):
            try:
                out.append(Berita(
                    judul=str(b["judul"]), tautan=str(b["tautan"]),
                    sumber=str(b["sumber"]), ts=float(b["ts"]),
                ))
            except (KeyError, TypeError, ValueError):
                continue
        return out

    def _ke_cache(self, items: list[Berita]) -> None:
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(
                json.dumps({"ts": time.time(), "items": [b.to_dict() for b in items]}, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError:
            pass  # cache gagal tulis bukan alasan menggagalkan snapshot

    def ambil(self) -> tuple[list[Berita], str]:
        """Ambil dari semua feed. Kembalikan (items, sumber_keterangan)."""
        # Cache segar → pakai itu (hemat permintaan; feed RSS bukan realtime).
        if self.cache_path.exists():
            try:
                age = time.time() - self.cache_path.stat().st_mtime
                if age < TTL_S:
                    cached = self._dari_cache()
                    if cached:
                        return cached, "cache"
            except OSError:
                pass

        items: list[Berita] = []
        gagal: list[str] = []
        client = make_client()
        for nama, url in self.feeds:
            try:
                r = client.get(url, timeout=12.0)
                r.raise_for_status()
                items.extend(parse_feed(r.text, nama))
            except Exception:  # noqa: BLE001 — satu feed mati tidak boleh menjatuhkan semuanya
                gagal.append(nama)
        if not items:
            cached = self._dari_cache()
            if cached:
                return cached, f"cache (feed gagal: {', '.join(gagal) or 'semua'})"
            return [], f"gagal semua feed: {', '.join(gagal)}"
        items.sort(key=lambda b: b.ts, reverse=True)
        items = items[:MAKS_ITEM]
        self._ke_cache(items)
        return items, "live" + (f" (sebagian gagal: {', '.join(gagal)})" if gagal else "")

    def snapshot(self) -> dict[str, Any]:
        items, sumber = self.ambil()
        now = time.time()
        for b in items:
            b.umur_s = max(0.0, now - b.ts)
        return {
            "tersedia": bool(items),
            "sumber_data": sumber,
            "jumlah": len(items),
            "feed": [n for n, _ in self.feeds],
            "items": [b.to_dict() for b in items],
        }


def snapshot(settings: Settings | None = None) -> dict[str, Any]:
    """Pintu masuk ringkas — dipakai dashboard."""
    return NewsCollector(settings or get_settings()).snapshot()
