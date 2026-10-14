"""Mark LP — nilai posisi LP paper dari **data pasar nyata**, bukan karangan.

Kenapa modul ini ada: `lp_paper.py` (di `~/gmgn-scan`) menaksir fee dari
`V/L × fee_tier × hari` dan IL dari rasio harga saja. Dua lubangnya:

1. **Harga bisa hilang** → posisi jadi "pool missing" tanpa angka.
2. **Hasil tidak pernah dibandingkan dengan hold** dan tidak pernah dinilai
   terhadap pakem bukti, jadi tak ada cara bilang "sudah terbukti" atau belum.

Modul ini:

- menarik harga & V/L **terbaru** via `gmgn-cli` (read-only, tanpa wallet);
- menghitung **fee terkumpul, IL, dan LP vs hold** dengan rumus yang sama
  seperti `lp_positions._hitung` (jangan sampai ada dua rumus berbeda);
- menulis **ledger per periode** (`state/lp_ledger.jsonl`) supaya PnL punya
  jejak waktu, bukan cuma angka sesaat;
- menilai hasil terhadap **pakem bukti** (n = jumlah hari, bukan jumlah baris).

Yang TIDAK dilakukan: order, swap, tanda tangan wallet, tulis ke venue.
"""

from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Any

__all__ = [
    "IL_RUMUS",
    "record_mark",
    "fee_terkumpul",
    "il_5050",
    "mark_position",
    "evaluate_pakem_lp",
    "score_pool",
]

# Rumus IL 50/50 — sama dengan lp_paper.il_5050 dan lp_positions (satu kebenaran).
IL_RUMUS = "2*sqrt(r)/(1+r) - 1, r = harga_sekarang/harga_masuk"
BPS_TAHUN = 365.0


def il_5050(price_ratio: float) -> float:
    """IL fraksi untuk pool 50/50 dari rasio harga (sekarang/masuk)."""
    if price_ratio <= 0:
        return -1.0
    return 2 * math.sqrt(price_ratio) / (1 + price_ratio) - 1


def fee_terkumpul(
    *,
    notional_usd: float,
    vl: float,
    fee_tier: float,
    hari: float,
) -> float:
    """Taksiran fee terkumpul: notional × (vol/liq) × tier × hari.

    Ini taksiran yang **wajib dilabeli taksiran**: V/L hari ini dipakai untuk
    seluruh umur posisi, padahal V/L berubah. ``fee_terkumpul_sejak`` di langkah
    berikutnya menyimpan asumsi itu agar tidak diam-diam jadi "fakta".
    """
    if notional_usd <= 0 or vl <= 0 or fee_tier <= 0 or hari <= 0:
        return 0.0
    return notional_usd * vl * fee_tier * hari


def score_pool(pool: dict[str, Any]) -> dict[str, Any]:
    """Skor kelayakan pool dari data gmgn-cli (bukan selera).

    Komponen dan bobotnya mengikuti `lp_paper.gate` supaya ambangnya konsisten:
    V/L ≥ 2 (layak) & ≥ 3 (entry), liq ≥ 50k, rug/bundler/insider/top10 aman,
    holders ≥ 1000, 5m tidak jatuh ≤ -8%. Skor hanya untuk **pengurutan**;
    keputusan lolos/tidak tetap dari gate boolean yang sama seperti lp_paper.
    """
    vl = float(pool.get("fee_ratio") or 0)
    liq = float(pool.get("liq") or 0)
    holders = int(pool.get("holders") or 0)
    five = pool.get("price_5m")
    five = float(five) if five is not None else 0.0
    rug = float(pool.get("rug") or 0)
    bundler = float(pool.get("bundler") or 0)
    insider = float(pool.get("insider") or 0)
    top10 = float(pool.get("top10") or 0)

    gagal: list[str] = []
    if vl < 2.0:
        gagal.append(f"V/L {vl:.2f} < 2")
    if liq < 50_000:
        gagal.append(f"liq {liq:,.0f} < 50k")
    if rug > 0.30:
        gagal.append("rug")
    if bundler > 0.20:
        gagal.append("bundler")
    if insider > 0.10:
        gagal.append("insider")
    if top10 > 0.25:
        gagal.append("top10")
    if holders < 1000:
        gagal.append(f"holders {holders} < 1000")
    if five < -8.0:
        gagal.append(f"5m {five:.2f} < -8")

    # Skor 0..100: V/L (log), likuiditas (log), keamanan, holder.
    def _norm(v: float, batas: float) -> float:
        if v <= 0:
            return 0.0
        return max(0.0, min(1.0, math.log10(1 + v) / math.log10(1 + batas)))

    aman = 1.0 - min(1.0, (rug / 0.30 + bundler / 0.20 + insider / 0.10 + top10 / 0.25) / 4)
    skor = round(
        45 * _norm(vl, 6) + 25 * _norm(liq, 1_000_000) + 20 * aman + 10 * _norm(holders, 20_000),
        1,
    )
    return {"skor": skor, "gagal": gagal, "lolos": not gagal}


