#!/usr/bin/env python3
"""Semai fakta minimum supaya suite e2e punya data nyata, bukan DB kosong.

Kenapa ada: 70 dari 122 test e2e gagal di CI bukan karena UI rusak, tapi karena
mereka ditulis untuk host dev yang sudah berisi fakta pasar. DB CI baru hasil
migrasi = kosong. Menyemai data di sini membuat test menguji **perilaku UI**,
bukan menguji keberadaan data di DB.

Prinsip:
- data disemai lewat fungsi domain yang sama dengan produksi (bukan INSERT manual
  yang bisa menyimpang dari skema);
- hanya fakta bentuk "snapshot" yang dibaca Home / halaman pasar;
- idempoten: dijalankan ulang menimpa versi pada detik yang sama;
- menolak jalan bila DB bukan loopback (jangan menyemai ke produksi).

Bentuk fakta mengikuti `services/api/src/warroom_api/routers/pasar.py`:
`pasar_akurasi` menyimpan `{"tersedia": bool, "pasar": {<nama>: {...per_setup}}}`,
dan tiap pasar berisi `per_setup: {<nama_setup>: {n, n_hari, winrate_pct, ...}}`.
"""

from __future__ import annotations

import argparse
import os
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from warroom_core.db.models import Fact

LOOPBACK = {"127.0.0.1", "localhost", "::1"}


def _setup(nama: str, *, n: int, winrate: float, mean_r: float, tingkat: str) -> dict:
    return {
        "nama": nama,
        "n": n,
        "n_hari": 30,
        "winrate_pct": winrate,
        "mean_r": mean_r,
        "total_r": round(mean_r * n, 3),
        "pnl_usd": round(mean_r * n * 10, 2),
        "tingkat": tingkat,
    }


def _per_pasar() -> dict[str, dict]:
    """Satu pasar per kunci yang dibaca Home, plus blok bukti secukupnya."""
    return {
        "crypto": {
            "tersedia": True,
            "per_setup": {
                "smc_bos": _setup("SMC BOS", n=42, winrate=57.1, mean_r=0.31, tingkat="PRELIMINARY"),
                "smc_fvg": _setup("SMC FVG", n=18, winrate=50.0, mean_r=0.04, tingkat="INSUFFICIENT"),
            },
        },
        "forex": {
            "tersedia": True,
            "per_setup": {
                "golden_pullback": _setup("Golden Pullback", n=31, winrate=45.2, mean_r=-0.11,
                                          tingkat="PRELIMINARY"),
            },
        },
        "gmgn": {
            "tersedia": True,
            "per_setup": {
                "lp_momentum": _setup("LP Momentum", n=55, winrate=52.7, mean_r=0.18, tingkat="DIRECTIONAL"),
            },
        },
        "polymarket": {
            "tersedia": True,
            "per_setup": {
                "btc_5m_momentum": _setup("BTC 5m Momentum", n=24, winrate=54.2, mean_r=0.22,
                                          tingkat="PRELIMINARY"),
            },
        },
        "lp": {
            "tersedia": True,
            "per_setup": {
                "lp_yield": _setup("LP Yield", n=12, winrate=50.0, mean_r=0.05, tingkat="INSUFFICIENT"),
            },
        },
    }


def _idx() -> dict:
    # IDX memakai kunci `pakem` (bukan `tingkat`) — dibaca keduanya oleh API.
    s = _setup("Bandarmologi", n=27, winrate=48.1, mean_r=0.07, tingkat="TUNING")
    s["pakem"] = "TUNING"
    return {"tersedia": True, "per_setup": {"bandarmologi": s}}


def _sinyal(pasangan: list[tuple[str, str, float, float]]) -> dict:
    """Blok `forex_sinyal`/`crypto_sinyal`: {"entries": [...]} + metadata sumber.

    Bentuk mengikuti prod: tiap entri punya pair, arah, tf, sl, tp1, tp2, r_r.
    `alasan=None` menandakan sinyal tersedia (bukan kosong karena masalah).
    """
    entries = [
        {
            "pair": pair,
            "arah": arah,
            "tf": "1H",
            "sl": sl,
            "tp1": round(sl * 0.997, 2),
            "tp2": round(sl * 0.994, 2),
            "r_r": rr,
        }
        for pair, arah, sl, rr in pasangan
    ]
    return {
        "alasan": None,
        "entries": entries,
        "sumber": "seed-e2e",
        "suplai": {"mesin": "seed e2e", "catatan": "data uji, bukan sinyal nyata"},
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Semai fakta minimum untuk suite e2e.")
    # Bentuk fakta produksi: kind="snapshot", key=<nama> (dibaca `latest_facts(s, kind="snapshot")`
    # di areas.py, yang mengelompokkan per KOLOM key, bukan kind).
    p.add_argument("--kind", default="snapshot")
    a = p.parse_args()

    db_url = os.environ.get("WARROOM_DB_URL", "")
    if not db_url:
        raise SystemExit("DITOLAK: WARROOM_DB_URL tidak diset.")
    host = urlparse(db_url).hostname or ""
    if host not in LOOPBACK:
        raise SystemExit(f"DITOLAK: DB non-loopback ({host!r}) — penyemaian hanya untuk DB tes.")

    kini = datetime.now(UTC).replace(microsecond=0)
    baris = [
        Fact(
            kind=a.kind,
            key="pasar_akurasi",
            value_json={"tersedia": True, "pasar": _per_pasar(), "standar": {"min_n": 30, "ci": 0.90}},
            source="seed-e2e",
            observed_at=kini,
            ttl_s=86_400,
            hash="",
        ),
        Fact(
            kind=a.kind,
            key="idx_akurasi",
            value_json=_idx(),
            source="seed-e2e",
            observed_at=kini,
            ttl_s=86_400,
            hash="",
        ),
        # Penanda segar agar badge "segar/basi" punya sesuatu untuk dibaca.
        Fact(
            kind=a.kind,
            key="dibuat",
            value_json={"dibuat": (kini - timedelta(minutes=2)).isoformat(), "sumber": "seed-e2e"},
            source="seed-e2e",
            observed_at=kini,
            ttl_s=3_600,
            hash="",
        ),
        # Sinyal mesin per pasar: halaman /forex & panel sinyal Home membacanya.
        Fact(
            kind=a.kind,
            key="forex_sinyal",
            value_json=_sinyal(
                [("XAUUSD", "BUY", 2650.0, 1.8), ("NAS100", "SHORT", 28657.0, 1.13)]
            ),
            source="seed-e2e",
            observed_at=kini,
            ttl_s=86_400,
            hash="",
        ),
        Fact(
            kind=a.kind,
            key="crypto_sinyal",
            value_json=_sinyal([("BTCUSDT", "BUY", 96000.0, 2.1), ("ETHUSDT", "BUY", 3200.0, 1.6)]),
            source="seed-e2e",
            observed_at=kini,
            ttl_s=86_400,
            hash="",
        ),
    ]

    mesin = create_engine(db_url)
    with Session(mesin) as s:
        for f in baris:
            s.merge(f)  # idempoten pada (kind, key, observed_at)
        s.commit()

    print(f"seed e2e: {len(baris)} fakta disemai ({', '.join(f.kind for f in baris)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
