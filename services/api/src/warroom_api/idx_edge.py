"""Sumber data IDX: idx-edge (stock.arjum.com).

Kuota: sebagian endpoint berbayar per panggilan ("1 kode = 1 kuota"), jadi modul ini
menyimpan hasil di cache dan TIDAK memanggil API untuk setiap request pengguna.
Aturan yang dipegang:

  - Angka yang tampil harus dari respons asli, tanpa diisi nol kalau gagal.
  - Kalau key tidak ada, balas 503 "not_configured" — bukan timeout menyesatkan.
  - Cache TTL berbeda per jenis data: quote 60 detik (pasar berubah cepat),
    daftar saham 20 menit, sisanya sesuai umur data.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any

BASE = "https://stock.arjum.com"
KEY_ENV = "WARROOM_IDX_API_KEY"
KEY_FILE = Path("/etc/warroom/idx.env")
CACHE_DIR = Path("/var/lib/warroom/idx-cache")

# TTL dalam detik. Quote pendek karena harga bergerak; daftar saham panjang karena
# isinya jarang berubah dan tiap panggilan memakan kuota.
TTL = {
    "health": 300,
    "search": 1800,
    "price": 60,
    "history": 900,
    "movers": 120,
    "market_cap": 3600,
    "broker_summary": 1800,
    "broker_accumulation": 1800,
    "analysis": 3600,
    "screener": 1800,
    "financial": 86400,
    "insiders": 3600,
    "seasonal": 86400,
}


class IdxTidakSiap(RuntimeError):
    """Key belum dipasang atau kuota habis — bukan kesalahan pengguna."""


def _kunci() -> str:
    kunci = os.environ.get(KEY_ENV, "").strip()
    if kunci:
        return kunci
    if KEY_FILE.exists():
        for baris in KEY_FILE.read_text().splitlines():
            baris = baris.strip()
            if not baris or baris.startswith("#"):
                continue
            if "=" in baris:
                nama, nilai = baris.split("=", 1)
                if nama.strip() == KEY_ENV:
                    return nilai.strip().strip('"').strip("'")
            elif baris.startswith("sk_"):
                return baris
    raise IdxTidakSiap(f"Kunci API IDX belum dipasang di {KEY_FILE} atau env {KEY_ENV}.")


def _cache_path(jenis: str, kunci_cache: str) -> Path:
    aman = "".join(c if c.isalnum() or c in "-_" else "_" for c in kunci_cache)[:80]
    return CACHE_DIR / f"{jenis}__{aman}.json"


def _baca_cache(jenis: str, kunci_cache: str) -> Any | None:
    p = _cache_path(jenis, kunci_cache)
    if not p.exists():
        return None
    try:
        isi = json.loads(p.read_text())
    except (OSError, ValueError):
        return None
    umur = time.time() - isi.get("_ts", 0)
    if umur > TTL.get(jenis, 300):
        return None
    return isi.get("data")


def _tulis_cache(jenis: str, kunci_cache: str, data: Any) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        p = _cache_path(jenis, kunci_cache)
        p.write_text(json.dumps({"_ts": time.time(), "data": data}, ensure_ascii=False))
    except OSError:
        pass  # cache gagal bukan alasan menggagalkan request


async def _get(jalur: str, params: dict[str, Any] | None = None, timeout: float = 20.0) -> Any:
    """Panggil idx-edge sekali. Tanpa retry: kuota berbayar, jangan diulang buta."""
    try:
        import httpx
    except ImportError as exc:  # pragma: no cover
        raise IdxTidakSiap("httpx tidak tersedia di lingkungan ini") from exc

    kunci = _kunci()
    url = BASE + jalur
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as klien:
        r = await klien.get(url, params=params, headers={"X-API-Key": kunci, "Accept": "application/json"})
    if r.status_code == 401:
        raise IdxTidakSiap("Kunci API IDX ditolak (401). Periksa key atau masa aktifnya.")
    if r.status_code == 429:
        raise IdxTidakSiap("Kuota IDX habis atau terlalu banyak panggilan (429).")
    if r.status_code >= 400:
        detail = ""
        try:
            detail = (r.json() or {}).get("detail", "")
        except ValueError:
            detail = r.text[:160]
        raise IdxTidakSiap(f"IDX menolak permintaan ({r.status_code}): {detail}")
    return r.json()


async def _ambil(jenis: str, jalur: str, params: dict[str, Any] | None = None) -> Any:
    kunci_cache = jalur + "?" + "&".join(f"{k}={v}" for k, v in sorted((params or {}).items()))
    tersimpan = _baca_cache(jenis, kunci_cache)
    if tersimpan is not None:
        return tersimpan
    data = await _get(jalur, params)
    _tulis_cache(jenis, kunci_cache, data)
    return data


# --------------------------------------------------------------------------- #
# Pembungkus per jenis data. Semuanya async dan mengembalikan dict siap saji.
# --------------------------------------------------------------------------- #


async def kesehatan() -> dict[str, Any]:
    return await _ambil("health", "/api/health")


async def cari(q: str) -> list[dict[str, Any]]:
    if len(q.strip()) < 2:
        return []
    data = await _ambil("search", "/api/search", {"q": q.strip()})
    return data if isinstance(data, list) else []


async def harga(kode: str) -> dict[str, Any]:
    kode = kode.strip().upper()
    return await _ambil("price", f"/api/price/{kode}")


async def harga_banyak(kode: list[str]) -> dict[str, Any]:
    """Ambil beberapa kode sekaligus. Tiap kode memakan 1 kuota, jadi maksimal 20."""
    bersih = [k.strip().upper() for k in kode if k.strip()][:20]
    if not bersih:
        raise IdxTidakSiap("Tidak ada kode saham yang diminta.")
    return await _ambil("price", "/api/price/list", {"codes": ",".join(bersih)})


async def riwayat(kode: str, limit: int = 60) -> dict[str, Any]:
    kode = kode.strip().upper()
    limit = max(20, min(int(limit), 500))
    return await _ambil("history", f"/api/history/{kode}", {"limit": limit})


async def penggerak(urut: str = "chg") -> dict[str, Any]:
    return await _ambil("movers", "/api/movers", {"by": urut})


async def kapitalisasi(halaman: int = 1) -> dict[str, Any]:
    return await _ambil("market_cap", "/api/market-cap", {"page": max(1, int(halaman))})


async def ringkasan_broker(kode: str, hari: int = 1) -> dict[str, Any]:
    kode = kode.strip().upper()
    return await _ambil("broker_summary", f"/api/broker-summary/{kode}", {"net": "false", "broker_limit": 10})


async def akumulasi_broker(kode: str) -> dict[str, Any]:
    kode = kode.strip().upper()
    return await _ambil("broker_accumulation", f"/api/broker-accumulation/{kode}")


async def analisa(kode: str) -> dict[str, Any]:
    kode = kode.strip().upper()
    return await _ambil("analysis", f"/api/analysis/{kode}")


async def insider(kode: str) -> dict[str, Any]:
    kode = kode.strip().upper()
    return await _ambil("insiders", f"/api/insiders/{kode}")


async def laporan_keuangan(kode: str) -> dict[str, Any]:
    kode = kode.strip().upper()
    return await _ambil("financial", f"/api/financial-statements/{kode}")


async def musiman(kode: str) -> dict[str, Any]:
    kode = kode.strip().upper()
    return await _ambil("seasonal", f"/api/seasonal/{kode}")


async def screener() -> dict[str, Any]:
    return await _ambil("screener", "/api/screener/latest")


async def indeks_ringkas() -> dict[str, Any]:
    """Ringkasan pasar: penggerak + beberapa saham besar, satu panggilan per bagian."""
    naik, turun, blue = await asyncio.gather(
        penggerak("chg"),
        penggerak("pct"),
        harga_banyak(["BBCA", "BBRI", "BMRI", "TLKM", "ASII"]),
        return_exceptions=True,
    )
    hasil: dict[str, Any] = {}
    for nama, isi in (("penggerak_nilai", naik), ("penggerak_persen", turun), ("blue_chip", blue)):
        if isinstance(isi, Exception):
            hasil[nama] = {"galat": str(isi)}
        else:
            hasil[nama] = isi
    hasil["sumber"] = "idx-edge:stock.arjum.com"
    hasil["diambil"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    return hasil
