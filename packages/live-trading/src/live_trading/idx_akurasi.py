"""Akurasi IDX per setup — angkat ledger mesin Tencent ke layar War Room.

Kenapa modul ini: ledger IDX (628 sinyal, 278 tuntas, grader v3) adalah bukti
paling matang yang dimiliki proyek, tapi selama ini hanya terlihat di Tencent.
Aturan produk: **semua yang tampil di web harus selaras dengan yang di balik
layar** — jadi angkanya dibaca apa adanya, lengkap dengan:

- pemisahan jujur **tuntas vs belum tuntas** (jangan campur),
- tingkat kematangan pakem pada **hari independen** (satu hari bursa = satu event),
- alasan eksklusi yang terlihat (TIMEOUT/AMBIGUOUS dihitung terpisah, bukan dibuang),
- jejak sumber (sha256 + tanggal impor) supaya tidak ada dua kebenaran.

Sumber: `state/idx_ledger.db` (SQLite, tabel `signals`, skema ledger Tencent:
event_id, job_id, ticker, setup, entry/sl/tp, status, result, net_r, costs_r,
grader_version, ...). Baca-saja; tidak pernah ditulis.

Catatan angka penting (dibuktikan 6 Okt): hasil modul ini IDENTIK dengan drift
mesin Tencent — BSJP gabungan n=45 meanR 0,608; ARA_HUNTER n=198 meanR −0,702.
Kalau berbeda, itu bug, bukan "sudut pandang".
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from .pakem import evaluate_pakem, summarize_r

__all__ = [
    "SETUP_MIN_UNTUK_TAYANG",
    "read_ledger",
    "compute_accuracy",
    "summarize_accuracy",
]

# Setup dengan lebih sedikit baris tuntas disembunyikan dari panel — bukan karena tak
# penting, tapi karena menampilkan n=3 sebagai "akurasi" menyesatkan. Ambang sengaja
# rendah (5) supaya setup baru tetap TERLIHAT sebagai "belum cukup sampel".
SETUP_MIN_UNTUK_TAYANG = 5

# Result yang berarti "tuntas" — di luar ini dihitung di kolom terpisah.
# TIMEOUT **termasuk**: posisi ditutup di pasar pada akhir jendela, punya net_r nyata.
# Mengeluarkannya dari metrik akan membuang kerugian nyata dan membuat angka terlihat
# lebih baik daripada kenyataan (terbukti 6 Okt: INTRADAY +0,107 vs −0,011 yang benar).
RESULT_TUNTAS = {"TP1", "TP2", "SL", "EXIT", "WIN", "LOSS", "TIMEOUT"}
RESULT_AMBIGU = {"AMBIGUOUS"}


def read_ledger(path: str | Path) -> list[dict[str, Any]]:
    """Baca tabel `signals`. Berkas/tabel tidak ada → list kosong (bukan error 500)."""
    p = Path(path)
    if not p.is_file():
        return []
    try:
        con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        rows = [dict(r) for r in con.execute("select * from signals")]
        con.close()
        return rows
    except sqlite3.Error:
        return []


def _hari(iso: str | None) -> str:
    return (iso or "")[:10]


def compute_accuracy(
    rows: list[dict[str, Any]],
    *,
    setup_min: int = SETUP_MIN_UNTUK_TAYANG,
) -> dict[str, Any]:
    """Statistik per setup: tuntas, belum tuntas, ambigü, R, hari, pakem.

    Aturan yang dipegang:
    - metrik performa HANYA dari baris tuntas;
    - `belum_tuntas` dilaporkan terpisah supaya pembacanya tahu masih ada yang jalan;
    - baris ambigu dihitung terpisah dan **tidak** masuk win/loss;
    - pakem memakai hari unik (koreksi klaster), sama seperti drift Tencent.
    """
    tuntas = [r for r in rows if r.get("status") == "CLOSED" and r.get("result") in RESULT_TUNTAS]
    ambigu = [r for r in rows if r.get("result") in RESULT_AMBIGU]
    belum = [r for r in rows if r.get("status") != "CLOSED"]

    per_setup: dict[str, dict[str, Any]] = {}
    grup = ("ARA_HUNTER", "BSJP_ARA", "BSJP_STRONG", "INTRADAY")

    def _rekap(baris: list[dict[str, Any]], nama: str) -> dict[str, Any] | None:
        if not baris:
            return None
        rs = [float(r["net_r"]) for r in baris if r.get("net_r") is not None]
        if not rs:
            return None
        hari = sorted({_hari(r.get("closed_at")) for r in baris if _hari(r.get("closed_at"))})
        # `r` untuk pakem = net_r per trade; koreksi klaster memakai tanggal tutup.
        closes = [
            {"r": float(r["net_r"]), "closed_at": r.get("closed_at")}
            for r in baris
            if r.get("net_r") is not None
        ]
        pk = evaluate_pakem(closes, kunci_r="r", kunci_tanggal="closed_at", biaya_tercatat=True)
        ringkas = summarize_r(rs)
        return {
            "setup": nama,
            "n": ringkas["n"],
            "n_hari": len(hari),
            "winrate_pct": ringkas["winrate_pct"],
            "mean_r": ringkas["mean_r"],
            "total_r": ringkas["total_r"],
            "profit_factor": ringkas["profit_factor"],
            "max_drawdown_r": ringkas["max_drawdown_r"],
            "ci_winrate": [round(pk.ci_winrate[0], 4), round(pk.ci_winrate[1], 4)],
            "pakem": pk.tingkat,
            "alasan": pk.alasan,
            "hari_pertama": hari[0] if hari else None,
            "hari_terakhir": hari[-1] if hari else None,
            "belum_tuntas": sum(1 for r in rows if r.get("setup") == nama and r.get("status") != "CLOSED"),
            "grader": sorted({r.get("grader_version") for r in baris if r.get("grader_version")}),
        }

    for s in grup:
        baris = [r for r in tuntas if r.get("setup") == s]
        rekap = _rekap(baris, s) if len(baris) >= setup_min else None
        per_setup[s] = rekap or {
            "setup": s,
            "n": len(baris),
            "n_hari": len({_hari(r.get("closed_at")) for r in baris if _hari(r.get("closed_at"))}),
            "pakem": "INSUFFICIENT",
            "alasan": [f"baris tuntas {len(baris)} < {setup_min} — belum ditampilkan sebagai akurasi"],
            "winrate_pct": None,
            "mean_r": None,
            "total_r": None,
            "belum_tuntas": sum(1 for r in rows if r.get("setup") == s and r.get("status") != "CLOSED"),
        }
    # Setup lain di luar grup dikenal (kalau ada) — dikelompokkan supaya tidak hilang.
    lain = sorted({r.get("setup") for r in tuntas if r.get("setup") not in grup})
    if lain:
        per_setup["LAIN"] = _rekap([r for r in tuntas if r.get("setup") in lain], "LAIN") or {}

    # BSJP digabung (ARA + STRONG): keputusan owner memakai BSJP sebagai satu keluarga.
    bsjp = [r for r in tuntas if str(r.get("setup", "")).startswith("BSJP")]
    gab = _rekap(bsjp, "BSJP (gabungan)") if len(bsjp) >= setup_min else None

    return {
        "total_baris": len(rows),
        "tuntas": len(tuntas),
        "belum_tuntas": len(belum),
        "ambigu": len(ambigu),
        "per_setup": per_setup,
        "bsjp_gabungan": gab,
        "catatan": [
            "hanya baris tuntas masuk metrik; belum tuntas & ambigu dilaporkan terpisah",
            "pakem dihitung pada hari independen (1 hari bursa = 1 event korelasi)",
            "net_r sudah termasuk biaya sesuai ledger sumber (costs_r per baris)",
        ],
    }


def summarize_accuracy(path: str | Path, *, setup_min: int = SETUP_MIN_UNTUK_TAYANG) -> dict[str, Any]:
    """Titik masuk snapshot: baca ledger → hitung → sertakan jejak sumber."""
    rows = read_ledger(path)
    if not rows:
        return {"tersedia": False, "alasan": f"ledger tidak terbaca: {path}"}
    hasil = compute_accuracy(rows, setup_min=setup_min)
    hasil["tersedia"] = True
    hasil["sumber"] = str(path)
    return hasil
