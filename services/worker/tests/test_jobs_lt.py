"""Tes pemilih biner `lt` — pelajaran mahal dari insiden `bagian` hilang.

Gejala yang pernah terjadi di produksi: job `refresh-snapshot` melaporkan `ok`, tetapi
`state/snapshot.json` hanya punya 7 bagian (macro/lp/overextended hilang) tanpa error apa pun.
Akar: `_jalankan_lt` mengambil `lt` dari `WARROOM_DOMAIN_HOME/.venv/bin/lt` — venv LAMA yang
meng-import dari source lama. Job jadi menjalankan kode sebelum merge.
"""

from __future__ import annotations

import sys
from pathlib import Path

from warroom_worker.jobs import _lt_bin


def test_memakai_venv_worker_bukan_venv_domain(monkeypatch, tmp_path: Path) -> None:
    """Venv tempat worker berjalan harus menang atas venv di WARROOM_DOMAIN_HOME."""
    venv_bin = tmp_path / "worker-venv-bin"
    venv_bin.mkdir()
    (venv_bin / "lt").write_text("#!/bin/sh\n", encoding="utf-8")
    domain = tmp_path / "domain"
    (domain / ".venv" / "bin").mkdir(parents=True)
    (domain / ".venv" / "bin" / "lt").write_text("#!/bin/sh\n", encoding="utf-8")

    monkeypatch.setattr(sys, "executable", str(venv_bin / "python"))
    monkeypatch.setenv("WARROOM_DOMAIN_HOME", str(domain))

    assert _lt_bin() == venv_bin / "lt"


def test_jatuh_ke_venv_domain_kalau_venv_worker_tidak_punya_lt(
    monkeypatch, tmp_path: Path
) -> None:
    """Kalau venv worker tidak punya `lt`, baru pakai venv domain — bukan gagal total."""
    venv_bin = tmp_path / "worker-venv-bin"
    venv_bin.mkdir()  # sengaja tanpa 'lt'
    domain = tmp_path / "domain"
    (domain / ".venv" / "bin").mkdir(parents=True)
    (domain / ".venv" / "bin" / "lt").write_text("#!/bin/sh\n", encoding="utf-8")

    monkeypatch.setattr(sys, "executable", str(venv_bin / "python"))
    monkeypatch.setenv("WARROOM_DOMAIN_HOME", str(domain))

    assert _lt_bin() == domain / ".venv" / "bin" / "lt"


def test_di_lingkungan_nyata_biner_lt_ada() -> None:
    """Di mesin ini, venv worker memang menyediakan `lt` (kalau tidak, semua job `lt` mati)."""
    biner = _lt_bin()
    assert biner.name == "lt"
    assert biner.exists(), f"lt tidak ada di {biner}"
