"""Mark posisi LP paper dari data pasar nyata, lalu nilai terhadap pakem bukti.

Satu perintah (`lt lp-mark`) menjalankan rangkaian penuh:

1. baca posisi LP terbuka (state/lp_paper_state.json — arsip gmgn-scan);
2. tarik mark **per alamat pool** dari DexScreener (gratis, tanpa key);
3. hitung fee taksiran + IL + **LP vs hold** dengan rumus di `lp_mark.py`;
4. tulis jejak ke `state/lp_ledger.jsonl` (append-only);
5. nilai jejak itu terhadap **pakem bukti** (n = hari, bukan baris).

Yang tidak dilakukan: order, wallet, tulis ke venue. Read-only pasar.

Kenapa DexScreener padahal owner menyebut `gmgn-cli`: `gmgn-cli` mencari pool
**berdasarkan rantai + trending**, sedangkan posisi LP kita punya **alamat pool** —
`mark_pool(alamat)` langsung memanggil endpoint publik, stabil, dan tanpa kuota
berbayar. Kalau nanti `gmgn-cli` menyediakan lookup per alamat, fungsi
`_harga_pool` di bawah satu-satunya tempat yang perlu diubah.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from . import lp_mark

__all__ = ["read_positions", "compute_all", "run_lp_mark", "lp_mark_report"]

FEE_TIER_BAWAAN = 0.01  # asumsi konservatif, selalu dilabeli taksiran
STATE_LP_PAPER = "~/live-trading/state/lp_paper_state.json"
LEDGER_LP = "lp_ledger.jsonl"
MARK_LP = "lp_mark_terakhir.json"


def read_positions(path: str | Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Baca state LP paper; (meta, daftar posisi). Berkas hilang → kosong, bukan error."""
    p = Path(str(path)).expanduser()
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, []
    if not isinstance(d, dict):
        return {}, []
    return d, list(d.get("positions") or [])


def _harga_pool(alamat: str, rantai: str | None = None) -> dict[str, Any] | None:
    """Satu-satunya titik sentuh pasar — tukar di sini bila sumber mark berubah."""
    from .collectors import dexscreen

    return dexscreen.mark_pool(alamat, rantai=rantai)


def compute_all(
    *,
    state_path: str | Path,
    state_dir: str | Path,
    fee_tier: float = FEE_TIER_BAWAAN,
    tulis_ledger: bool = True,
    kini: float | None = None,
) -> dict[str, Any]:
    """Mark semua posisi terbuka; kembalikan laporan + tulis ledger bila diminta."""
    t = time.time() if kini is None else kini
    meta, posisi = read_positions(state_path)
    if not posisi:
        return {
            "status": "tidak-ada-posisi",
            "mark": [],
            "pakem": None,
            "alasan": "belum ada posisi LP paper (lp_paper) — state kosong/hilang",
        }

    ledger_path = Path(state_dir) / LEDGER_LP
    hasil: list[dict[str, Any]] = []
    for p in posisi:
        alamat = str(p.get("address") or "")
        if not alamat:
            hasil.append({"symbol": p.get("symbol"), "status": "tidak-ada-alamat"})
            continue
        pasar = _harga_pool(alamat, rantai=p.get("chain") or p.get("rantai"))
        if not pasar or not pasar.get("harga_usd"):
            hasil.append(
                {
                    "symbol": p.get("symbol"),
                    "status": "pasar-tak-terbaca",
                    "alasan": "DexScreener tidak mengembalikan harga untuk pool ini",
                }
            )
            continue
        m = lp_mark.mark_position(
            p,
            harga_sekarang=float(pasar["harga_usd"]),
            vl_sekarang=float(pasar.get("vl") or 0.0),
            fee_tier=fee_tier,
            kini=t,
        )
        m["ts"] = t
        m["sumber"] = "dexscreener"
        m["liq_usd"] = pasar.get("liq_usd")
        m["chg_h24"] = pasar.get("chg_h24")
        hasil.append(m)
        if tulis_ledger and m.get("status") == "dinilai":
            lp_mark.record_mark(ledger_path, m)

    # Pakem atas seluruh jejak (termasuk baris lama) — n = hari unik.
    pakem = None
    if ledger_path.is_file():
        baris = []
        for ln in ledger_path.read_text(encoding="utf-8").splitlines():
            try:
                baris.append(json.loads(ln))
            except json.JSONDecodeError:
                continue
        # tambahkan mark sesi ini supaya pakem mencerminkan keadaan terbaru
        baris.extend([m for m in hasil if m.get("status") == "dinilai" and m.get("ts") == t])
        hasil_pakem = lp_mark.evaluate_pakem_lp(baris)
        pakem = hasil_pakem.as_dict()

    dinilai = [m for m in hasil if m.get("status") == "dinilai"]
    ringkas = {
        "status": "ok",
        "dibuat": t,
        "fee_tier": fee_tier,
        "fee_tier_adalah_asumsi": True,
        "mark": hasil,
        "total_pnl_usd": round(sum(m.get("pnl_usd") or 0.0 for m in dinilai), 6),
        "total_vs_hold_usd": round(sum(m.get("lp_vs_hold_usd") or 0.0 for m in dinilai), 6),
        "pakem": pakem,
        "catatan": [
            "fee = notional x V/L x tier x hari — pakai V/L HARI INI untuk seluruh umur (taksiran)",
            "IL dihitung dengan rumus 50/50; pool ber-range butuh porsi in-range (belum tersedia)",
        ],
    }
    # Simpan mark terakhir supaya panel bisa menampilkan tanpa memanggil pasar lagi.
    out = Path(state_dir) / MARK_LP
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(ringkas, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass
    return ringkas


def lp_mark_report(state_dir: str | Path) -> dict[str, Any]:
    """Baca mark terakhir untuk panel (tanpa jaringan). Tidak ada → jujur 'belum ada'."""
    p = Path(state_dir) / MARK_LP
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"status": "belum-ada", "mark": [], "pakem": None}


def run_lp_mark(state_dir: str | Path, state_path: str | Path = STATE_LP_PAPER) -> dict[str, Any]:
    """Titik masuk worker/cron: mark + ledger + pakem."""
    return compute_all(state_path=state_path, state_dir=state_dir)
