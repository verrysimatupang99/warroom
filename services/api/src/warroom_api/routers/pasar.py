"""Router pasar — gate/evaluate, sinyal per pasar, verdict, ringkas pasar.

Diekstrak dari app.py (P1-2, langkah 3). Refactor murni: path, status kode,
dan auth dependency tidak berubah.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from warroom_core.db import User, session_scope
from warroom_core.gate import DEFAULT_CI, DEFAULT_MIN_N, GateInput, evaluate

from warroom_api import auth
from warroom_api.areas import latest_facts, split_poly_terverifikasi

router = APIRouter()


class GateBody(BaseModel):
    n: int
    win: int
    be: float
    ci: float = DEFAULT_CI
    min_n: int = DEFAULT_MIN_N
    split: str | None = None
    # Koreksi klaster (design effect); >= 1. Lihat gate.evaluate.
    deff: float = 1.0
    label: str = "konfirmasi"
    subject: str = ""
    rule: str = ""


@router.post("/api/v1/gate/evaluate")
def gate_evaluate(body: GateBody, user: Annotated[User, Depends(auth.current_user)]) -> dict[str, Any]:
    # "frozen:<id>" hanya label sampai isi berkasnya dicek (sha256 via
    # splits.verifikasi: id terdaftar DAN berkas cocok). Id terdaftar tapi
    # berkas berubah/hilang = 422 — bukan lolos. Tanpa ini, siapa pun bisa
    # memakai split basi SETELAH melihat hasil — gate jadi upacara tanpa isi
    # (ADR-003, P1; diperketat verifikasi hash 12 Okt).
    if body.split and body.split.startswith("frozen:"):
        from warroom_core import splits as _splits

        with session_scope() as s:
            if _splits.split_untuk_gate(s, body.split) is None:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "code": "split_tidak_terdaftar",
                        "message": (
                            "split beku tidak terdaftar di platform — bekukan dulu "
                            "via POST /api/v1/datasets/freeze, jangan mengarang id"
                        ),
                        "split": body.split,
                    },
                )
            hasil_verifikasi = _splits.verifikasi(s, body.split)
            if not hasil_verifikasi.get("cocok"):
                raise HTTPException(
                    status_code=422,
                    detail={
                        "code": "split_tidak_cocok",
                        "message": (
                            "split beku tidak cocok dengan yang dibekukan "
                            "(berkas berubah/hilang sejak dibekukan) — bekukan ulang "
                            "via POST /api/v1/datasets/freeze"
                        ),
                        "split": body.split,
                        "berubah": hasil_verifikasi.get("berubah"),
                        "hilang": hasil_verifikasi.get("hilang"),
                    },
                )
    r = evaluate(
        GateInput(
            n=body.n,
            win=body.win,
            be=body.be,
            ci=body.ci,
            min_n=body.min_n,
            split=body.split,
            deff=body.deff,
            label=body.label,  # type: ignore[arg-type]
            subject=body.subject,
            rule=body.rule,
        )
    )
    return {
        "verdict": r.verdict,
        "reason": r.reason,
        "ci_low": r.ci_low,
        "ci_high": r.ci_high,
        "win_rate": r.win_rate,
        "be": r.be,
        "n": r.n,
        "required_n": r.required_n,
        "policy_version": r.policy_version,
        # Kebijakan yang dipakai — UI wajib melabeli hasil dengan ini (90% vs 95%+deff).
        "ci": r.ci,
        "deff": r.deff,
        "notes": r.notes,
        # Pakem bukti (6 Okt): kematangan sampel pada n efektif — terpisah dari verdict
        # supaya UI tidak membaca "n besar" sebagai "hampir lolos".
        "pakem": r.pakem,
        "n_efektif": r.n_efektif,
    }


# --- sinyal terbaik per pasar (Home, 5 Okt 2026) -----------------------------------
# Satu kontrak untuk seluruh UI baru: semua pasar dinormalkan ke bentuk yang sama,
# lengkap dengan status verifikasi (klaim eksplorasi tidak boleh terlihat seperti edge).


@router.get("/api/v1/sinyal/per-pasar")
def signals_per_market(
    user: Annotated[User, Depends(auth.current_user)],
    maks: int = Query(3, ge=1, le=20, description="sinyal terbaik per pasar (Home: 3)"),
) -> dict[str, Any]:
    """Sinyal per pasar untuk Home: maks `maks` terbaik + status jujur per pasar.

    `status_data` tegas: **ada** (ada sinyal) · **kosong** (mesin hidup, tak ada
    setup yang cocok — ini hasil kerja sistem) · **gagal** (sumber tak terbaca /
    mesin mati — JANGAN pernah ditulis "tidak ada sinyal").
    """
    from warroom_core.market_signal import best_signal_per_market, signals_per_market

    with session_scope() as s:
        terverifikasi = split_poly_terverifikasi(s)
        daftar = signals_per_market(s, maks=maks, split_terverifikasi=terverifikasi)
        rows = best_signal_per_market(s, split_terverifikasi=terverifikasi)
    return {
        "sinyal": [r.to_dict() for r in rows],          # bentuk lama (kompatibel)
        "pasar": [d.to_dict() for d in daftar],          # bentuk baru (Home)
        "count": len(rows),
        "ada": sum(1 for r in rows if r.ada),
    }


@router.get("/api/v1/verdict")
def verdict_semua(user: Annotated[User, Depends(auth.current_user)]) -> dict[str, Any]:
    """Verdict KANONIK per pasar — satu sumber keputusan untuk seluruh UI.

    Audit QA 7 Okt: UI tidak boleh menyusun verdict sendiri dari beberapa angka
    (kartu bilang "EDGE TERBUKTI", gate bilang "split belum beku"). Backend
    mengeluarkan lima state + headline + alasan blokir; UI hanya merender.
    """
    from warroom_core.verdict import all_market_verdicts

    with session_scope() as s:
        rows = all_market_verdicts(s, split_terverifikasi=split_poly_terverifikasi(s))
    return {
        "verdict": [v.to_dict() for v in rows],
        "dibuat": datetime.now(UTC).isoformat(),
        "aturan": {
            "promosi_min_bukti": "PRELIMINARY",
            "wajib_split_beku": ["polymarket"],
            "syarat_tambahan": "expectancy > 0 dan PnL kumulatif > 0",
        },
    }


@router.get("/api/v1/pasar/ringkas")
def pasar_ringkas(user: Annotated[User, Depends(auth.current_user)]) -> dict[str, Any]:
    """Ringkas akurasi+PnL per market untuk Home (angka apa adanya, tanpa hitung ulang).

    Dibaca dari fakta `snapshot/pasar_akurasi` + `snapshot/idx_akurasi` — mesin yang
    sama dengan halaman per-area, supaya Home tidak pernah berbeda dari halaman detail.
    Pasar yang belum punya angka TIDAK diisi nol: `tersedia=False` + alasan.
    """
    with session_scope() as s:
        fakta = latest_facts(s)
        pasar_akurasi = fakta.get("pasar_akurasi")
        idx_akurasi = fakta.get("idx_akurasi")

    # Label manusia untuk kolom tabel — satu sumber, tidak diulang di UI.
    LABEL_PASAR = {
        "crypto": "Crypto (SMC)",
        "idx": "IDX",
        "forex": "Forex",
        "gmgn": "GMGN / LP",
        "lp": "LP / Yield",
        "polymarket": "Polymarket",
        "sistem": "Sistem",
    }

    def _baris(nama: str, v: Any) -> dict[str, Any]:
        per_setup = (v or {}).get("per_setup") or {}
        kunci_seri, seri = max(
            per_setup.items(),
            key=lambda kv: (kv[1].get("n") or 0),
            default=(None, None),
        )
        seri = seri or {}
        return {
            "pasar": nama,
            "label": LABEL_PASAR.get(nama, nama),
            "tersedia": bool((v or {}).get("tersedia")),
            "alasan": (v or {}).get("alasan"),
            "n": seri.get("n"),
            "n_hari": seri.get("n_hari"),
            "winrate_pct": seri.get("winrate_pct"),
            "mean_r": seri.get("mean_r"),
            "total_r": seri.get("total_r"),
            "pnl_usd": seri.get("total_pnl_usd", seri.get("pnl_usd")),
            # IDX memakai nama kunci `pakem`; pasar lain `tingkat` — dibaca keduanya.
            "tingkat": seri.get("tingkat") or seri.get("pakem"),
            "setup": seri.get("nama") or kunci_seri,
            "jumlah_setup": len(per_setup),
            # Blok BUKTI (audit QA putaran 3): tujuh jawaban untuk halaman
            # Performance & Proof — closed trades, WR, total R, PnL, drawdown,
            # biaya, periode + denominator. Diterbitkan mesin (pasar.py), API hanya
            # meneruskan; kalau mesin belum menghitungnya, jangan dikarang di sini.
            "bukti": (v or {}).get("bukti"),
        }

    pa = (pasar_akurasi.value_json if pasar_akurasi else {}) or {}
    pembagian = pa.get("pasar") or {}
    ringkas = {
        "crypto": _baris("crypto", pembagian.get("crypto")),
        "idx": _baris("idx", idx_akurasi.value_json if idx_akurasi else {}),
        "forex": _baris("forex", pembagian.get("forex")),
        "gmgn": _baris("gmgn", pembagian.get("gmgn")),
        "polymarket": _baris("polymarket", pembagian.get("polymarket")),
    }
    return {
        "pasar": ringkas,
        "standar": pa.get("standar"),
        "sumber": "fakta snapshot pasar_akurasi + idx_akurasi (mesin pasar.py)",
    }
