"""Adapter LP Agent (baca-saja) — telemetri likuiditas Solana (Meteora).

Sumber: **LP Agent Open API** (https://portal.lpagent.io), tier Basic (owner, $10 lifetime).

ATURAN KERAS ADAPTER INI
------------------------
1. **Baca-saja.** Hanya memakai endpoint GET (``/pools/discover``, ``/pools/{id}/info``,
   ``/pools/{id}/top-lpers``). Tidak pernah menyentuh ``*-tx``, ``/jito``, atau ``/rpc`` —
   itu jalur bangun transaksi, dan gerbang live War Room tetap terkunci (``armed=false``).
2. **Tanpa kunci → jujur, bukan nol.** Bila ``LPAGENT_API_KEY`` tidak ada, kembalikan
   ``{"tersedia": false, "sebab": "..."}``. TIDAK mengarang angka pool.
3. **Hemat kuota.** Rate-limit dijaga (jeda minimum antar panggilan + backoff 429), karena
   tier Basic itu kecil. UI TIDAK boleh memanggil langsung — selalu lewat snapshot worker.

CATATAN KOREKSI (10 Okt): dokumen riset ``docs/belajar/lpagent-io-...`` menulis base URL
``https://api.lpagent.io/v1`` dan endpoint ``/api/v1/pools`` — **keduanya keliru**.
Spesifikasi resmi (``docs.lpagent.io/api-reference/openapi.json``, tersimpan di
``docs/belajar/lampiran/``) menyebut base URL **``https://api.lpagent.io/open-api/v1``**
dan endpoint **``/pools/discover``**. Adapter ini mengikuti spec, bukan dokumen.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

__all__ = ["lpagent_ringkas", "siap"]

# Base URL dari spec resmi (openapi.json servers[0].url) — BUKAN dari dokumen riset.
BASE_URL = "https://api.lpagent.io/open-api/v1"

# Jeda minimum antar panggilan (detik). Tier Basic kecil; lebih baik lambat & utuh daripada
# kena 429. Angka ini konservatif & bisa diturunkan bila owner tahu limit pastinya —
# spec resmi TIDAK mencantumkan rate limit (dokumen riset menyebut 5 RPM, tak terverifikasi).
JEDA_MINIMUM_S = 12.0

# Berapa lama hasil boleh dianggap segar (dipakai sebagai TTL fakta).
TTL_S = 1800

_panggilan_terakhir = 0.0


def _kunci() -> str | None:
    """Ambil API key dari environment atau file rahasia. Tidak pernah ditulis ke log."""
    k = os.environ.get("LPAGENT_API_KEY", "").strip()
    if k:
        return k
    # Jalur cadangan: berkas rahasia (mode 600) di luar repo.
    for p in ("/etc/warroom/lpagent.env", "/home/admin/.config/warroom/lpagent.env"):
        try:
            with open(p, encoding="utf-8") as fh:
                for baris in fh:
                    baris = baris.strip()
                    if baris.startswith("LPAGENT_API_KEY="):
                        v = baris.split("=", 1)[1].strip().strip('"').strip("'")
                        if v:
                            return v
        except OSError:
            continue
    return None


def siap() -> bool:
    """True bila API key tersedia. Dipakai job untuk memutuskan jalan/tidak."""
    return _kunci() is not None


def _get(path: str, params: dict[str, Any] | None = None, timeout: float = 20.0) -> dict[str, Any]:
    """GET satu endpoint. Selalu lewat penjaga jeda. Kembalikan dict hasil atau {'galat': ...}.

    Tidak pernah melempar kecuali bug programmer: kegagalan jaringan/HTTP jadi nilai balik,
    supaya job worker tidak mati karena API pihak ketiga sedang down.
    """
    global _panggilan_terakhir
    kunci = _kunci()
    if not kunci:
        return {"galat": "kunci", "pesan": "LPAGENT_API_KEY belum ada"}

    # Penjaga jeda: tidur seperlunya agar tidak melanggar rate limit tier Basic.
    tunggu = JEDA_MINIMUM_S - (time.monotonic() - _panggilan_terakhir)
    if tunggu > 0:
        time.sleep(tunggu)

    url = BASE_URL + path
    if params:
        url += "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    req = urllib.request.Request(url, headers={"x-api-key": kunci, "accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            _panggilan_terakhir = time.monotonic()
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        _panggilan_terakhir = time.monotonic()
        if e.code == 429:
            # Backoff sopan: job akan dicoba lagi pada interval berikutnya.
            return {"galat": "rate-limit", "pesan": "429 — kuota API habis, coba lagi nanti"}
        if e.code in (401, 403):
            return {"galat": "auth", "pesan": f"{e.code} — API key ditolak"}
        return {"galat": "http", "pesan": f"{e.code}", "kode": e.code}
    except (urllib.error.URLError, TimeoutError) as e:
        _panggilan_terakhir = time.monotonic()
        return {"galat": "jaringan", "pesan": type(e).__name__}
    except json.JSONDecodeError:
        _panggilan_terakhir = time.monotonic()
        return {"galat": "format", "pesan": "respons bukan JSON"}


def _pool_ringkas(p: dict[str, Any]) -> dict[str, Any]:
    """Ambil hanya field yang kita butuhkan dari satu pool. Angka apa adanya."""
    return {
        "pool": p.get("pool"),
        "chain": p.get("chain"),
        "protocol": p.get("protocol"),
        "token0": p.get("token0_symbol"),
        "token1": p.get("token1_symbol"),
        "tvl": p.get("tvl"),
        "vol_24h": p.get("vol_24h"),
        "fee_24h": p.get("fee"),
        "mcap": p.get("mcap"),
        "bin_step": p.get("bin_step"),
        "organic_score": p.get("organic_score"),
        "price_change_24h": p.get("price_24h_change"),
        "created_at": p.get("created_at"),
    }


def lpagent_ringkas(top: int = 5) -> dict[str, Any]:
    """Snapshot pool likuiditas Solana (Meteora) — baca-saja, hemat kuota.

    Kembalikan dict dengan ``tersedia`` + ``sebab`` bila tak bisa (kunci hilang / galat),
    atau ``tersedia: true`` + ``pools`` bila berhasil. Tidak pernah mengarang angka.
    """
    if not _kunci():
        return {
            "tersedia": False,
            "status": "menunggu-kunci",
            "sebab": (
                "LPAGENT_API_KEY belum ada — menunggu owner membeli tier Basic di "
                "portal.lpagent.io dan menaruh kuncinya di /etc/warroom/lpagent.env"
            ),
            "sumber": "LP Agent Open API (Meteora DLMM/DAMM v2)",
            "base_url": BASE_URL,
            "armed": False,
        }

    # /pools/discover — urutkan fee/TVL ratio: pool dengan imbal hasil fee terbaik dulu.
    hasil = _get(
        "/pools/discover",
        {
            "chain": "SOL",
            "platform": "meteora",
            "sortBy": "fee_tvl_ratio",
            "sortOrder": "desc",
            "pageSize": max(1, min(int(top), 50)),
        },
    )
    if "galat" in hasil:
        return {
            "tersedia": False,
            "status": hasil["galat"],
            "sebab": hasil.get("pesan", "gagal memanggil LP Agent"),
            "sumber": "LP Agent Open API (Meteora DLMM/DAMM v2)",
            "armed": False,
        }

    data = hasil.get("data")
    if not isinstance(data, list):
        return {
            "tersedia": False,
            "status": "format",
            "sebab": "respons tidak memuat daftar 'data'",
            "sumber": "LP Agent Open API",
            "armed": False,
        }

    pools = [_pool_ringkas(p) for p in data if isinstance(p, dict)]
    return {
        "tersedia": True,
        "status": "ok",
        "n": len(pools),
        "pools": pools,
        "sumber": "LP Agent Open API (Meteora DLMM/DAMM v2)",
        "base_url": BASE_URL,
        "frekuensi_snapshot": f"{int(TTL_S // 60)} menit",
        "status_verifikasi": "terukur via API pihak ketiga",
        "catatan": (
            "Baca-saja. Ini telemetri pool, BUKAN sinyal beli. Uji paper dulu sebelum "
            "menyentuh transaksi (zap-in/zap-out = jalur uang nyata, tetap terkunci)."
        ),
        "armed": False,
    }
