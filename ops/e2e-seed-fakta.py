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


def _kandidat_crypto() -> list[dict]:
    """`snapshot/kandidat`: hasil pemindaian SMC crypto — sumber `_crypto()`.

    `_crypto()` di market_signal.py membaca fakta INI (bukan `crypto_sinyal`),
    dan `_waktu_kandidat()` mengambil `dibuat_pada` dari kunci `ts`. Tanpa `ts`
    sinyal crypto muncul tanpa keterangan kapan dibuat.

    Field disalin dari prod (snapshot/kandidat, 8 kandidat, tier SKIP semua).
    Di sini sengaja dibuat satu STANDAR yang lolos gate, supaya jalur "lolos" ikut
    teruji — di prod semua SKIP sehingga cabang itu tidak pernah dieksekusi.
    """
    from datetime import UTC, datetime, timedelta

    kini = datetime.now(UTC).replace(microsecond=0)

    def rules(lolos: bool) -> list[dict]:
        pola = [
            ("mtf_alignment", True, False, "4H+1H searah"),
            ("poi_valid", lolos, True, "entry di dalam POI swing"),
            ("freshness", True, True, "harga masih dekat POI"),
            ("sl_distance", True, True, "SL 1.04% dari entry"),
            ("rr_min", lolos, True, "RR >= 1.5"),
        ]
        return [
            {"rule": n, "ok": ok, "hard": hard, "reason": rs}
            for n, ok, hard, rs in pola
        ]

    return [
        {
            "pair": "SOLUSDT",
            "direction": "SHORT",
            "ts": (kini - timedelta(minutes=18)).isoformat(),
            "mode": "PAPER",
            "tier": "STANDAR",
            "strategy": "smc_pullback",
            "strategy_version": "seed-e2e",
            "allowed": True,
            "entry": 92.42,
            "sl": 95.4558,
            "tp1": 89.3842,
            "risk_pct": 0.5,
            "atr_pct": 1.84,
            "poi_low": 92.10,
            "poi_high": 92.88,
            "harga_keputusan": 92.42,
            "filter_funding_oi": "netral",
            "agents": ["smc"],
            "rules": rules(True),
        },
        {
            "pair": "CRVUSDT",
            "direction": "LONG",
            "ts": (kini - timedelta(minutes=41)).isoformat(),
            "mode": "PAPER",
            "tier": "SKIP",
            "strategy": "smc_pullback",
            "strategy_version": "seed-e2e",
            "allowed": False,
            "entry": 0.2664,
            "sl": 0.26918,
            "tp1": 0.26362,
            "risk_pct": 0.5,
            "atr_pct": 0.92,
            "poi_low": 0.2661336,
            "poi_high": 0.2666664,
            "harga_keputusan": 0.2664,
            "filter_funding_oi": "netral",
            "agents": ["smc"],
            "rules": rules(False),
        },
    ]


def _deret_ekuitas_forex() -> list[dict]:
    """Deret `mt5_snapshot` untuk /jurnal?market=forex.

    `journal_performance()` (lokal.py) menghitung kurva dari fakta `mt5_snapshot`
    dengan `key=snapshot_key(account)` → "ringkas" bila tanpa akun. Tanpa deret ini
    endpoint membalas 503 "Belum ada riwayat ekuitas", dan kartu "Drawdown maks"
    tidak dirender karena syaratnya `kinerja.n_titik > 0`.

    Bentuk mengikuti prod (equity, balance, net_pnl_today_usd, account, currency).
    Angka dibuat naik-turun supaya drawdown benar-benar terhitung, bukan nol palsu.
    """
    from datetime import UTC, datetime, timedelta

    kini = datetime.now(UTC).replace(microsecond=0)
    # 30 titik, 1 jam sekali, mundur dari sekarang.
    jalur = [
        10.00, 10.12, 10.05, 10.31, 10.44, 10.20, 10.02, 9.88, 10.06, 10.27,
        10.51, 10.38, 10.62, 10.80, 10.55, 10.41, 10.19, 10.33, 10.67, 10.92,
        11.04, 10.86, 10.71, 10.95, 11.20, 11.08, 10.88, 11.02, 11.19, 11.34,
    ]
    return [
        {
            "kind": "mt5_snapshot",
            "key": "ringkas",
            "value_json": {
                "account": "e2e-uji",
                "broker": "seed e2e",
                "currency": "USD",
                "equity": eq,
                "balance": eq,
                "margin": 0.0,
                "posisi": 0,
                "pending": 0,
                "cent_factor": 1.0,
                "net_pnl_today_usd": round(eq - jalur[0], 2),
            },
            "observed_at": kini - timedelta(hours=len(jalur) - i),
            "source": "seed-e2e",
            "ttl_s": 86_400,
            "hash": "",
        }
        for i, eq in enumerate(jalur)
    ]


def _idx() -> dict:
    # IDX memakai kunci `pakem` (bukan `tingkat`) — dibaca keduanya oleh API.
    s = _setup("Bandarmologi", n=27, winrate=48.1, mean_r=0.07, tingkat="TUNING")
    s["pakem"] = "TUNING"
    return {"tersedia": True, "per_setup": {"bandarmologi": s}}


