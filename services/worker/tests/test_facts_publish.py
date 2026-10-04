"""Tes penulis fakta + parity dengan `state/snapshot.json` (P1-T5/T6).

Acceptance yang diuji: untuk fakta yang diterbitkan, **nilai di DB == nilai di berkas**.
"""

from __future__ import annotations

import json
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from warroom_core.db import Event, Fact, session_scope
from warroom_worker.facts_publish import canonical_hash, publish_snapshot

SNAPSHOT_ASLI = Path.home() / "live-trading" / "state" / "snapshot.json"


@pytest.fixture(autouse=True)
def _bersihkan_tabel(db):
    """Isolasi tes: setiap tes mulai dari tabel fakta/event/strategi yang kosong."""
    from warroom_core.db import Strategy

    with session_scope() as s:
        s.query(Fact).delete()
        s.query(Event).delete()
        s.query(Strategy).delete()
    yield


@pytest.fixture
def snapshot_uji(tmp_path: Path) -> Path:
    """Snapshot sintetis dengan bentuk yang sama seperti aslinya (termasuk 'dibuat')."""
    dibuat = datetime(2026, 10, 2, 20, 0, tzinfo=UTC).isoformat()
    payload = {
        "dibuat": dibuat,
        "mode": "paper",
        "bagian": {"crypto": "ok", "idx": "ok", "forex": "ok"},
        "risiko": {"ruang_rugi_r": 3.0, "posisi_terpakai": 0},
        "equity": {"usd": 100.0, "r": 3.844},
        "ledger": {"trade": 5, "menang": 4},
        "poly_paper": {"arm_b": {"entry": 111, "menang": 93}},
        "lp_paper": {"posisi": 0},
        "gmgn": {"radar": "basi"},
        "radar": {"umur_mnt": 42},
        "kandidat": [],
    }
    p = tmp_path / "snapshot.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def test_menerbitkan_fakta_dari_snapshot(db, snapshot_uji: Path) -> None:
    jml = len(json.loads(snapshot_uji.read_text(encoding="utf-8")))
    with session_scope() as s:
        rep = publish_snapshot(s, snapshot_uji)
    assert rep.status == "ok"
    assert rep.facts == jml

    with session_scope() as s:
        keys = {f.key for f in s.query(Fact).filter_by(kind="snapshot").all()}
    assert {"mode", "equity", "ledger", "poly_paper"} <= keys


def test_observed_at_dari_berkas_bukan_sekarang(db, snapshot_uji: Path) -> None:
    """Snapshot lama tidak boleh menyamar segar — waktu diambil dari 'dibuat'."""
    with session_scope() as s:
        publish_snapshot(s, snapshot_uji)
    with session_scope() as s:
        f = s.query(Fact).filter_by(key="mode").one()
    assert f.observed_at.year == 2026 and f.observed_at.hour == 20


def test_parity_nilai_db_sama_dengan_berkas(db, snapshot_uji: Path) -> None:
    """20 kunci acak (semua kunci di sini) — nilai DB harus identik dengan berkas."""
    payload = json.loads(snapshot_uji.read_text(encoding="utf-8"))
    with session_scope() as s:
        publish_snapshot(s, snapshot_uji)
    with session_scope() as s:
        rows = {f.key: f.value_json for f in s.query(Fact).filter_by(kind="snapshot").all()}

    kunci = random.sample(sorted(payload.keys()), k=min(20, len(payload)))
    for k in kunci:
        assert rows[k] == payload[k], f"nilai {k} berbeda antara DB dan berkas"


def test_hash_kanonik_stabil() -> None:
    a = {"b": 1, "a": [1, 2]}
    b = {"a": [1, 2], "b": 1}
    assert canonical_hash(a) == canonical_hash(b)


def test_terbit_dua_kali_tidak_gagal_dan_tidak_menggandakan(db, snapshot_uji: Path) -> None:
    jml = len(json.loads(snapshot_uji.read_text(encoding="utf-8")))
    with session_scope() as s:
        publish_snapshot(s, snapshot_uji)
    with session_scope() as s:
        publish_snapshot(s, snapshot_uji)
    with session_scope() as s:
        n = s.query(Fact).filter_by(kind="snapshot").count()
    assert n == jml, "fakta dengan (kind,key,observed_at) sama tidak boleh terduplikasi"


def test_event_tercatat_dengan_fact_ids(db, snapshot_uji: Path) -> None:
    jml = len(json.loads(snapshot_uji.read_text(encoding="utf-8")))
    with session_scope() as s:
        publish_snapshot(s, snapshot_uji)
    with session_scope() as s:
        ev = s.query(Event).filter_by(type="snapshot.published").one()
    assert ev.actor == "worker"
    assert len(ev.fact_ids) == jml
    assert ev.payload_json["count"] == jml


def test_berkas_tidak_ada_tidak_menulis_apa_pun(db, tmp_path: Path) -> None:
    with session_scope() as s:
        rep = publish_snapshot(s, tmp_path / "tidak-ada.json")
    assert rep.status == "tidak-ada"
    with session_scope() as s:
        assert s.query(Fact).filter_by(kind="snapshot").count() == 0


