"""War Room core — façade tipis ke domain `live-trading`.

Domain (collectors, signals, risk, execution, measure, backtest, equity) tetap tinggal
di repo `../live-trading` beserta 219 tesnya. Paket ini ada supaya layanan platform
(`services/*`) bergantung pada satu nama yang stabil, bukan pada path relatif.

Aturan: tidak ada logika domain yang disalin ke sini. Kalau butuh fungsi baru,
tambahkan di `live-trading`, lalu ekspor ulang di sini.
"""

from __future__ import annotations

import os
from pathlib import Path

import live_trading
from live_trading import config as domain_config

from warroom_core.specs import ExecutionSpec, HypothesisSpec, SpecError

__all__ = [
    "DOMAIN_VERSION",
    "ExecutionSpec",
    "HypothesisSpec",
    "SpecError",
    "domain_version",
    "paths",
    "prompts_dir",
    "repo_root",
]

DOMAIN_VERSION: str = live_trading.__version__


def domain_version() -> str:
    """Versi paket domain yang sedang dipakai platform."""
    return live_trading.__version__


def repo_root() -> Path:
    """Akar monorepo War Room (berisi `prompts/`).

    Ditelusuri dari lokasi paket ini, bukan dari `cwd`: worker dan API dijalankan systemd
    dengan cwd berbeda-beda, dan berkas prompt bukan milik domain.
    """
    env = os.environ.get("WARROOM_REPO_ROOT")
    if env:
        return Path(env)
    for basis in (Path(__file__).resolve(), Path.cwd().resolve()):
        for kandidat in (basis, *basis.parents):
            if (kandidat / "prompts").is_dir() and (kandidat / "pyproject.toml").is_file():
                return kandidat
    return Path.home() / "warroom"


def prompts_dir() -> Path:
    """Direktori registry prompt (env `WARROOM_PROMPTS_DIR` menimpa)."""
    return Path(os.environ.get("WARROOM_PROMPTS_DIR") or (repo_root() / "prompts"))


def paths() -> dict[str, str]:
    """Path efektif domain (home, state, secrets, ledger) — satu sumber, bukan tebakan."""
    s = domain_config.get_settings()
    return {
        "home": str(s.home),
        "state_dir": str(s.state_dir),
        "secrets_dir": str(s.secrets_dir),
        "ledger_path": str(s.ledger_path),
    }
