"""Regresi: split beku (P1 roadmap 5 Okt 2026).

Yang dikunci di sini:
1. Split yang TIDAK punya penanda hasil DITOLAK untuk dibekukan — lebih baik menolak
   daripada membuat split kosong yang terlihat sah (recorder Poly belum menulis outcome).
2. Split yang punya penanda hasil bisa dibekukan; id-nya terdaftar + tercatat sebagai
   event `dataset.frozen`.
3. `verifikasi` mendeteksi dataset yang berubah setelah dibekukan (sha256).
4. `split_untuk_gate` tidak pernah mengarang label untuk id yang tak terdaftar.
"""

from __future__ import annotations

import gzip
import json
import shutil
from pathlib import Path

import pytest
from warroom_core import splits
from warroom_core.db import Event, FrozenSplit, session_scope


@pytest.fixture(autouse=True)
def _bersihkan(db):
    with session_scope() as s:
        s.query(FrozenSplit).delete()
        s.query(Event).filter(Event.type == "dataset.frozen").delete()
    yield


def _buat_run(tmp_path: Path, *, dengan_outcome: bool) -> Path:
    d = tmp_path / "auto-20261005t000000z"
    d.mkdir(parents=True, exist_ok=True)
    (d / "manifest.json").write_text(
        json.dumps({"codeHashes": {"recorder": "abc"}, "partition": {"firstFullWindow": 1791158700,
                                                                    "holdoutStart": 1791159600}}),
        encoding="utf-8",
    )
    baris = [json.dumps({"kind": "decision", "partition": "holdout", "side": "Up", "token": "1"})]
    if dengan_outcome:
        baris.append(json.dumps({"kind": "resolution", "outcome": "won", "token": "1"}))
    with gzip.open(d / "events-0000.jsonl.gz", "wt", encoding="utf-8") as fh:
        fh.write("\n".join(baris) + "\n")
    return d


def test_split_tanpa_outcome_ditolak(db, tmp_path: Path) -> None:
    """Tanpa penanda hasil, split tidak bisa dinilai → jangan pernah dibekukan."""
    d = _buat_run(tmp_path, dengan_outcome=False)
    with session_scope() as s:
        with pytest.raises(ValueError, match="penanda hasil"):
            splits.bekukan(s, dataset="paired", root=d)
    with session_scope() as s:
        assert s.query(FrozenSplit).count() == 0


def test_split_dengan_outcome_dibekukan_dan_tercatat(db, tmp_path: Path) -> None:
    d = _buat_run(tmp_path, dengan_outcome=True)
    with session_scope() as s:
        hasil = splits.bekukan(s, dataset="paired", root=d, created_by="uji")
    assert hasil["split"].startswith("frozen:")
    assert hasil["ada_outcome"] is True
    assert hasil["files"] == 1

    with session_scope() as s:
        assert splits.split_untuk_gate(s, hasil["id"]) == hasil["split"]
        ev = s.query(Event).filter_by(type="dataset.frozen").one()
        assert ev.payload_json["split"] == hasil["split"]


def test_verifikasi_mendeteksi_dataset_berubah(db, tmp_path: Path) -> None:
    d = _buat_run(tmp_path, dengan_outcome=True)
    with session_scope() as s:
        hasil = splits.bekukan(s, dataset="paired", root=d)
    with session_scope() as s:
        assert splits.verifikasi(s, hasil["id"])["cocok"] is True

    # ubah berkas setelah dibekukan
    with gzip.open(d / "events-0000.jsonl.gz", "wt", encoding="utf-8") as fh:
        fh.write(json.dumps({"kind": "resolution", "outcome": "lost"}) + "\n")
    with session_scope() as s:
        v = splits.verifikasi(s, hasil["id"])
        assert v["cocok"] is False
        assert v["berubah"] == ["events-0000.jsonl.gz"]


def test_split_untuk_gate_tidak_mengarang(db) -> None:
    with session_scope() as s:
        assert splits.split_untuk_gate(s, "tidak-ada-123") is None


def test_split_kosong_ditolak(db, tmp_path: Path) -> None:
    d = tmp_path / "kosong"
    d.mkdir()
    with session_scope() as s:
        with pytest.raises(ValueError, match="tidak ada berkas"):
            splits.bekukan(s, dataset="paired", root=d)


def test_split_untuk_gate_menolak_dataset_yang_hilang(db, tmp_path: Path) -> None:
    """Regresi 23 Okt 2026: split terdaftar tapi berkasnya hilang tetap diloloskan gate.

    Split ``poly-paired-131d1ab4aed5`` melaporkan 411 berkas hilang dari disk, tetapi
    ``split_untuk_gate`` masih mengembalikan ``frozen:...`` sehingga gate menerima bukti
    dari dataset yang sudah tidak ada. Sekarang harus ``None``.
    """
    d = _buat_run(tmp_path, dengan_outcome=True)
    with session_scope() as s:
        hasil = splits.bekukan(s, dataset="paired", root=d)

    # Sebelum dihapus: split sah dan boleh dipakai gate.
    with session_scope() as s:
        assert splits.split_untuk_gate(s, hasil["id"]) == hasil["split"]

    # Dataset dihilangkan dari disk: gate TIDAK boleh lagi menerima split ini.
    shutil.rmtree(d)
    with session_scope() as s:
        assert splits.split_untuk_gate(s, hasil["id"]) is None