def test_berkas_rusak_dilaporkan_bukan_ditebak(db, tmp_path: Path) -> None:
    bad = tmp_path / "rusak.json"
    bad.write_text("{ini bukan json", encoding="utf-8")
    with session_scope() as s:
        rep = publish_snapshot(s, bad)
    assert rep.status == "rusak"
    assert "JSONDecodeError" in rep.detail


@pytest.mark.skipif(not SNAPSHOT_ASLI.exists(), reason="snapshot asli tidak ada di mesin ini")
def test_parity_dengan_snapshot_asli(db) -> None:
    """Bukti P1-T6: 20 fakta dari snapshot nyata — nilai DB == nilai berkas."""
    payload = json.loads(SNAPSHOT_ASLI.read_text(encoding="utf-8"))
    with session_scope() as s:
        rep = publish_snapshot(s, SNAPSHOT_ASLI)
    assert rep.status == "ok"
    with session_scope() as s:
        rows = {f.key: f.value_json for f in s.query(Fact).filter_by(kind="snapshot").all()}
    kunci = random.sample(sorted(payload.keys()), k=min(20, len(payload)))
    beda = [k for k in kunci if rows.get(k) != payload[k]]
    assert not beda, f"nilai berbeda untuk: {beda}"


def test_fakta_basi_terdeteksi_lewat_ttl(db, snapshot_uji: Path) -> None:
    """TTL 600 s: snapshot berumur 20 jam harus berstatus basi (dihitung dari observed_at)."""
    with session_scope() as s:
        publish_snapshot(s, snapshot_uji)
    with session_scope() as s:
        f = s.query(Fact).filter_by(key="mode").one()
        umur = datetime.now(UTC) - f.observed_at
    assert umur > timedelta(seconds=f.ttl_s)

# --- Regresi: perangkap `dibuat` berformat WIB tanpa penanda zona ---------------------------
#
# Gejala yang pernah terjadi di produksi: snapshot dibangun 18:43 WIB, tetapi `dibuat` diumpankan
# apa adanya ke `fromisoformat` sehingga jamnya dianggap UTC → fakta terlihat 7 jam lebih tua.
# Akibatnya (a) badge kesegaran selalu salah, dan (b) `on_conflict_do_nothing` pada
# (kind, key, observed_at) terus menabrak baris lama, jadi fakta baru TIDAK PERNAH masuk.

def test_dibuat_wib_tidak_mundur_tujuh_jam(tmp_path):
    """`dibuat` berformat "<tgl> <jam> WIB" (UTC+7) dikonversi ke UTC dan sesuai mtime."""
    import datetime as dt

    from warroom_worker.facts_publish import _observed_at

    berkas = tmp_path / "snapshot.json"
    berkas.write_text("{}", encoding="utf-8")
    mtime = dt.datetime.fromtimestamp(berkas.stat().st_mtime, tz=dt.UTC)
    wib_str = (mtime + dt.timedelta(hours=7)).strftime("%Y-%m-%d %H:%M:%S WIB")
    hasil = _observed_at({"dibuat": wib_str}, berkas)
    # Harus sesuai mtime (selisih <= 2 detik), bukan melompat 7 jam ke depan atau ke belakang.
    assert abs((hasil.astimezone(dt.UTC) - mtime).total_seconds()) <= 2


def test_dibuat_iso_berzona_dipakai_apa_adanya(tmp_path):
    import datetime as dt

    from warroom_worker.facts_publish import _observed_at

    berkas = tmp_path / "snapshot.json"
    berkas.write_text("{}", encoding="utf-8")
    hasil = _observed_at({"dibuat": "2026-10-04T18:43:19+07:00"}, berkas)
    assert hasil.utcoffset() == dt.timedelta(hours=7)
    assert (hasil.year, hasil.month, hasil.day, hasil.hour) == (2026, 10, 4, 18)


def test_tanpa_dibuat_pakai_mtime(tmp_path):
    import datetime as dt

    from warroom_worker.facts_publish import _observed_at

    berkas = tmp_path / "snapshot.json"
    berkas.write_text("{}", encoding="utf-8")
    hasil = _observed_at({}, berkas)
    mtime = dt.datetime.fromtimestamp(berkas.stat().st_mtime, tz=dt.UTC)
    assert abs((hasil - mtime).total_seconds()) < 2


def test_dibuat_rusak_jatuh_ke_mtime(tmp_path):
    import datetime as dt

    from warroom_worker.facts_publish import _observed_at

    berkas = tmp_path / "snapshot.json"
    berkas.write_text("{}", encoding="utf-8")
    hasil = _observed_at({"dibuat": "bukan waktu sama sekali"}, berkas)
    mtime = dt.datetime.fromtimestamp(berkas.stat().st_mtime, tz=dt.UTC)
    assert abs((hasil - mtime).total_seconds()) < 2
