"""Aturan exit LP Arc — pengganti `~/gmgn-scan/lp_paper.py::aturan_keluar` yang hilang.

Konteks (temuan 10 Okt): folder `~/gmgn-scan/` sudah tidak ada, sehingga
`packages/live-trading/tests/test_ambil.py` (7 tes) gagal dengan FileNotFoundError.
Fungsi ini merekonstruksi perilaku yang diuji — bukan karangan baru:

- pool hilang (row None) → KELUAR
- dump 5m ≤ -8% → KELUAR (sama seperti gate `score_pool` di `lp_mark.py`)
- IL 50/50 < -5% → KELUAR "IL"
- V/L < 2.0 → KELUAR "layu" (sama seperti gate `score_pool`)
- fee taksiran ≥ 5% notional → KELUAR "target"
- umur > 14 hari → KELUAR "umur"
- selain itu → TAHAN

Rumus fee & IL sama dengan `lp_mark.py` (satu kebenaran):
fee = notional × vl_now × tier × hari; IL = 2√r/(1+r) − 1.
"""

from __future__ import annotations

from typing import Any

from .lp_mark import fee_terkumpul, il_5050

FEE_TIER = 0.01
TARGET_PCT = 5.0
VL_LAYU = 2.0
IL_DALAM_PCT = -5.0
DUMP_5M_PCT = -8.0
UMUR_LEWAT_HARI = 14.0

__all__ = ["aturan_keluar"]


def aturan_keluar(
    pos: dict[str, Any],
    row: dict[str, Any] | None,
    kini: float,
) -> tuple[str, str]:
    """Tentukan KELUAR/TAHAN + alasan. Tak pernah menebak harga yang hilang."""
    if row is None:
        return "KELUAR", "pool hilang — data pasar tak terbaca"

    masuk = float(pos.get("entry_price") or 0)
    notional = float(pos.get("notional_usd") or 0)
    masuk_ts = float(pos.get("entry_ts") or 0)
    vl_masuk = float(pos.get("vl_at_entry") or 0)
    _ = vl_masuk  # dokumentasi: ambang layu absolut (VL_LAYU), bukan relatif entry

    harga = float(row.get("price") or 0)
    vl = float(row.get("fee_ratio") or 0)
    lima = row.get("price_5m")
    lima_f = float(lima) if lima is not None else 0.0

    hari = max(0.0, (kini - masuk_ts) / 86400.0) if masuk_ts else 0.0

    if lima_f <= DUMP_5M_PCT:
        return "KELUAR", f"dump 5m {lima_f:.1f}% ≤ -8%"

    if masuk > 0 and harga > 0:
        il_pct = il_5050(harga / masuk) * 100.0
        if il_pct <= IL_DALAM_PCT:
            return "KELUAR", f"IL {il_pct:.1f}% dalam (≤ -5%)"

    if vl < VL_LAYU:
        return "KELUAR", f"layu — V/L {vl:.2f} < 2.0"

    if notional > 0 and hari > 0:
        fee = fee_terkumpul(notional_usd=notional, vl=vl, fee_tier=FEE_TIER, hari=hari)
        if fee >= notional * TARGET_PCT / 100.0:
            return "KELUAR", f"target +{TARGET_PCT:.0f}% kena (fee taksiran ${fee:,.2f})"

    if hari > UMUR_LEWAT_HARI:
        return "KELUAR", f"umur {hari:.1f} hari lewat batas {UMUR_LEWAT_HARI:.0f} hari"

    return "TAHAN", "sehat — tak ada pemicu exit"
