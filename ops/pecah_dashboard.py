#!/usr/bin/env python3
"""Pecah dashboard.py -> paket dashboard/ (AST-based, tabel eksplisit).

Menjalankan sekali; menulis dashboard/*.py dan __init__.py. Cara pakai:
    python ops/pecah_dashboard.py
Verifikasi setelahnya: pytest packages/live-trading/tests/test_dashboard.py
"""
from __future__ import annotations

import ast
from pathlib import Path

SRC = Path("packages/live-trading/src/live_trading/dashboard.py")
OUT = SRC.parent / "dashboard"

# nama top-level -> modul tujuan (urut sesuai sumber)
PETA = {
    "log": "format",
    "GMGN_DIR": "panels",
    "_FRONTEND_DIR": "panels",
    "_ASETS_DIR": "panels",
    "e": "format",
    "_persen": "format",
    "fharga": "format",
    "MODEL_POD": "format",
    "_wib": "format",
    "_backtest_panel": "panels",
    "_RADAR_SEGAR_MNT": "panels",
    "_radar_ringkas": "panels",
    "_radar_panel": "panels",
    "_lencana_lp": "panels",
    "_arti_lp": "panels",
    "WARNA_POD": "panels",
    "_pod_card": "panels",
    "_lp_panel": "panels",
    "_POLY_ARMS": "panels",
    "_poly_panel": "panels",
    "_gmgn_panel": "panels",
    "build_snapshot": "panels",
    "load_snapshot": "panels",
    "_grafik_ekuitas": "fragments",
    "_bar_pair": "fragments",
    "_TERMINAL": "fragments",
    "_ringkas": "fragments",
    "_radar_tabs": "fragments",
    "_cur": "fragments",
    "_e": "fragments",
    "_card": "fragments",
    "_ubin": "fragments",
    "_lencana": "fragments",
    "_sumber": "fragments",
    "_arti": "fragments",
    "_grup": "fragments",
    "_tab": "fragments",
    "_grup_badge": "fragments",
    "_ctx": "fragments",
    "_nav": "fragments",
    "_sparkline": "fragments",
    "_bar_divergen": "fragments",
    "_minibar": "fragments",
    "_hero": "fragments",
    "_kepala": "fragments",
    "_status_halaman": "fragments",
    "_blok": "fragments",
    "_rakit": "fragments",
    "_css": "fragments",
    "render": "server",
    "_SHELL": "server",
    "serve": "server",
    "render_shell": "server",
    "_KLINES_TTL": "server",
    "_klines": "server",
    "fragments": "server",
    "FRAGMEN_HALAMAN": "server",
}

HEADER = {
    "format": '"""Format angka & waktu dashboard (dipisah dari dashboard.py)."""\n\n'
    "from __future__ import annotations\n\nimport datetime as dt\n"
    "import html\n\nfrom .format_helpers import e  # noqa: F401 (re-export)\n",
    "panels": None,   # ditulis di bawah
    "fragments": None,
    "server": None,
}


def potong(sumber: str):
    """Kembalikan dict nama -> teks blok (termasuk dekorator)."""
    lines = sumber.splitlines(keepends=True)
    tree = ast.parse(sumber)
    blok = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name:
            start = node.lineno
            if getattr(node, "decorator_list", None):
                start = min(d.lineno for d in node.decorator_list)
            blok[node.name] = "".join(lines[start - 1 : node.end_lineno]) + "\n\n"
        elif isinstance(node, ast.Assign):
            if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                blok[node.targets[0].id] = "".join(lines[node.lineno - 1 : node.end_lineno]) + "\n\n"
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            pass  # import ditulis manual per modul
    return blok


def main() -> int:
    sumber = SRC.read_text()
    blok = potong(sumber)
    OUT.mkdir(exist_ok=True)

    isi = {"format": [], "panels": [], "fragments": [], "server": []}
    for nama, mod in PETA.items():
        if nama in blok:
            isi[mod].append(blok[nama])
        else:
            print(f"  PERINGATAN: {nama} tak ditemukan sebagai top-level")

    # header import tiap modul (disesuaikan kebutuhan)
    headers = {
        "format": (
            '"""Format angka & waktu (dipisah dari dashboard.py)."""\n\n'
            "from __future__ import annotations\n\n"
            "import datetime as dt\n"
            "import html\n"
            "import logging\n\n"
            'e = html.escape\n'
            'log = logging.getLogger("live_trading.dashboard")\n\n'
        ),
        "panels": (
            '"""Panel data dashboard: radar, lp, poly, gmgn, snapshot."""\n\n'
            "from __future__ import annotations\n\n"
            "import json\n"
            "import logging\n"
            "from pathlib import Path\n"
            "from typing import Any\n\n"
            "from ..config import Settings, get_settings\n"
            "from ..risk import RiskGate\n"
            "from .format import MODEL_POD, _persen, _wib, e, fharga, log\n\n"
        ),
        "fragments": (
            '"""Fragmen HTML dashboard (string builder)."""\n\n'
            "from __future__ import annotations\n\n"
            "import datetime as dt\n"
            "import html\n"
            "from typing import Any\n\n"
            "from .format import MODEL_POD, _persen, _wib, e, fharga\n"
            "from .panels import WARNA_POD\n\n"
            "_e = html.escape\n\n"
        ),
        "server": (
            '"""Server HTTP dashboard + render halaman."""\n\n'
            "from __future__ import annotations\n\n"
            "import datetime as dt\n"
            "import logging\n"
            "from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer\n"
            "from pathlib import Path\n"
            "from typing import Any\n\n"
            "from ..config import Settings, get_settings\n"
            "from .fragments import (\n"
            "    _blok,\n"
            "    _css,\n"
            "    _hero,\n"
            "    _kepala,\n"
            "    _rakit,\n"
            "    _status_halaman,\n"
            ")\n"
            "from .panels import build_snapshot, load_snapshot\n\n"
            'log = logging.getLogger("live_trading.dashboard")\n\n'
        ),
    }

    for mod, bagian in isi.items():
        teks = headers[mod] + "".join(bagian)
        (OUT / f"{mod}.py").write_text(teks)
        print(f"tulis {mod}.py ({len(bagian)} blok)")

    # __init__.py: re-export semua nama lama
    reexp = []
    for nama, mod in PETA.items():
        reexp.append(f"from .{mod} import {nama}  # noqa: F401")
    (OUT / "__init__.py").write_text(
        '"""Dashboard satu layar (paket; dipecah dari dashboard.py 14 Okt 2026).\n\n'
        "Re-export semua nama lama agar `from live_trading import dashboard` tetap sama.\n"
        '"""\n\n'
        "from __future__ import annotations\n\n"
        + "\n".join(reexp)
        + "\n\n__all__ = [\n"
        + "".join(f'    "{n}",\n' for n in PETA)
        + "]\n"
    )
    print("tulis __init__.py")

    SRC.unlink()
    print("dashboard.py dihapus (digantikan paket dashboard/)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
