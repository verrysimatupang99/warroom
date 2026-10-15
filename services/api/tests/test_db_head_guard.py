"""P0-4: mekanisme pencegahan migrasi DB tertinggal.

Kejadian 14 Okt 2026: kode merge tapi migrasi belum diterapkan -> produksi
tertinggal 3 revisi. Permanen: ExecStartPre `ops/check-db-head.py --upgrade`
di unit api & worker, sehingga unit tidak akan start dengan skema basi.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OPS = ROOT / "ops"


def _baca(nama: str) -> str:
    return (OPS / nama).read_text()


def test_unit_api_dan_worker_punya_execstartpre_migrasi() -> None:
    for nama in ("warroom-api.service", "warroom-worker.service"):
        unit = _baca(nama)
        assert "ExecStartPre=" in unit, f"{nama} tanpa ExecStartPre migrasi"
        baris = [
            line for line in unit.splitlines()
            if line.startswith("ExecStartPre=") and "check-db-head.py" in line
        ]
        assert baris, f"{nama} tidak memanggil check-db-head.py di ExecStartPre"
        assert "CHECK_DB_HEAD_REQUIRED=1" in unit, (
            f"{nama} tanpa CHECK_DB_HEAD_REQUIRED=1 (guard bisa bisu tanpa DB_URL)"
        )
    api = _baca("warroom-api.service")
    worker = _baca("warroom-worker.service")
    pre_api = [line for line in api.splitlines() if line.startswith("ExecStartPre=")]
    assert pre_api and "--upgrade" in pre_api[0], "api: ExecStartPre tanpa --upgrade"
    # Temuan QA 15 Okt: hanya api yang upgrade; worker verifikasi saja.
    pre_worker = [line for line in worker.splitlines() if line.startswith("ExecStartPre=")]
    assert pre_worker and "--upgrade" not in pre_worker[0], (
        "worker tidak boleh menjalankan --upgrade (risiko alembic paralel)"
    )


def test_check_db_head_gagal_bila_warroom_db_url_kosong_tapi_upgrade_minta_lewat() -> None:
    # Tanpa WARROOM_DB_URL: skenario CI tanpa DB -> lewat (0), BUKAN lulus palsu.
    r = subprocess.run(
        [sys.executable, str(OPS / "check-db-head.py")],
        cwd=ROOT, capture_output=True, text=True,
        env={"PATH": "/usr/bin:/bin", "HOME": "/home/admin"},
    )
    assert r.returncode == 0
    assert "LEWAT" in r.stdout


def test_check_db_head_required_gagal_tanpa_warroom_db_url() -> None:
    # CHECK_DB_HEAD_REQUIRED=1 (dipakai unit systemd): tanpa DB_URL -> GAGAL, bukan bisu.
    r = subprocess.run(
        [sys.executable, str(OPS / "check-db-head.py")],
        cwd=ROOT, capture_output=True, text=True,
        env={"PATH": "/usr/bin:/bin", "HOME": "/home/admin", "CHECK_DB_HEAD_REQUIRED": "1"},
    )
    assert r.returncode == 1
    assert "GAGAL" in r.stdout


def test_check_db_head_terlihat_di_runbook_deploy() -> None:
    runbook = (ROOT / "ops" / "runbook-deploy.md").read_text()
    assert "check-db-head" in runbook, "runbook deploy belum menyebut cek migrasi"
