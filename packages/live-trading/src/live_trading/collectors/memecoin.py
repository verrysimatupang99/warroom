"""Sumber memecoin — empat venue yang disebut kanal @awsnumsignal, diambil dari data nyata.

Kanal itu menyebut empat sumber: 🌊 Pumpfun · 🪐 Jup · 🟢 Robinhood · 📈 Stonkfun, dengan posisi
yang jujur: **"data mentah, bukan rekomendasi."** Modul ini menyambungkan yang benar-benar bisa
diambil, dan **menyatakan dengan jujur mana yang tidak**.

Hasil pemeriksaan pasar (4 Okt 2026, DexScreener):

| Venue klaim | Bisa diambil? | Bagaimana |
|---|---|---|
| Pumpfun | ✅ | chain `solana`, dexId `pumpfun` |
| Jup | ⚠️ | Jup itu **agregator**, bukan venue. Likuiditasnya ada di meteora/raydium/orca, bukan di "Jup". |
| Robinhood | ✅ | chain **`robinhood`**, dexId `uniswap` dan `flapsh` — rantai ini di-index DexScreener |
| Stonkfun | ❌ | tidak ditemukan di DexScreener. Tidak ditebak; dicatat sebagai tidak tersedia. |

ATURAN KEJUJURAN: modul ini **memindahkan label asli kanal itu** — ini data mentah, bukan
rekomendasi, dan **tidak ada track record yang bisa diverifikasi**. Setiap keluaran membawanya.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

LABEL_JUJUR = (
    "data mentah, bukan rekomendasi — tidak ada track record yang bisa diverifikasi (posisi kanal "
    "sumbernya sendiri)"
)

# venue internal -> (chainId DexScreener, himpunan dexId yang dihitung milik venue itu)
#
# PENTING: himpunan dexId antar-venue harus SALING LEPAS. `pumpswap` adalah AMM milik Pump,
# jadi ia hanya boleh ada di pumpfun — kalau ia juga ada di `jup`, peta jadi ambigu dan hasil
# klasifikasi bergantung urutan kamus (bug yang pernah lolos ke tes).
VENUE: dict[str, tuple[str, set[str]]] = {
    "pumpfun": ("solana", {"pumpfun", "pumpswap"}),
    "jup": ("solana", {"meteora", "raydium", "orca"}),
    "robinhood": ("robinhood", {"uniswap", "flapsh"}),
}

# yang disebut kanal tapi tidak bisa diambil — dinyatakan, bukan dipalsukan
TIDAK_TERSEDIA = {
    "stonkfun": "stonkfun — tidak ditemukan di DexScreener (4 Okt 2026); tidak ditebak, tidak dipalsukan",
}

CACHE_NAME = "memecoin.json"
TTL_S = 900  # 15 menit, sama dengan irama snapshot


def klasifikasi_venue(chain: str | None, dex: str | None) -> str | None:
    """Petakan (chain, dex) ke venue internal. None = tidak termasuk venue mana pun."""
    c = (chain or "").lower()
    d = (dex or "").lower()
    for nama, (chain_v, dex_v) in VENUE.items():
        if c == chain_v and d in dex_v:
            return nama
    return None


def pilih_venue(pairs: list[dict[str, Any]], venue: str, limit: int = 5) -> list[dict[str, Any]]:
    """Saring pool yang termasuk venue tertentu, lalu urutkan menurun **berdasarkan volume**.

    Volume, bukan likuiditas — pelajaran yang sama seperti penyaring LP: pool dengan likuiditas
    besar tetapi hampir tanpa transaksi adalah pool terbengkalai.
    """
    spesifikasi = VENUE.get(venue)
    if not spesifikasi:
        return []
    _, dex_v = spesifikasi

    def vol(p: dict[str, Any]) -> float:
        try:
            return float((p.get("volume") or {}).get("h24") or 0)
        except (TypeError, ValueError):
            return 0.0

    sah = [
        p
        for p in pairs
        if p.get("pairAddress")
        and klasifikasi_venue(p.get("chainId"), p.get("dexId")) == venue
        and (p.get("dexId") or "").lower() in dex_v
        and vol(p) > 0
    ]
    sah.sort(key=vol, reverse=True)
    return sah[:limit]


def _ringkas(p: dict[str, Any], venue: str) -> dict[str, Any]:
    bt = (p.get("baseToken") or {}).get("symbol") or "?"
    qt = (p.get("quoteToken") or {}).get("symbol") or "?"
    def _f(v: Any) -> float | None:
        try:
            x = float(v)
        except (TypeError, ValueError):
            return None
        return x if x == x else None

    liq = _f((p.get("liquidity") or {}).get("usd"))
    v24 = _f((p.get("volume") or {}).get("h24"))
    chg = _f((p.get("priceChange") or {}).get("h24"))
    umur_jam = None
    if p.get("pairCreatedAt"):
        try:
            umur_jam = round((time.time() - float(p["pairCreatedAt"]) / 1000) / 3600, 1)
        except (TypeError, ValueError):
            umur_jam = None
    return {
        "venue": venue,
        "rantai": p.get("chainId"),
        "dex": p.get("dexId"),
        "pasangan": f"{bt}/{qt}",
        "alamat": p.get("pairAddress"),
        "url": p.get("url"),
        "liq_usd": liq,
        "vol_24h": v24,
        # DexScreener TIDAK melaporkan likuiditas untuk pool pumpfun (diverifikasi di endpoint
        # cari DAN detail — keduanya `None`). Jadi turnover tidak bisa dihitung di sana, dan itu
        # dinyatakan lewat `liq_tersedia` alih-alih diam-diam menampilkan "—".
        "liq_tersedia": liq is not None,
        "turnover_24h": round(v24 / liq, 3) if (liq and v24 and liq > 0) else None,
        "chg_h24": chg,
        "umur_jam": umur_jam,
    }


def skrining(
    state_dir: Path | str,
    *,
    per_venue: int = 5,
    sekarang: float | None = None,
    ambil=None,
) -> dict[str, Any]:
    """Ambil kandidat tiap venue, labeli, urutkan. Cache 15 menit.

    `ambil(kata)` = fungsi pencarian DexScreener (untuk tes tanpa jaringan).
    """
    if ambil is None:
        raise ValueError("`ambil` wajib: fungsi pencarian yang menerima kata kunci")

    d = Path(state_dir) / "cache"
    p = d / CACHE_NAME
    kini = time.time() if sekarang is None else sekarang
    try:
        isi = json.loads(p.read_text(encoding="utf-8"))
        if (kini - float(isi.get("diambil_epoch") or 0)) < TTL_S:
            return isi
    except (OSError, json.JSONDecodeError):
        pass

    hasil: dict[str, list[dict[str, Any]]] = {}
    galat: list[str] = []
    for venue in VENUE:
        try:
            payload = ambil(venue)
            pairs = payload.get("pairs") if isinstance(payload, dict) else payload
            hasil[venue] = [_ringkas(x, venue) for x in pilih_venue(pairs or [], venue, per_venue)]
        except Exception as exc:  # noqa: BLE001 — satu venue gagal jangan menjatuhkan sisanya
            galat.append(f"{venue}: {type(exc).__name__}")
            hasil[venue] = []

    out = {
        "diambil_epoch": kini,
        "ttl_s": TTL_S,
        "per_venue": per_venue,
        "venue": hasil,
        "total": sum(len(v) for v in hasil.values()),
        "tidak_tersedia": TIDAK_TERSEDIA,
        "galat": galat,
        "catatan": [
            LABEL_JUJUR,
            "Jup adalah agregator, bukan venue — yang diambil adalah DEX Solana tempat "
            "likuiditasnya benar-benar berada (meteora/raydium/orca)",
            "pool pumpfun tidak melaporkan likuiditas di DexScreener (diverifikasi di endpoint "
            "cari dan detail) — di sana urutan tetap pakai volume, tapi turnover tidak tersedia",
            *TIDAK_TERSEDIA.values(),
        ],
    }
    try:
        d.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    return out
