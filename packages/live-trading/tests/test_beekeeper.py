"""Tes Beekeeper: deteksi dua-jendela, pemicu usulan, dan pagar usulan-saja."""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from warroom_core import autonomy
from warroom_core.db import Event, Parameter, Proposal, session_scope

from live_trading import beekeeper as bk

BASE = datetime(2026, 10, 1, tzinfo=UTC)


def _rows(nama: str, basis: list[float], baru: list[float]) -> list[dict]:
    rows = []
    ts = BASE
    for r in basis + baru:
        rows.append({"strategi": nama, "r": r, "ts": ts.isoformat()})
        ts += timedelta(hours=1)
    return rows


@pytest.fixture(autouse=True)
def _bersihkan(db):
    with session_scope() as s:
        s.query(Proposal).delete()
        s.query(Parameter).delete()
        s.query(Event).delete()
        autonomy.seed_parameters(s)
    yield
    with session_scope() as s:
        s.query(Proposal).delete()
        s.query(Parameter).delete()
        s.query(Event).delete()


def _turun() -> list[dict]:
    """Basis 20 trade @ +0.4R, baru 20 trade @ −0.3R → turun 0.7R expectancy."""
    return _rows("smc-btc", [0.4] * 20, [-0.3] * 20)


def test_deteksi_menangkap_penurunan_nyata() -> None:
    hasil = bk.deteksi_penurunan(_turun())
    assert len(hasil) == 1
    u = hasil[0]
    assert u.strategi == "smc-btc"
    assert u.n_basis == 20 and u.n_baru == 20
    assert u.expectansi_baru_r < 0
    assert (u.expectansi_basis_r - u.expectansi_baru_r) >= bk.PENURUNAN_R
    assert u.t is not None and abs(u.t) >= bk.AMBANG_T
    ev = u.evidence()
    assert ev["strategi"] == "smc-btc" and ev["n_baru"] == 20
    assert ev["signifikan_tanpa_variansi"] is True  # jendela R konstan → t tak hingga


def test_deteksi_bekerja_pada_data_variansi_sehat() -> None:
    # Hasil realistis TP/SL bercampur derau; rata-rata turun jauh dan nyata.
    basis = [2.0, -1.0, 2.0, -1.0, 2.0, 2.0, -1.0, 2.0, -1.0, 2.0] * 2
    baru = [-1.0, -1.0, 2.0, -1.0, -1.0, -1.0, -1.0, -1.0, 2.0, -1.0] * 2
    hasil = bk.deteksi_penurunan(_rows("variansi", basis, baru))
    assert len(hasil) == 1
    u = hasil[0]
    assert u.expectansi_basis_r >= 0.5 and u.expectansi_baru_r < 0
    assert u.t is not None and math.isfinite(u.t)
    ev = u.evidence()
    assert ev["signifikan_tanpa_variansi"] is False
    assert ev["t_welch"] is not None


def test_deteksi_menolak_derau_dan_sampel_kurang() -> None:
    # Membaik: basis negatif, baru positif — bukan usulan.
    assert bk.deteksi_penurunan(_rows("naik", [-0.3] * 20, [0.4] * 20)) == []
    # Turun tipis (< PENURUNAN_R) — derau, bukan usulan.
    assert bk.deteksi_penurunan(_rows("tipis", [0.1] * 20, [-0.05] * 20)) == []
    # Turun nyata tapi expectation baru masih positif — strategi masih untung.
    assert bk.deteksi_penurunan(_rows("turun-tapi-untung", [0.6] * 20, [0.05] * 20)) == []
    # Sampel di bawah dua jendela penuh — belum boleh disimpulkan.
    pendek = _rows("kurang", [0.4] * 15, [-0.3] * 20)
    assert bk.deteksi_penurunan(pendek) == []


def test_baris_tak_tuntas_dan_tak_bernomor_diluarkan_bukan_dihitung_nol() -> None:
    rows = _turun()
    # 8 baris menunggu (r None) + 4 baris tanpa strategi: boleh memengaruhi urutan waktu
    # kalau dihitung; karena diluarkan, hasil deteksinya identik dengan data bersih.
    for i in range(8):
        rows.append({"strategi": "smc-btc", "r": None, "ts": (BASE + timedelta(days=i)).isoformat()})
    rows.append({"strategi": "", "r": -1.0, "ts": BASE.isoformat()})
    rows.append({"strategi": "smc-btc", "r": -1.0, "ts": "bukan-iso"})
    assert bk.deteksi_penurunan(rows) == bk.deteksi_penurunan(_turun())


def _usul(db_session):
    u = bk.deteksi_penurunan(_turun())[0]
    return bk.usulkan(
        db_session,
        u,
        parameter="risk.sizeUsd",
        nilai_baru=2.5,
        alasan="expectancy turun nyata; kurangi ukuran sampai diverifikasi owner",
    )


def test_usulkan_selalu_butuh_manusia_dan_tidak_mengubah_parameter(db) -> None:
    with session_scope() as s:
        out = _usul(s)
        assert out["keputusan"] == "butuh_manusia"
        id_p = out["proposal_id"]
        p = s.scalar(select(Parameter).where(Parameter.name == "risk.sizeUsd"))
        assert float(p.value_json) == 5.0  # nilai SEED tidak tersentuh
        pr = s.get(Proposal, id_p)
        assert pr is not None and pr.status == "butuh_manusia"
        assert pr.decided_by is None and pr.applied_at is None
        assert pr.from_json == 5.0 and pr.to_json == 2.5
        assert pr.evidence_json["n_baru"] == 20
        kejadian = s.scalars(select(Event).where(Event.type == "beekeeper.usulan")).all()
        assert len(kejadian) == 1 and kejadian[0].severity == "warning"


def test_usulkan_menolak_parameter_gate_terkunci_dan_tak_terdaftar(db) -> None:
    u = bk.deteksi_penurunan(_turun())[0]
    with session_scope() as s:
        for param in ("gate.min_n", "mode", "tidak.ada"):
            out = bk.usulkan(s, u, parameter=param, nilai_baru=1, alasan="uji pagar")
            assert out["keputusan"] == "ditolak", param
        assert s.scalars(select(Proposal)).all() == []
        assert s.scalars(select(Event).where(Event.type == "beekeeper.usulan")).all() == []


def test_kill_switch_aktif_memblokir_usulan_gagal_tertutup(db) -> None:
    with session_scope() as s:
        autonomy.set_kill_switch(s, True)
    with session_scope() as s:
        out = _usul(s)
        assert out["keputusan"] == "ditolak"
        assert "kill switch" in out["sebab"]
        assert s.scalars(select(Proposal)).all() == []


def test_kill_switch_tak_terbaca_juga_memblokir(db) -> None:
    with session_scope() as s:
        # Baris parameter hilang → kill_switch_aktif() harus menganggap AKTIF.
        s.query(Parameter).filter(Parameter.name == "ai.kill_switch").delete()
    with session_scope() as s:
        assert autonomy.kill_switch_aktif(s) is True
        out = _usul(s)
        assert out["keputusan"] == "ditolak"
        assert s.scalars(select(Proposal)).all() == []
