"""Verifikasi silang LP: harga pool kita vs API publik (7 Okt 2026).

Pertanyaan owner: "apakah data yang kita pegang sama dengan yang ada di internet live?"

Modul ini menjawabnya dengan **membandingkan**, bukan mengklaim:
- satu pool dipanggil ke 2–3 sumber keyless (Meteora DAMM v2 / DexScreener / GeckoTerminal);
- selisih harga antar sumber dihitung dan diberi status (sepakat / selisih / gagal);
- pool yang tipis (<$10k likuiditas) ditandai: selisih di pool tipis itu normal, bukan berita.

Batas yang tidak dilanggar: tidak ada order, tidak ada kunci API, tidak menulis apa pun ke
sumber. Semua kegagalan jaringan ditampilkan sebagai `galat`, bukan angka.
"""

from __future__ import annotations

import json
import urllib.request
from typing import Any

__all__ = ["verifikasi_pool", "pool_contoh", "AMBANG_SELISIH_PCT"]

# Selisih harga antar sumber di atas ini dianggap "perlu dilihat" — bukan otomatis salah,
# karena metodologi agregator berbeda (bukti riset 6 Okt: TVL MET-USDC beda 18%).
AMBANG_SELISIH_PCT = 1.0
_MIN_LIKUIDITAS_SEHAT = 10_000.0

# Pool acuan tetap (bukan pilihan acak): MET-USDC DAMM v2 = pool paling likuid yang kami
# pakai untuk uji; TSLA/WETH = bukti bahwa Robinhood Chain benar-benar berisi Stock Token.
POOL_CONTOH: tuple[dict[str, Any], ...] = (
    {
        "nama": "MET-USDC (Meteora DAMM v2, Solana)",
        "chain": "solana",
        "alamat": "BnztueWcXv93mgW7yJe8WYpnCxpz34nujPhfjQT6SLu1",
        "sumber": {
            "meteora": "https://damm-v2.datapi.meteora.ag/pools/{alamat}",
            "dexscreener": "https://api.dexscreener.com/latest/dex/pairs/{chain}/{alamat}",
            "geckoterminal": "https://api.geckoterminal.com/api/v2/networks/{chain}/pools/{alamat}",
        },
    },
    {
        "nama": "TSLA/WETH (Uniswap v3, Robinhood Chain)",
        "chain": "robinhood",
        "alamat": "0xa1771923045e0dade6578f8c99de248d5a6029b97fb928328f9e767674e7663a",
        "sumber": {
            "dexscreener": "https://api.dexscreener.com/latest/dex/pairs/{chain}/{alamat}",
        },
    },
)


def _get(url: str, timeout: float = 15.0) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": "war-room/1.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 — URL tetap dari modul
        return json.load(r)


def _harga_meteora(d: dict[str, Any]) -> tuple[float | None, float | None]:
    """Harga + likuiditas dari Meteora DAMM v2 Data API."""
    harga = d.get("current_price")
    tvl = d.get("tvl")
    def _angka(v: object) -> float | None:
        return float(v) if isinstance(v, (int, float)) else None

    return (_angka(harga), _angka(tvl))


def _harga_dexscreener(d: dict[str, Any]) -> tuple[float | None, float | None]:
    pairs = d.get("pairs") or d.get("pair")
    if isinstance(pairs, list):
        pairs = pairs[0] if pairs else None
    if not isinstance(pairs, dict):
        return (None, None)
    try:
        harga = float(pairs.get("priceUsd")) if pairs.get("priceUsd") is not None else None
    except (TypeError, ValueError):
        harga = None
    try:
        liq = float((pairs.get("liquidity") or {}).get("usd"))
    except (TypeError, ValueError):
        liq = None
    return (harga, liq)


def _harga_gecko(d: dict[str, Any]) -> tuple[float | None, float | None]:
    attrs = ((d.get("data") or {}).get("attributes")) if isinstance(d, dict) else None
    if not isinstance(attrs, dict):
        return (None, None)
    try:
        harga = float(attrs.get("base_token_price_usd"))
    except (TypeError, ValueError):
        harga = None
    try:
        liq = float(attrs.get("reserve_in_usd"))
    except (TypeError, ValueError):
        liq = None
    return (harga, liq)


