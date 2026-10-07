"""Penjaga INVARIANT RISIKO dompet IDX (temuan QA eksternal, 7 Okt 2026).

QA menulis: "satu trade tidak boleh menghasilkan R < -1R kecuali diberi status khusus".
Kenyataannya bisa — ARA_HUNTER menahan posisi sampai open sesi berikutnya, jadi gap
pembukaan bisa 14x risiko yang direncanakan (bukti: MBTO.JK −13,84R). Yang salah bukan
angkanya, melainkan membiarkannya TANPA penanda. Tes ini mengunci: klasifikasi wajib
terbit, terburuk wajib disebut, dan sinyal CREATED wajib dibedakan dari posisi berjalan.
"""

from __future__ import annotations

import datetime as dt
import json
import sqlite3
from pathlib import Path

from live_trading import dompet


def _ledger_idx(tmp_path: Path, baris: list[tuple]) -> None:
    db = tmp_path / "idx_ledger.db"
    con = sqlite3.connect(db)
    con.execute(
        "create table signals (event_id text, ticker text, setup text, status text, "
        "result text, net_r real, closed_at text, created_at text)"
    )
    con.executemany("insert into signals values (?,?,?,?,?,?,?,?)", baris)
    con.commit()
    con.close()
    (tmp_path / "kurs_usd_idr.json").write_text(
        json.dumps({"kurs": 17_841.0, "diambil": dt.datetime.now(dt.UTC).isoformat(), "sumber": "tes"}),
        encoding="utf-8",
    )


def test_invariant_terbit_dan_mengklasifikasi(tmp_path: Path) -> None:
    _ledger_idx(
        tmp_path,
        [
            # wajar
            ("a1", "AAAA.JK", "ARA_HUNTER", "CLOSED", "TP1", 2.0, "2026-10-01T09:00", "2026-09-30T10:00"),
            ("a2", "BBBB.JK", "ARA_HUNTER", "CLOSED", "LOSS", -1.0, "2026-10-01T09:00", "2026-09-30T10:00"),
            # gap 1–2R
            ("a3", "CCCC.JK", "ARA_HUNTER", "CLOSED", "LOSS", -1.6, "2026-10-01T09:00", "2026-09-30T10:00"),
            # dalam 2–5R
            ("a4", "DDDD.JK", "ARA_HUNTER", "CLOSED", "LOSS", -4.2, "2026-10-01T09:00", "2026-09-30T10:00"),
            # ekstrem > 5R — harus disebut sebagai terburuk
            ("a5", "MBTO.JK", "ARA_HUNTER", "CLOSED", "LOSS", -13.84, "2026-09-29T09:00", "2026-09-28T09:30"),
            # yatim: CREATED (bukan posisi berjalan)
            ("a6", "BIKE.JK", "ARA_HUNTER", "CREATED", None, None, None, "2026-09-24T10:03"),
        ],
    )
    d = dompet.ringkas_semua_dompet(tmp_path)["pasar"]["idx"]
    inv = d["invariant"]
    assert inv["model_breach"] is True
    assert inv["pelanggaran_1r"] == 3, "3 trade di luar kelas wajar"
    assert inv["kelas_loss"] == {"wajar": 2, "gap": 1, "dalam": 1, "ekstrem": 1}
    assert inv["terburuk"]["pair"] == "MBTO.JK"
    assert inv["terburuk"]["r"] == -13.84
    assert "TIDAK mengenal rugi maksimal 1R" in inv["penjelasan"]
    # CREATED tidak pernah dihitung sebagai trade tuntas, tapi jumlahnya terbit
    assert d["trade"] == 5
    assert d["sinyal_yatim"]["jumlah"] == 1
    assert d["sinyal_yatim"]["tertua"].startswith("2026-09-24")
    # Klasifikasi PER SETUP (QA putaran 2: "pisahkan breach/gap loss"):
    # ARA_HUNTER punya 3 trade breach (gap+dalam+ekstrem) dari 5, 1 di antaranya >5R.
    ara = d["per_setup"]["ARA_HUNTER"]
    assert ara["lewat_1r"] == 3
    assert ara["lewat_1r_pct"] == 60.0
    assert ara["rugi_ekstrem_5r"] == 1
    assert ara["risiko_tak_terbatas"] is True


def test_invariant_tenang_bila_semua_wajar(tmp_path: Path) -> None:
    _ledger_idx(
        tmp_path,
        [
            ("b1", "AAAA.JK", "BSJP", "CLOSED", "TP1", 1.4, "2026-10-01T09:00", "2026-09-30T15:00"),
            ("b2", "BBBB.JK", "BSJP", "CLOSED", "SL", -1.02, "2026-10-01T09:00", "2026-09-30T15:00"),
        ],
    )
    d = dompet.ringkas_semua_dompet(tmp_path)["pasar"]["idx"]
    assert d["invariant"]["model_breach"] is False
    assert d["invariant"]["pelanggaran_1r"] == 0
    assert "terpenuhi" in d["invariant"]["penjelasan"]