def mark_position(
    pos: dict[str, Any],
    *,
    harga_sekarang: float,
    vl_sekarang: float,
    fee_tier: float,
    kini: float | None = None,
) -> dict[str, Any]:
    """Nilai satu posisi LP terbuka. Semua angka membawa satuan yang jelas."""
    t = time.time() if kini is None else kini
    masuk = float(pos.get("entry_price") or 0)
    notional = float(pos.get("notional_usd") or 0)
    waktu_masuk = float(pos.get("entry_ts") or t)
    hari = max(0.0, (t - waktu_masuk) / 86400.0)

    if masuk <= 0 or harga_sekarang <= 0:
        return {
            "symbol": pos.get("symbol"),
            "status": "tidak-ada-harga",
            "alasan": "harga masuk/sekarang tidak tersedia — jangan dikarang",
        }

    rasio = harga_sekarang / masuk
    il = il_5050(rasio)
    il_usd = notional * il
    fee = fee_terkumpul(notional_usd=notional, vl=vl_sekarang, fee_tier=fee_tier, hari=hari)
    pnl = fee + il_usd
    return {
        "symbol": pos.get("symbol"),
        "address": pos.get("address"),
        "status": "dinilai",
        "notional_usd": round(notional, 4),
        "harga_masuk": masuk,
        "harga_sekarang": harga_sekarang,
        "rasio_harga": round(rasio, 6),
        "umur_hari": round(hari, 3),
        "vl_sekarang": round(vl_sekarang, 4),
        "vl_masuk": pos.get("vl_at_entry"),
        "fee_tier": fee_tier,
        "fee_usd": round(fee, 6),
        "il_pct": round(il * 100, 4),
        "il_usd": round(il_usd, 6),
        "pnl_usd": round(pnl, 6),
        "pnl_pct": round(pnl / notional * 100, 4) if notional else None,
        # Pembanding hold: menahan token tanpa LP = tanpa fee, kena IL yang sama.
        "hold_usd": round(il_usd, 6),
        "lp_vs_hold_usd": round(pnl - il_usd, 6),
        "fee_apakah_taksiran": True,
        "rumus_il": IL_RUMUS,
    }


def record_mark(ledger_path: str | Path, baris: dict[str, Any]) -> None:
    """Append satu baris mark ke ledger jsonl (jejak waktu, tidak ditimpa)."""
    p = Path(ledger_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(baris, ensure_ascii=False) + "\n")


def evaluate_pakem_lp(baris_ledger: list[dict[str, Any]]):
    """Nilai jejak LP terhadap pakem bukti — n = hari unik, bukan jumlah baris.

    Satu baris ledger = satu mark (bisa beberapa per hari). Yang dinilai adalah
    **hari**, karena keputusan LP berjalan harian (fee & IL berakumulasi harian).
    """
    from .pakem import evaluate_pakem

    # Ambil mark terakhir per posisi per hari sebagai satu pengamatan harian.
    terakhir: dict[tuple[str, str], dict[str, Any]] = {}
    for b in baris_ledger:
        if b.get("status") != "dinilai":
            continue
        ts = float(b.get("ts") or 0)
        hari = time.strftime("%Y-%m-%d", time.gmtime(ts)) if ts else ""
        if not hari:
            continue
        kunci = (str(b.get("symbol")), hari)
        terakhir[kunci] = b
    pengamatan = list(terakhir.values())

    # `r` untuk pakem = pnl_pct/100 (return per hari pada hari itu).
    def _hari(b: dict[str, Any]) -> str:
        return time.strftime("%Y-%m-%d", time.gmtime(float(b.get("ts") or 0)))

    closes = [
        {"r": (b.get("pnl_pct") or 0) / 100.0, "closed_at": _hari(b)}
        for b in pengamatan
    ]
    return evaluate_pakem(closes, biaya_tercatat=True)