def _kesimpulan(harga_sah: list[Any], hasil: dict[str, Any]) -> str:
    if not harga_sah:
        return "TIDAK BISA DIVERIFIKASI (sumber gagal)"
    if hasil.get("sepakat"):
        return "SEPAKAT"
    if hasil.get("selisih_pct") is not None:
        return "SELISIH"
    return "SEBAGIAN"


def verifikasi_pool(pool: dict[str, Any], *, ambil=_get) -> dict[str, Any]:
    """Panggil semua sumber untuk satu pool; bandingkan harga; jangan mengarang bila gagal."""
    alamat, chain = pool["alamat"], pool["chain"]
    hasil: dict[str, Any] = {"nama": pool["nama"], "chain": chain, "alamat": alamat, "sumber": {}}

    for nama, pola in (pool.get("sumber") or {}).items():
        url = pola.format(alamat=alamat, chain=chain)
        try:
            d = ambil(url)
        except Exception as exc:  # noqa: BLE001 — satu sumber gagal bukan alasan mengarang
            hasil["sumber"][nama] = {"galat": f"{type(exc).__name__}: {exc}", "url": url}
            continue
        if nama == "meteora":
            harga, liq = _harga_meteora(d if isinstance(d, dict) else {})
        elif nama == "dexscreener":
            harga, liq = _harga_dexscreener(d if isinstance(d, dict) else {})
        else:
            harga, liq = _harga_gecko(d if isinstance(d, dict) else {})
        hasil["sumber"][nama] = {
            "harga": harga,
            "likuiditas_usd": round(liq, 2) if liq is not None else None,
            "url": url,
        }

    harga_sah = [s["harga"] for s in hasil["sumber"].values() if s.get("harga")]
    if len(harga_sah) >= 2:
        rata = sum(harga_sah) / len(harga_sah)
        selisih_pct = (max(harga_sah) - min(harga_sah)) / rata * 100 if rata else None
        liq = max(
            (s.get("likuiditas_usd") or 0) for s in hasil["sumber"].values()
        )
        hasil["selisih_pct"] = round(selisih_pct, 3) if selisih_pct is not None else None
        hasil["sepakat"] = bool(selisih_pct is not None and selisih_pct <= AMBANG_SELISIH_PCT)
        hasil["likuiditas_tipis"] = liq < _MIN_LIKUIDITAS_SEHAT
        hasil["catatan"] = (
            "Selisih di atas ambang — periksa cache/agregator; TIDAK otomatis berarti data kita salah."
            if not hasil["sepakat"]
            else "Semua sumber sepakat dalam ambang."
        )
        if hasil["likuiditas_tipis"]:
            hasil["catatan"] += " Likuiditas tipis: selisih harga di pool tipis itu wajar."
    else:
        hasil["selisih_pct"] = None
        hasil["sepakat"] = None
        hasil["catatan"] = "Butuh ≥2 sumber yang berhasil untuk membandingkan."

    hasil["kesimpulan"] = _kesimpulan(harga_sah, hasil)
    return hasil


def pool_contoh() -> dict[str, Any]:
    """Verifikasi semua pool acuan — inilah jawaban 'data kita vs internet live'."""
    hasil = [verifikasi_pool(p) for p in POOL_CONTOH]
    return {
        "jumlah": len(hasil),
        "sepakat": sum(1 for h in hasil if h.get("sepakat")),
        "pool": hasil,
        "ambang_selisih_pct": AMBANG_SELISIH_PCT,
        "catatan": (
            "Sumber keyless: Meteora DAMM v2 Data API, DexScreener, GeckoTerminal. "
            "Definisi likuiditas berbeda antar sumber (bukti 6 Okt: selisih 18% pada pool yang sama) — "
            "yang dibandingkan adalah HARGA, bukan likuiditas."
        ),
    }
