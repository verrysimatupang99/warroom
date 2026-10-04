"""Kolektor DEX Screener (gratis, tanpa key, 60 req/menit).

Dua fungsi:
- boosts_top(): token yang lagi di-boost (perhatian = bahan discovery).
- enrich(pairs): statistik buys/sells + likuiditas untuk token shadow kita,
  konfirmasi independen dari feed GMGN.

Cache berkas TTL 15 menit — snapshot dibangun tiap 15 menit jadi 1x fetch.
"""

from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path
from typing import Any

BASE = "https://api.dexscreener.com"
TTL_S = 900

# chain internal GMGN -> chainId DEX Screener (yang tak ada = skip jujur)
CHAIN_MAP = {
    "sol": "solana",
    "eth": "ethereum",
    "bsc": "bsc",
    "base": "base",
}


def _get(path: str, timeout: float = 15.0) -> Any:
    req = urllib.request.Request(BASE + path, headers={"User-Agent": "war-room/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def _cache_file(state_dir: Path) -> Path:
    d = state_dir / "cache" / "dexscreen"
    d.mkdir(parents=True, exist_ok=True)
    return d / "dex.json"


def load_cache(state_dir: Path) -> dict[str, Any] | None:
    try:
        p = _cache_file(state_dir)
        d = json.loads(p.read_text(encoding="utf-8"))
        if time.time() - float(d.get("ts", 0)) < TTL_S:
            return d
    except (OSError, json.JSONDecodeError, ValueError, KeyError):
        pass
    return None


def save_cache(state_dir: Path, payload: dict[str, Any]) -> None:
    try:
        p = _cache_file(state_dir)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps({**payload, "ts": time.time()}), encoding="utf-8")
        tmp.replace(p)
    except OSError:
        pass


def boosts_top(limit: int = 10) -> list[dict[str, Any]]:
    """Token ter-boost — discovery, bukan rekomendasi (boost = iklan berbayar)."""
    try:
        data = _get("/token-boosts/top/v1")
    except Exception:
        return []
    out = []
    for t in (data or [])[:limit]:
        out.append(
            {
                "symbol": (t.get("tokenAddress") or "")[:12],
                "chain": t.get("chainId"),
                "url": t.get("url"),
                "tokenAddress": t.get("tokenAddress"),
                "description": (t.get("description") or "")[:120],
            }
        )
    return out


def _angka(v: Any) -> float | None:
    """float atau None — tidak pernah menebak nol dari data yang tidak ada."""
    try:
        f = float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return f if f == f else None  # buang NaN


def ukur_lp(p: dict[str, Any]) -> dict[str, Any]:
    """Ukur peluang LP dari SATU pool DexScreener — dan jujur soal yang belum diketahui.

    Yang **bisa** dihitung dari data pool: turnover (volume24j ÷ likuiditas) sebagai proksi
    potensi fee, tekanan IL (perubahan harga), dan umur pool.

    Yang **tidak bisa**: fee APR nyata dan selisih LP vs hold — keduanya butuh **harga masuk dan
    keluar posisi**, bukan cuma kuantitas token. Karena itu selalu ditulis "belum diketahui",
    tidak ditebak. Inilah kesalahan yang membuat klaim LP dari media sosial tidak bisa diaudit:
    mereka menyebut % tanpa pernah menyebut jendela waktu, fee tier, atau pembanding hold.
    """
    liq = _angka((p.get("liquidity") or {}).get("usd"))
    v24 = _angka((p.get("volume") or {}).get("h24"))
    v6 = _angka((p.get("volume") or {}).get("h6"))
    pc = p.get("priceChange") or {}
    chg24, chg6 = _angka(pc.get("h24")), _angka(pc.get("h6"))
    umur_jam: float | None = None
    if p.get("pairCreatedAt"):
        try:
            umur_jam = round((time.time() - float(p["pairCreatedAt"]) / 1000) / 3600, 1)
        except (TypeError, ValueError):
            umur_jam = None
    turnover = round(v24 / liq, 3) if (liq and v24 and liq > 0) else None

    catatan: list[str] = []
    if liq is None or v24 is None:
        kualitas = "belum-cukup-data"
        catatan.append("likuiditas atau volume tidak tersedia")
    elif liq < 20_000:
        kualitas = "tipis"
        catatan.append(f"likuiditas ${liq:,.0f} < $20.000 — slippage keluar besar")
    elif turnover is not None and turnover < 0.02:
        # Likuiditas besar tapi hampir tak ada transaksi = pool terbengkalai.
        # LP di sini memarkir modal tanpa menghasilkan fee sama sekali.
        kualitas = "pool-mati"
        catatan.append(
            f"turnover {turnover}x — likuiditas ${liq:,.0f} tapi hampir tak ada transaksi; "
            "modal diparkir tanpa menghasilkan fee"
        )
    elif turnover is not None and turnover < 0.5:
        kualitas = "tipis"
        catatan.append(f"turnover {turnover}x — fee kecil dibanding modal yang diparkir")
    elif umur_jam is not None and umur_jam < 48:
        kualitas = "terlalu-baru"
        catatan.append(f"pool baru {umur_jam:.0f} jam — belum ada riwayat")
    else:
        kualitas = "layak-ditinjau"
    if chg24 is not None and abs(chg24) >= 30:
        catatan.append(f"harga {chg24:+.0f}% dalam 24 jam — gerak searah sebesar ini = IL besar vs hold")
    catatan.append("fee APR nyata: belum diketahui (butuh fee tier + porsi posisi di dalam range)")
    catatan.append("LP vs hold: belum diketahui (butuh harga masuk & keluar posisi, bukan kuantitas)")

    return {
        "label_pool": (p.get("labels") or [None])[0],
        "liq_usd": liq,
        "vol_24h": v24,
        "vol_6h": v6,
        "turnover_24h": turnover,
        "chg_h24": chg24,
        "chg_h6": chg6,
        "umur_jam": umur_jam,
        "kualitas": kualitas,
        "catatan": catatan,
    }


def _nilai_vol(p: dict[str, Any]) -> float:
    return _angka((p.get("volume") or {}).get("h24")) or 0.0


def pilih_pool(pairs: list[dict[str, Any]], limit: int = 6) -> list[dict[str, Any]]:
    """Buang pool tanpa volume, lalu urutkan menurun **berdasarkan volume 24 jam**.

    Kenapa volume dan bukan likuiditas: pada data nyata ada pool BONK/USDC dengan likuiditas
    $50,4 juta tetapi volume hanya $0,31/hari. Kalau diurutkan pakai likuiditas, pool terbengkalai
    itulah yang terpilih — padahal LP di sana tidak menghasilkan fee sama sekali. Fee datang dari
    transaksi, jadi volume yang jadi urutan.
    """
    sah = [p for p in pairs if p.get("pairAddress") and _nilai_vol(p) > 0]
    sah.sort(key=_nilai_vol, reverse=True)
    return sah[:limit]


def lp_cari(kata: str, limit: int = 6) -> list[dict[str, Any]]:
    """Cari pool LP lewat DEX Screener dan ukur masing-masing dengan `ukur_lp`.

    Mengembalikan daftar siap-tampil (rantai, dex, pasangan, alamat, url + hasil ukur).
    Murni baca-saja, tanpa key.
    """
    from urllib.parse import quote as _quote

    d = _get(f"/latest/dex/search?q={_quote(kata)}")
    out: list[dict[str, Any]] = []
    for p in pilih_pool(d.get("pairs") or [], limit):
        bt = (p.get("baseToken") or {}).get("symbol") or "?"
        qt = (p.get("quoteToken") or {}).get("symbol") or "?"
        out.append(
            {
                "rantai": p.get("chainId"),
                "dex": p.get("dexId"),
                "pair": f"{bt}/{qt}",
                "alamat": p.get("pairAddress"),
                "url": p.get("url"),
                **ukur_lp(p),
            }
        )
    return out


def enrich(pairs: list[tuple[str, str]]) -> dict[str, dict[str, Any]]:
    """Statistik per token {(chain, address): {...}}. Batch per chain (maks 30 alamat)."""
    by_chain: dict[str, list[str]] = {}
    for chain, addr in pairs:
        ds = CHAIN_MAP.get(chain)
        if not ds or not addr:
            continue
        by_chain.setdefault(ds, [])
        if addr not in by_chain[ds] and len(by_chain[ds]) < 30:
            by_chain[ds].append(addr)
    out: dict[str, dict[str, Any]] = {}
    for ds, addrs in by_chain.items():
        try:
            data = _get(f"/tokens/v1/{ds}/{','.join(addrs)}")
        except Exception:
            continue
        for p in data or []:
            base = p.get("baseToken") or {}
            addr = base.get("address") or ""
            tx = p.get("txns") or {}
            m5 = tx.get("m5") or {}
            h1 = tx.get("h1") or {}
            pc = p.get("priceChange") or {}
            liq = (p.get("liquidity") or {}).get("usd")
            b5, s5 = int(m5.get("buys") or 0), int(m5.get("sells") or 0)
            b1, s1 = int(h1.get("buys") or 0), int(h1.get("sells") or 0)
            # cari chain internal balik dari ds
            inv = next((k for k, v in CHAIN_MAP.items() if v == ds), ds)
            out[f"{inv}:{addr}"] = {
                "symbol": base.get("symbol"),
                "price_usd": p.get("priceUsd"),
                "liq_usd": liq,
                "chg_h24": pc.get("h24"),
                "buys_m5": b5,
                "sells_m5": s5,
                "bs_m5": round(b5 / s5, 2) if s5 else (float(b5) if b5 else None),
                "buys_h1": b1,
                "sells_h1": s1,
                "bs_h1": round(b1 / s1, 2) if s1 else (float(b1) if b1 else None),
                "url": p.get("url"),
                "dex": p.get("dexId"),
                "lp": ukur_lp(p),
            }
    return out


def snapshot(state_dir: Path, shadow: list[dict[str, Any]]) -> dict[str, Any]:
    """Satu panggilan untuk build_snapshot: cache dulu, fetch kalau basi."""
    cached = load_cache(state_dir)
    if cached is not None:
        return cached
    pairs = []
    for r in (shadow or [])[-15:]:
        key = str(r.get("key") or "")
        if ":" in key:
            c, a = key.split(":", 1)
            pairs.append((c, a))
    out = {"boosts": boosts_top(10), "enrich": enrich(pairs), "metas": metas_overlap(shadow)}
    save_cache(state_dir, out)
    return out


def metas_trending(limit: int = 8) -> list[dict[str, Any]]:
    """Narasi panas — murni discovery (lihat Narrative Labs: narasi = perhatian)."""
    try:
        data = _get("/metas/trending/v1")
    except Exception:
        return []
    out = []
    for m in (data or [])[:limit]:
        chg = m.get("marketCapChange") or {}
        out.append(
            {
                "name": m.get("name"),
                "slug": m.get("slug"),
                "marketCap": m.get("marketCap"),
                "volume": m.get("volume"),
                "chg_h24": chg.get("h24"),
                "chg_h1": chg.get("h1"),
            }
        )
    return out


def metas_overlap(shadow: list[dict[str, Any]], top: int = 5) -> dict[str, Any]:
    """Narasi mana yang memuat token shadow kita (irisan alamat on-chain).

    Jujur: irisan alamat ≠ konfirmasi entry — cuma tahu kita dan narasi
    sedang melihat token yang sama.
    """
    metas = metas_trending(8)
    shadow_addr = set()
    for r in shadow or []:
        key = str(r.get("key") or "")
        if ":" in key:
            shadow_addr.add(key.split(":", 1)[1].lower())
    rows = []
    for m in metas[:top]:
        slug = m.get("slug") or ""
        addrs: set[str] = set()
        try:
            detail = _get(f"/metas/meta/v1/{slug}")
            for p in (detail.get("pairs") or [])[:50]:
                base = (p.get("baseToken") or {}).get("address") or ""
                if base:
                    addrs.add(base.lower())
        except Exception:
            pass
        hit = sorted(a for a in addrs if a in shadow_addr)
        rows.append({**m, "overlap": len(hit), "overlap_hit": hit[:5]})
    return {"metas": rows}
