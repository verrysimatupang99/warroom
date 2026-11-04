"""Dashboard satu layar (paket; dipecah dari dashboard.py 14 Okt 2026).

Re-export semua nama lama agar `from live_trading import dashboard` tetap sama.
"""

from __future__ import annotations

from .format import (
    _persen,  # noqa: F401
    _wib,  # noqa: F401
    e,  # noqa: F401
    fharga,  # noqa: F401
    log,  # noqa: F401
)
from .page_parts import (
    _TERMINAL,  # noqa: F401
    _arti,  # noqa: F401
    _bar_divergen,  # noqa: F401
    _bar_pair,  # noqa: F401
    _blok,  # noqa: F401
    _card,  # noqa: F401
    _css,  # noqa: F401
    _ctx,  # noqa: F401
    _cur,  # noqa: F401
    _e,  # noqa: F401
    _grafik_ekuitas,  # noqa: F401
    _grup,  # noqa: F401
    _grup_badge,  # noqa: F401
    _hero,  # noqa: F401
    _kepala,  # noqa: F401
    _lencana,  # noqa: F401
    _minibar,  # noqa: F401
    _nav,  # noqa: F401
    _radar_tabs,  # noqa: F401
    _rakit,  # noqa: F401
    _ringkas,  # noqa: F401
    _sparkline,  # noqa: F401
    _status_halaman,  # noqa: F401
    _sumber,  # noqa: F401
    _tab,  # noqa: F401
    _ubin,  # noqa: F401
)
from .panels import (
    _ASETS_DIR,  # noqa: F401
    _FRONTEND_DIR,  # noqa: F401
    _POLY_ARMS,  # noqa: F401
    _RADAR_SEGAR_MNT,  # noqa: F401
    GMGN_DIR,  # noqa: F401
    WARNA_POD,  # noqa: F401
    _arti_lp,  # noqa: F401
    _backtest_panel,  # noqa: F401
    _gmgn_panel,  # noqa: F401
    _lencana_lp,  # noqa: F401
    _lp_panel,  # noqa: F401
    _pod_card,  # noqa: F401
    _poly_panel,  # noqa: F401
    _radar_panel,  # noqa: F401
    _radar_ringkas,  # noqa: F401
    build_snapshot,  # noqa: F401
    load_snapshot,  # noqa: F401
)
from .server import (
    _KLINES_TTL,  # noqa: F401
    _SHELL,  # noqa: F401
    FRAGMEN_HALAMAN,  # noqa: F401
    _klines,  # noqa: F401
    fragments,  # noqa: F401
    render,  # noqa: F401
    render_shell,  # noqa: F401
    serve,  # noqa: F401
)

__all__ = [
    "log",
    "GMGN_DIR",
    "_FRONTEND_DIR",
    "_ASETS_DIR",
    "e",
    "_persen",
    "fharga",
    "_wib",
    "_backtest_panel",
    "_RADAR_SEGAR_MNT",
    "_radar_ringkas",
    "_radar_panel",
    "_lencana_lp",
    "_arti_lp",
    "WARNA_POD",
    "_pod_card",
    "_lp_panel",
    "_POLY_ARMS",
    "_poly_panel",
    "_gmgn_panel",
    "build_snapshot",
    "load_snapshot",
    "_grafik_ekuitas",
    "_bar_pair",
    "_TERMINAL",
    "_ringkas",
    "_radar_tabs",
    "_cur",
    "_e",
    "_card",
    "_ubin",
    "_lencana",
    "_sumber",
    "_arti",
    "_grup",
    "_tab",
    "_grup_badge",
    "_ctx",
    "_nav",
    "_sparkline",
    "_bar_divergen",
    "_minibar",
    "_hero",
    "_kepala",
    "_status_halaman",
    "_blok",
    "_rakit",
    "_css",
    "render",
    "_SHELL",
    "serve",
    "render_shell",
    "_KLINES_TTL",
    "_klines",
    "fragments",
    "FRAGMEN_HALAMAN",
]
