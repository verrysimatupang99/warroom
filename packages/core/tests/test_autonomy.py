"""Tes bounded autonomy (P5): registry, batas, gate, penerapan, rollback, kill switch."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from warroom_core import autonomy
from warroom_core.db import Alert, Event, Fact, FrozenSplit, Job, Parameter, Proposal, session_scope


@pytest.fixture(autouse=True)
def _bersihkan(db):
    with session_scope() as s:
        s.query(Proposal).delete()
        s.query(Parameter).delete()
        s.query(Fact).delete()
        s.query(Event).delete()
        s.query(Alert).delete()
        s.query(Job).delete()
        s.query(FrozenSplit).delete()
    yield


def _split_beku(s) -> str:
    """Daftarkan split beku sungguhan — gate menolak label "frozen:" yang dikarang."""
    s.add(FrozenSplit(
        id="uji-autonomy", dataset="poly-agent", source="/tmp", files_json=[], manifest_hash="x"
    ))
    s.flush()
    return "frozen:uji-autonomy"


def test_seed_mendaftarkan_parameter_dan_tidak_menimpa_nilai_yang_ada(db) -> None:
    with session_scope() as s:
        pertama = autonomy.seed_parameters(s)
        p = s.scalar(select(Parameter).where(Parameter.name == "agent.threshold"))
        p.value_json = 0.75
    with session_scope() as s:
        kedua = autonomy.seed_parameters(s)
        p = s.scalar(select(Parameter).where(Parameter.name == "agent.threshold"))
    assert "agent.threshold" in pertama
    assert kedua == []
    assert p.value_json == 0.75, "nilai yang sudah ada tidak boleh ditimpa saat seeding"


def test_parameter_gate_dan_locked_prohibited(db) -> None:
    with session_scope() as s:
        autonomy.seed_parameters(s)
        assert autonomy.decide_proposal(s, "gate.min_n", 10)[0] == "prohibited"
        assert autonomy.decide_proposal(s, "mode", "live")[0] == "prohibited"
        assert autonomy.decide_proposal(s, "gate.ci", 0.9)[0] == "prohibited"
        assert autonomy.decide_proposal(s, "fee.rumus", 0.01)[0] == "prohibited"


def test_di_luar_batas_ditolak_dengan_alasan_tercatat(db) -> None:
    """Bukti nyata: weights.book 0,602 di luar batas 0,6."""
    with session_scope() as s:
        autonomy.seed_parameters(s)
        hasil = autonomy.propose(
            s, "agent.weights.book", 0.602,
            alasan="patch agen", evidence={"n": 340, "win": 305, "be": 0.8675},
        )
    assert hasil["keputusan"] == "ditolak"
    assert "di_luar_bounds" in hasil["sebab"]
    with session_scope() as s:
        pr = s.query(Proposal).one()
        assert pr.status == "ditolak" and "di_luar_bounds" in pr.rejected_reason
        assert s.query(Event).filter_by(type="proposal.rejected").count() == 1


def test_bukti_kurang_ditolak(db) -> None:
    with session_scope() as s:
        autonomy.seed_parameters(s)
        hasil = autonomy.propose(s, "agent.threshold", 0.8, alasan="tanpa bukti")
    assert hasil["keputusan"] == "ditolak"
    assert "bukti kurang" in hasil["sebab"]


def test_bukti_tanpa_split_beku_ditolak_gate(db) -> None:
    """Log agen = rentang bergulir, bukan split beku → gate menolak (disengaja)."""
    with session_scope() as s:
        autonomy.seed_parameters(s)
        hasil = autonomy.propose(
            s, "agent.threshold", 0.8,
            alasan="patch agen",
            evidence={"n": 340, "win": 305, "be": 0.8675, "sumber": "agent-lessons.jsonl"},
        )
    assert hasil["keputusan"] == "ditolak"
    assert "gate" in hasil["sebab"].lower()
    with session_scope() as s:
        p = s.scalar(select(Parameter).where(Parameter.name == "agent.threshold"))
        assert p.value_json == 0.82, "nilai tidak boleh berubah saat usulan ditolak"


def test_usulan_dalam_batas_dengan_bukti_beku_diterapkan_dan_tercatat(db) -> None:
    with session_scope() as s:
        autonomy.seed_parameters(s)
        hasil = autonomy.propose(
            s, "agent.threshold", 0.86,
            alasan="kencangkan setelah gate gagal",
            evidence={"n": 500, "win": 420, "be": 0.77, "ci": 0.90, "split": _split_beku(s)},
        )
    assert hasil["keputusan"] == "diterapkan"
    with session_scope() as s:
        p = s.scalar(select(Parameter).where(Parameter.name == "agent.threshold"))
        pr = s.query(Proposal).one()
        assert p.value_json == 0.86
        assert pr.applied_at is not None
        assert pr.config_hash and len(pr.config_hash) == 64
        assert pr.evidence_json["n"] == 500
        # n=500, win=420 (84%) vs BE 77% → ci_low > be → gate lolos (angka, bukan selera)
        assert pr.gate_verdict == "lolos"
        assert s.query(Event).filter_by(type="proposal.decided").count() == 1


def test_evidence_lemah_masih_diterapkan_tapi_gate_tercatat_gagal(db) -> None:
    """Angka di bawah BE tidak menghalangi perubahan *kencang*; yang penting keputusan tercatat."""
    with session_scope() as s:
        autonomy.seed_parameters(s)
        hasil = autonomy.propose(
            s, "agent.threshold", 0.88,
            alasan="kencangkan karena gate gagal",
            evidence={"n": 300, "win": 237, "be": 0.77, "ci": 0.90, "split": _split_beku(s)},
        )
    assert hasil["keputusan"] == "diterapkan"
    assert hasil["gate"] == "gagal"
    with session_scope() as s:
        pr = s.query(Proposal).one()
        assert pr.gate_verdict == "gagal"
        assert pr.applied_at is not None


def test_rollback_mengembalikan_nilai_dan_tercatat(db) -> None:
    with session_scope() as s:
        autonomy.seed_parameters(s)
        autonomy.propose(
            s, "agent.threshold", 0.86, alasan="ubah",
            evidence={"n": 500, "win": 420, "be": 0.77, "split": _split_beku(s)},
        )
        pr = s.query(Proposal).one()
        pid = pr.id
    with session_scope() as s:
        assert autonomy.rollback(s, pid) is True
    with session_scope() as s:
        p = s.scalar(select(Parameter).where(Parameter.name == "agent.threshold"))
        pr = s.get(Proposal, pid)
        assert p.value_json == 0.82
        assert pr.status == "dibatalkan"
        assert s.query(Event).filter_by(type="proposal.rolled_back").count() == 1


def test_scope_live_butuh_manusia_lalu_diterapkan_oleh_owner(db) -> None:
    with session_scope() as s:
        autonomy.seed_parameters(s)
        # sizeUsd scope paper; kita ubah scope-nya jadi live untuk menguji jalur "butuh manusia"
        p = s.scalar(select(Parameter).where(Parameter.name == "risk.sizeUsd"))
        p.scope = "live"
        hasil = autonomy.propose(s, "risk.sizeUsd", 7,
                                alasan="naikkan ukuran", evidence={"n": 500, "win": 420, "be": 0.77})
        assert hasil["keputusan"] == "butuh_manusia"
        pid = hasil["proposal_id"]

    with session_scope() as s:
        assert autonomy.apply_proposal(s, pid, actor="owner") is True
    with session_scope() as s:
        p = s.scalar(select(Parameter).where(Parameter.name == "risk.sizeUsd"))
        pr = s.get(Proposal, pid)
        assert p.value_json == 7 and pr.decided_by == "owner"
        assert s.query(Event).filter_by(type="proposal.applied").count() == 1


def test_kill_switch_mematikan_usulan(db) -> None:
    with session_scope() as s:
        autonomy.seed_parameters(s)
        assert autonomy.kill_switch_aktif(s) is False
        autonomy.set_kill_switch(s, True, actor="owner")
    with session_scope() as s:
        assert autonomy.kill_switch_aktif(s) is True
        ev = s.query(Event).filter_by(type="ai.kill_switch").one()
        assert ev.payload_json == {"dari": False, "ke": True}
        assert ev.severity == "warning"


def test_hash_konfigurasi_berubah_saat_parameter_berubah(db) -> None:
    with session_scope() as s:
        autonomy.seed_parameters(s)
        h1 = autonomy.hash_konfigurasi(s)
    with session_scope() as s:
        autonomy.propose(s, "agent.threshold", 0.86, alasan="x",
                         evidence={"n": 500, "win": 420, "be": 0.77, "split": _split_beku(s)})
        h2 = autonomy.hash_konfigurasi(s)
    assert h1 != h2


def test_handler_learner_menolak_saat_kill_switch(db) -> None:
    from warroom_worker.jobs import register_handlers
    from warroom_worker.schedule import run_one

    register_handlers()
    with session_scope() as s:
        autonomy.seed_parameters(s)
        autonomy.set_kill_switch(s, True)
    with session_scope() as s:
        j = s.scalar(select(Job).where(Job.name == "learner"))
        if j is None:
            import warroom_worker.schedule as sch

            sch.ensure_jobs(s)
            j = s.scalar(select(Job).where(Job.name == "learner"))
        status, detail = run_one(s, j)
    assert status == "ok"
    assert "kill switch" in detail
    assert datetime.now(UTC) is not None


def test_terapkan_menolak_usulan_yang_ditolak(db) -> None:
    with session_scope() as s:
        autonomy.seed_parameters(s)
        hasil = autonomy.propose(
            s, "agent.threshold", 0.99,
            alasan="terlalu tinggi",
            evidence={"n": 500, "win": 420, "be": 0.77, "split": _split_beku(s)},
        )
        assert hasil["keputusan"] == "ditolak"
        pid = hasil["proposal_id"]
    with session_scope() as s:
        assert autonomy.apply_proposal(s, pid, actor="owner") is False