"""War Room core — façade tipis ke domain `live-trading`.

Domain (collectors, signals, risk, execution, measure, backtest, equity) tetap tinggal
di repo `../live-trading` beserta 219 tesnya. Paket ini ada supaya layanan platform
(`services/*`) bergantung pada satu nama yang stabil, bukan pada path relatif.

Aturan: tidak ada logika domain yang disalin ke sini. Kalau butuh fungsi baru,
tambahkan di `live-trading`, lalu ekspor ulang di sini.
"""

from __future__ import annotations

import live_trading
from live_trading import config as domain_config

__all__ = ["DOMAIN_VERSION", "domain_version", "paths"]

DOMAIN_VERSION: str = live_trading.__version__


def domain_version() -> str:
    """Versi paket domain yang sedang dipakai platform."""
    return live_trading.__version__


def paths() -> dict[str, str]:
    """Path efektif domain (home, state, secrets, ledger) — satu sumber, bukan tebakan."""
    s = domain_config.get_settings()
    return {
        "home": str(s.home),
        "state_dir": str(s.state_dir),
        "secrets_dir": str(s.secrets_dir),
        "ledger_path": str(s.ledger_path),
    }
