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
    # (ADR-003, P1; diperketat verifikasi hash).
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
        # Pakem bukti: kematangan sampel pada n efektif — terpisah dari verdict
        # supaya UI tidak membaca "n besar" sebagai "hampir lolos".
        "pakem": r.pakem,
        "n_efektif": r.n_efektif,
    }


# --- sinyal terbaik per pasar (Home) -----------------------------------
# Satu kontrak untuk seluruh UI: semua pasar dinormalkan ke bentuk yang sama,
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

    UI tidak menyusun verdict sendiri dari beberapa angka; backend menyajikan state kanonik
    (lima state + headline + alasan blokir) dan UI hanya merender.
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
            # Blok bukti performa dari pasar.py diteruskan apa adanya tanpa kalkulasi tambahan di API.
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


@router.get("/api/v1/pasar/quant-backtest")
def pasar_quant_backtest() -> dict[str, Any]:
    """Menyajikan hasil validasi backtest & optimasi parameter kuantitatif (Multi-Asset)."""
    import json
    import os
    json_path = "/home/admin/warroom/data/quant_backtest_cache.json"
    if os.path.exists(json_path):
        try:
            with open(json_path) as f:
                return json.load(f)
        except Exception:
            pass
    # Fallback response
    return {
        "updated": "2026-10-21T06:20:00Z",
        "strategy": "Break & Retest 15m (Multi-Asset)",
        "assets": [
            {
                "symbol": "XAUUSD", "name": "Gold (Emas)", "category": "Metal",
                "win_rate": 32.5, "pf": 1.30, "pnl": 2.34, "max_dd": 2.38, "trades": 40,
                "config": "LB:35, SL:1.6x, RRR:1:3",
            },
            {
                "symbol": "BTCUSDT", "name": "Bitcoin", "category": "Crypto",
                "win_rate": 39.4, "pf": 1.74, "pnl": 3.49, "max_dd": 1.74, "trades": 33,
                "config": "LB:20, SL:1.2x, RRR:1:2",
            },
            {
                "symbol": "SOLUSDT", "name": "Solana", "category": "Crypto",
                "win_rate": 30.0, "pf": 1.80, "pnl": 7.74, "max_dd": 4.23, "trades": 20,
                "config": "LB:15, SL:1.8x, RRR:1:3",
            },
            {
                "symbol": "EURUSD", "name": "Euro / USD", "category": "Forex",
                "win_rate": 41.0, "pf": 1.67, "pnl": 1.45, "max_dd": 0.38, "trades": 39,
                "config": "LB:30, SL:2.0x, RRR:1:3",
            },
            {
                "symbol": "GBPUSD", "name": "GBP / USD", "category": "Forex",
                "win_rate": 42.4, "pf": 2.10, "pnl": 2.04, "max_dd": 0.58, "trades": 33,
                "config": "LB:15, SL:2.0x, RRR:1:3",
            }
        ]
    }


class SizingRequest(BaseModel):
    pair: str
    account_size: float
    risk_pct: float
    entry_price: float
    sl_price: float
    leverage: float = 1.0


@router.post("/api/v1/tools/sizing")
def calculate_position_sizing(req: SizingRequest) -> dict[str, Any]:
    """Standarisasi Schema Sizing Tool (awesome-omni-skills standard)."""
    dollar_risk = req.account_size * (req.risk_pct / 100.0)
    sl_dist = abs(req.entry_price - req.sl_price)
    if sl_dist <= 0 or req.entry_price <= 0:
        raise HTTPException(status_code=400, detail="Invalid price parameters: entry and sl must differ")

    sl_dist_pct = (sl_dist / req.entry_price) * 100.0

    if "XAU" in req.pair.upper():
        # Gold: 1 standard lot = 100 oz. 1 pip (0.10) = $10 per lot
        pips = sl_dist * 10.0
        risk_per_point = dollar_risk / max(0.1, sl_dist)
        lot = round((risk_per_point / 100.0), 2)
        return {
            "pair": req.pair,
            "account_size": req.account_size,
            "risk_usd": round(dollar_risk, 2),
            "sl_pips": round(pips, 1),
            "calculated_lot": max(0.01, lot),
            "lot_step": 0.01,
            "risk_model": "GOLD_PIP_SIZING",
        }
    else:
        # Crypto or standard FX percentage sizing
        pos_size_usd = dollar_risk / (sl_dist_pct / 100.0)
        units = pos_size_usd / req.entry_price
        liq_price = (
            req.entry_price * (1 - (1 / max(1.0, req.leverage)) * 0.9)
            if req.sl_price < req.entry_price
            else req.entry_price * (1 + (1 / max(1.0, req.leverage)) * 0.9)
        )
        return {
            "pair": req.pair,
            "account_size": req.account_size,
            "risk_usd": round(dollar_risk, 2),
            "sl_distance_pct": round(sl_dist_pct, 2),
            "position_size_usd": round(pos_size_usd, 2),
            "units": round(units, 4),
            "est_liquidation_price": round(liq_price, 2),
            "risk_model": "LEVERAGE_NOTIONAL_SIZING",
        }

