"""Regresi: retensi data (P5 roadmap 5 Okt 2026).

Yang dikunci:
1. Versi lama `facts` dibuang, tetapi `keep_versi` TERBARU per kunci SELALU tersisa —
   versi terbaru tidak boleh pernah ikut terhapus (itu yang dipakai UI/AI).
2. `rencana()` tidak menghapus apa pun (aman dijalankan di produksi).
3. `events` (jejak audit) TIDAK dihapus kecuali diminta eksplisit.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from warroom_core import retensi
from warroom_core.db import Event, Fact, session_scope


@pytest.fixture(autouse=True)
def _bersihkan(db):
    """Isolasi: retensi bersifat GLOBAL (semua kunci), jadi sisa tes lain harus dikosongkan."""
    with session_scope() as s:
        s.query(Fact).delete()
        s.query(Event).filter(Event.type.in_(["uji.lama"])).delete()
    yield


def _fact(s, kind: str, key: str, menit_lalu: int, nilai: float) -> None:
    s.add(
        Fact(
            kind=kind, key=key, value_json={"v": nilai}, source="uji",
            observed_at=datetime.now(UTC) - timedelta(minutes=menit_lalu),
            ttl_s=600, hash=f"h{nilai}",
        )
    )


def test_rencana_tidak_menghapus(db) -> None:
    with session_scope() as s:
        for m in range(10):
            _fact(s, "uji", "kunci-a", m, float(m))
    with session_scope() as s:
        r = retensi.rencana(s, keep_versi=3)
        assert r["facts"] == 7  # 10 versi - 3 yang disimpan
    with session_scope() as s:
        from sqlalchemy import func, select

        assert s.scalar(select(func.count()).select_from(Fact)) == 10  # tidak ada yang hilang


def test_jalankan_menyimpan_versi_terbaru(db) -> None:
    with session_scope() as s:
        for m in range(10):
            _fact(s, "uji", "kunci-a", m, float(m))  # menit_lalu menurun = makin baru
    with session_scope() as s:
        hasil = retensi.jalankan(s, keep_versi=3, hapus_events=False)
        assert hasil["dihapus"]["facts"] == 7
    with session_scope() as s:
        from sqlalchemy import select

        tersisa = s.scalars(select(Fact).order_by(Fact.observed_at.desc())).all()
        assert len(tersisa) == 3
        # 3 TERBARU yang tersisa (menit_lalu 0,1,2 → nilai 0.0,1.0,2.0)
        assert sorted(f.value_json["v"] for f in tersisa) == [0.0, 1.0, 2.0]


def test_kunci_berbeda_dihitung_terpisah(db) -> None:
    with session_scope() as s:
        for m in range(5):
            _fact(s, "uji", "kunci-a", m, float(m))
        for m in range(5):
            _fact(s, "uji", "kunci-b", m, float(100 + m))
    with session_scope() as s:
        hasil = retensi.jalankan(s, keep_versi=2, hapus_events=False)
        assert hasil["dihapus"]["facts"] == 6  # (5-2) × 2 kunci
    with session_scope() as s:
        from sqlalchemy import func, select

        # tiap kunci menyisakan 2 versinya sendiri
        for kunci in ("kunci-a", "kunci-b"):
            n = s.scalar(
                select(func.count()).select_from(Fact).where(Fact.key == kunci)
            )
            assert n == 2


def test_fact_yang_dirujuk_event_TIDAK_dihapus(db) -> None:
    """Regresi: retensi pertama tanpa penjaga ini membuat 935 event menunjuk fact_id yang
    sudah hilang di produksi. Jejak audit append-only harus tetap bisa ditelusuri."""
    with session_scope() as s:
        for m in range(6):
            _fact(s, "uji", "kunci-r", m, float(m))
    # rujuk versi PALING TUA (id terkecil) — ini yang jadi kandidat hapus
    with session_scope() as s:
        tertua = s.scalars(select(Fact).where(Fact.key == "kunci-r").order_by(Fact.observed_at)).first()
        s.add(
            Event(
                type="uji.rujuk", actor="uji", payload_json={}, fact_ids=[tertua.id], severity="info"
            )
        )
        tertua_id = tertua.id

    with session_scope() as s:
        retensi.jalankan(s, keep_versi=3, hapus_events=False)
    with session_scope() as s:
        # fakta yang dirujuk masih ada walau versinya sudah tua
        assert s.get(Fact, tertua_id) is not None
        yatim = s.scalar(
            select(func.count())
            .select_from(Event)
            .where(func.jsonb_array_length(Event.fact_ids) > 0)
            .where(
                ~select(Fact.id).where(Fact.id == tertua_id).exists()
            )
        )
        assert yatim == 0, "tidak boleh ada event yang menunjuk fakta terhapus"


def test_events_audit_tidak_dihapus_kecuali_diminta(db) -> None:
    lama = datetime.now(UTC) - timedelta(days=400)
    with session_scope() as s:
        s.add(
            Event(
                type="uji.lama", actor="uji", payload_json={}, fact_ids=[],
                severity="info", created_at=lama,
            )
        )
    with session_scope() as s:
        retensi.jalankan(s, events_hari=30, hapus_events=False)
    with session_scope() as s:
        from sqlalchemy import func, select

        assert s.scalar(select(func.count()).select_from(Event).where(Event.type == "uji.lama")) == 1

    with session_scope() as s:
        hasil = retensi.jalankan(s, events_hari=30, hapus_events=True)
        assert hasil["dihapus"]["events"] == 1


# --- Alerts dalam retensi (temuan audit 7 Okt) ------------------------------------------
# 100 alert menumpuk (75 belum di-ack sejak 2 Okt) karena retensi tidak pernah menyentuh
# tabel ini. Aturannya: yang SUDAH di-ack dan tua → dibuang; yang BELUM di-ack → tetap
# (itu pekerjaan manusia, bukan retensi).

def test_alert_sudah_diack_tua_dibuang(db) -> None:
    from datetime import UTC, datetime, timedelta

    from warroom_core.db import Alert, session_scope
    from warroom_core.retensi import jalankan, rencana

    lama = datetime.now(UTC) - timedelta(days=40)
    with session_scope() as s:
        s.add(Alert(severity="info", subject="uji/lama", message="x", ack_at=lama, created_at=lama))
        s.add(Alert(severity="info", subject="uji/baru", message="y", ack_at=datetime.now(UTC)))
        s.add(Alert(severity="info", subject="uji/belum", message="z", ack_at=None, created_at=lama))
    with session_scope() as s:
        assert rencana(s, alerts_hari=14)["alerts"] == 1
    with session_scope() as s:
        rep = jalankan(s, alerts_hari=14)
        assert rep["dihapus"]["alerts"] == 1
    with session_scope() as s:
        sisa = {a.subject for a in s.query(Alert).all()}
    assert sisa == {"uji/baru", "uji/belum"}, "yang belum di-ack TIDAK boleh dibuang"


def test_alert_belum_diack_selamanya_dipertahankan(db) -> None:
    from datetime import UTC, datetime, timedelta

    from warroom_core.db import Alert, session_scope
    from warroom_core.retensi import rencana

    sangat_lama = datetime.now(UTC) - timedelta(days=365)
    with session_scope() as s:
        s.add(Alert(severity="warning", subject="uji/lama", message="x", ack_at=None, created_at=sangat_lama))
    with session_scope() as s:
        assert rencana(s, alerts_hari=1)["alerts"] == 0