def _sinyal(pasangan: list[tuple[str, str, float, float]]) -> dict:
    """Blok `forex_sinyal`/`crypto_sinyal`: {"entries": [...]} + metadata sumber.

    Bentuk mengikuti prod: tiap entri punya pair, arah, tf, sl, tp1, tp2, r_r.
    `waktu` WAJIB ada: `_dari_fakta_sinyal` (market_signal.py) membaca
    `waktu`/`dibuat`/`ditutup` untuk mengisi `dibuat_pada` — tanpa itu Home tidak
    bisa menampilkan kesegaran sinyal dan test timestamp gagal.
    `alasan=None` menandakan sinyal tersedia (bukan kosong karena masalah).
    """
    from datetime import UTC, datetime, timedelta

    kini = datetime.now(UTC).replace(microsecond=0)
    entries = [
        {
            "pair": pair,
            "arah": arah,
            "tf": "1H",
            "sl": sl,
            "tp1": round(sl * 0.997, 2),
            "tp2": round(sl * 0.994, 2),
            "r_r": rr,
            "waktu": (kini - timedelta(minutes=22 + i * 7)).isoformat(),
            "status": "open",
        }
        for i, (pair, arah, sl, rr) in enumerate(pasangan)
    ]
    return {
        "alasan": None,
        "entries": entries,
        "sumber": "seed-e2e",
        "suplai": {"mesin": "seed e2e", "catatan": "data uji, bukan sinyal nyata"},
    }


def _posisi_crypto() -> list[dict]:
    """`snapshot/posisi`: daftar posisi crypto terbuka (bentuk dari prod)."""
    return [
        {
            "pair": "SOLUSDT",
            "direction": "SHORT",
            "status": "open",
            "entry": 92.42,
            "stop": 95.45580386,
            "stop_init": 95.45580386,
            "tp1": 89.38419614,
            "tp2": 89.38419614,
            "size_usd": 28.7,
            "cost_bps": 20.0,
            "strategi": "seed-e2e",
            "source": "paper-crypto",
            "signal_id": "#SIGSEED0001",
            "opened_at": "2026-11-03T07:04:09+07:00",
            "note": "data uji e2e; bukan posisi nyata",
        }
    ]


def _ledger_crypto() -> dict:
    """`snapshot/ledger`: ringkasan trade tertutup + beberapa baris terakhir."""
    terakhir = [
        {
            "pair": pair,
            "direction": arah,
            "status": status,
            "r": r,
            "fee_usd": 0.15,
            "cost_bps": 20.0,
            "strategi": "seed-e2e",
            "source": "paper-crypto",
            "signal_id": f"#SIGSEED{1000 + i}",
            "closed_at": f"2026-11-0{i + 1}T03:22:44+07:00",
            "note": status.lower(),
        }
        for i, (pair, arah, status, r) in enumerate(
            [
                ("APTUSDT", "SHORT", "closed_TP2", 1.0),
                ("BTCUSDT", "LONG", "closed_TP1", 0.5),
                ("ETHUSDT", "LONG", "closed_SL", -1.0),
            ]
        )
    ]
    return {"trade": 3, "total_r": 0.5, "terakhir": terakhir}


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
        # Panel "Posisi Terbuka" (/crypto?sub=eksekusi) dan ringkasan ledger.
        Fact(
            kind=a.kind,
            key="posisi",
            value_json=_posisi_crypto(),
            source="seed-e2e",
            observed_at=kini,
            ttl_s=86_400,
            hash="",
        ),
        Fact(
            kind=a.kind,
            key="ledger",
            value_json=_ledger_crypto(),
            source="seed-e2e",
            observed_at=kini,
            ttl_s=86_400,
            hash="",
        ),
        # Sumber `_crypto()` — bukan crypto_sinyal. `ts` = dibuat_pada sinyal crypto.
        Fact(
            kind=a.kind,
            key="kandidat",
            value_json=_kandidat_crypto(),
            source="seed-e2e",
            observed_at=kini,
            ttl_s=86_400,
            hash="",
        ),
        # Akun OKX: `kind` berbeda ("okx.positions"), key "ringkas".
        Fact(
            kind="okx.positions",
            key="ringkas",
            value_json={
                "jumlah": 1,
                "posisi": [
                    {
                        "instId": "ARB-USDT-SWAP",
                        "posSide": "short",
                        "pos": "18.8",
                        "avgPx": "0.15921",
                        "lever": "3",
                        "mgnMode": "cross",
                        "upl": "0.8742",
                    }
                ],
            },
            source="seed-e2e",
            observed_at=kini,
            ttl_s=900,
            hash="",
        ),
        # Deret ekuitas forex: tanpa ini /journal/performance balas 503 dan kartu
        # "Drawdown maks" tidak dirender (syaratnya n_titik > 0).
        *[
            Fact(
                kind=d["kind"],
                key=d["key"],
                value_json=d["value_json"],
                source=d["source"],
                observed_at=d["observed_at"],
                ttl_s=d["ttl_s"],
                hash=d["hash"],
            )
            for d in _deret_ekuitas_forex()
        ],
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
