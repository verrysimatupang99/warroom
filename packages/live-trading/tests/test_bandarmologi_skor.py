"""Tes skor bandarmologi — kejujuran angka di atas kenyamanan tampilan.

Temuan nyata 6 Okt: radar sering hanya berisi 1–2 emiten. Skor harus tetap jujur:
- rasio ATS menentukan arah (beli > jual → >50);
- radar kecil TIDAK memberi bonus ukuran (dulu median-dari-satu membuat semua naik);
- emiten status bukan 'ok' dilewati, bukan diisi nol.
"""

from __future__ import annotations

from live_trading import bandarmologi_skor as bs


def _row(**kw):
    dasar = {
        "kode": "AAA",
        "status": "ok",
        "no_sell": False,
        "ats_beli": 100.0,
        "ats_jual": 100.0,
        "frq_beli": 100.0,
        "frq_jual": 100.0,
    }
    dasar.update(kw)
    return dasar


def test_seimbang_skor_50():
    out = bs.score_from_outcome([_row()])
    assert out[0]["skor"] == 50
    assert out[0]["kelas"] == "SEIMBANG"


def test_beli_dominan_naik_jual_dominan_turun():
    beli = bs.score_from_outcome([_row(ats_beli=300, ats_jual=100, frq_beli=300, frq_jual=100)])[0]
    jual = bs.score_from_outcome([_row(ats_beli=100, ats_jual=300, frq_beli=100, frq_jual=300)])[0]
    assert beli["skor"] > 50 > jual["skor"]
    assert beli["skor"] - 50 == 50 - jual["skor"], "simetris — tidak memihak"


def test_no_sell_memberi_bonus():
    dasar = bs.score_from_outcome([_row()])[0]["skor"]
    bonus = bs.score_from_outcome([_row(no_sell=True)])[0]["skor"]
    assert bonus == dasar + 20


def test_radar_kecil_tidak_menggembungkan_skor():
    """Median dari satu emiten tidak boleh memberi nilai penuh komponen ukuran."""
    out = bs.score_from_outcome([_row(ats_beli=10_000, ats_jual=1)])[0]
    komponen = {k["nama"]: k["kontribusi"] for k in out["komponen"]}
    assert komponen["ukuran_ats"] == 0.0
    assert any("terlalu kecil" in c for c in out["catatan"])


def test_skala_ukuran_pada_radar_besar():
    rows = [
        _row(kode=f"E{i}", ats_beli=100 + i * 100, ats_jual=100)
        for i in range(4)
    ]
    rows.append(_row(kode="BESAR", ats_beli=10_000, ats_jual=100))
    out = {e["kode"]: e for e in bs.score_from_outcome(rows)}
    assert out["BESAR"]["ukuran_relatif"] == 1.0, "cap di 1.5x median"
    assert out["E0"]["ukuran_relatif"] < 0.5


def test_status_bukan_ok_dilewati():
    out = bs.score_from_outcome([_row(kode="X", status="galat"), _row(kode="Y")])
    assert [e["kode"] for e in out] == ["Y"]


def test_pembungkus_mengembalikan_alasan_bila_kosong():
    out = bs.bandarmologi_score({"bandarmologi": {"error": "kuota habis"}})
    assert out["tersedia"] is False
    assert "kuota habis" in out["alasan"]
