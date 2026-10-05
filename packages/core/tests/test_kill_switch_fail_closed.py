"""Regresi: kill switch AI wajib fail-closed bila baris tak terbaca.

Tidak menyentuh DB produksi. Memakai WARROOM_TEST_DB_URL / ~/.config/warroom/test-db.env.
Pada kode sekarang tes ini HARUS gagal (merah): baris hilang dibaca sebagai saklar mati.
Setelah patch di DELIVERABLE.md, ketiga assert lulus.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy import select


def _pakai_db_tes() -> None:
    if os.environ.get("WARROOM_TEST_DB_URL"):
        os.environ["WARROOM_DB_URL"] = os.environ["WARROOM_TEST_DB_URL"]
        return
    env = Path.home() / ".config" / "warroom" / "test-db.env"
    for line in env.read_text(encoding="utf-8").splitlines():
        if line.startswith("WARROOM_TEST_DB_URL="):
            os.environ["WARROOM_DB_URL"] = line.split("=", 1)[1].strip().strip("\"'")
            return
    raise RuntimeError("DB tes tidak ada — tes ini tidak boleh jatuh ke DB produksi")


_pakai_db_tes()

from warroom_core import autonomy  # noqa: E402
from warroom_core.db import Parameter, dispose_engine, session_scope  # noqa: E402
from warroom_core.db.session import safe_url  # noqa: E402


def test_url_bukan_produksi() -> None:
    url = safe_url()
    assert "warroom_test" in url, url
    assert "/warroom:" not in url.split("@")[-1]


def test_baris_hilang_dianggap_saklar_aktif(db_siap) -> None:
    """Tak terbaca = berhenti. Bukan 'saklar mati'."""
    with session_scope() as s:
        assert autonomy.kill_switch_aktif(s) is True


def test_hanya_false_eksplisit_yang_membuka_tulisan(db_siap) -> None:
    with session_scope() as s:
        autonomy.seed_parameters(s)
        p = s.scalar(select(Parameter).where(Parameter.name == "ai.kill_switch"))
        assert p is not None and p.value_json is False
        assert autonomy.kill_switch_aktif(s) is False
        p.value_json = "false"  # string bukan boolean
    with session_scope() as s:
        assert autonomy.kill_switch_aktif(s) is True
    with session_scope() as s:
        autonomy.set_kill_switch(s, False, actor="uji")
        assert autonomy.kill_switch_aktif(s) is False


def test_usulan_tidak_jalan_bila_saklar_tak_terbaca(db_siap) -> None:
    with session_scope() as s:
        # Parameter lain ada, saklar tidak — pembaca lama akan mengizinkan usulan.
        s.add(
            Parameter(
                name="agent.threshold",
                scope="paper",
                value_json=0.82,
                bounds_json=[0.5, 0.9],
                locked=False,
                note="uji",
            )
        )
    with session_scope() as s:
        hasil = autonomy.usulkan(
            s,
            "agent.threshold",
            0.86,
            alasan="tidak boleh tembus saat saklar tak terbaca",
            evidence={"n": 500, "win": 420, "be": 0.77, "split": "frozen:uji"},
            actor="learner",
        )
        assert hasil["keputusan"] != "diterapkan"
    with session_scope() as s:
        p = s.scalar(select(Parameter).where(Parameter.name == "agent.threshold"))
        assert p.value_json == 0.82


@pytest.fixture
def db_siap():
    dispose_engine()
    from warroom_core.db import Proposal
    from warroom_core.db import session_scope as scope

    with scope() as s:
        s.query(Proposal).delete()
        s.query(Parameter).delete()
    yield
    with scope() as s:
        s.query(Proposal).delete()
        s.query(Parameter).delete()
    dispose_engine()
