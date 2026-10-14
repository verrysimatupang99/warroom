#!/usr/bin/env python3
"""Pecah jobs.py -> paket jobs/ (AST-based, tabel per fungsi).

Menulis jobs/*.py + __init__.py yang re-export SEMUA nama lama (agar
`from warroom_worker.jobs import X` tetap identik). Verifikasi: pytest services/worker.
"""
from __future__ import annotations

import ast
from pathlib import Path

SRC = Path("services/worker/src/warroom_worker/jobs.py")
OUT = SRC.parent / "jobs"

# nama top-level -> modul tujuan
PETA = {
    # base: konstanta + helper bersama
    "root_dir": "base",
    "_lt_bin": "base",
    "_jalankan_lt": "base",
    "_tulis_fakta": "base",
    "_alert": "base",
    "_fakta_terbaru": "base",
    "_ringkas_fakta": "base",
    "_pesan_sinyal": "base",
    "_pelajaran_terakhir": "base",
    "_unit_state": "base",
    "_upsert_service": "base",
    # infra
    "handler_publish_facts": "infra",
    "handler_freshness": "infra",
    "handler_notify": "infra",
    "handler_collect": "infra",
    "handler_refresh_snapshot": "infra",
    "handler_radar_update": "infra",
    "handler_lp_mark": "infra",
    "handler_backup": "infra",
    "handler_source_health": "infra",
    "handler_retensi": "housekeeping",
    # domain
    "handler_poly_sync": "domain",
    "handler_verdict_sync": "domain",
    "handler_parity_drift": "domain",
    "handler_lpagent_sync": "domain",
    "handler_reconcile": "domain",
    "handler_rekonsiliasi_crypto": "domain",
    "handler_gmgn_sync": "domain",
    "handler_signal_sync": "domain",
    # llm / paper
    "handler_learner": "llm",
    "handler_prompts_sync": "llm",
    "handler_llm_brief": "llm",
    "handler_paper_eval": "llm",
    "_pair_sudah_dipakai": "llm",
    "_kandidat_terbaru_dari_ledger": "llm",
    "handler_paper_scan": "llm",
}

HEADERS = {
    "base": (
        '"""Basis handler job worker: path, pemanggil CLI domain, penulis fakta, alert."""\n\n'
        "from __future__ import annotations\n\n"
        "import json\nimport logging\nimport os\nimport subprocess\nfrom pathlib import Path\n"
        "from typing import Any\n\n"
        "from sqlalchemy import select\n"
        "from warroom_core.db import Alert, Event, Fact, Job, SASession, session_scope\n\n"
        'log = logging.getLogger("warroom_worker.jobs")\n\n'
    ),
    "infra": (
        '"""Handler job infra: freshness, notify, collect, snapshot, radar, lp, backup."""\n\n'
        "from __future__ import annotations\n\n"
        "import json\nimport logging\nimport os\nimport shutil\nimport subprocess\nimport zipfile\n"
        "from datetime import UTC, datetime, timedelta\n"
        "from pathlib import Path\nfrom typing import Any\n\n"
        "from sqlalchemy import select\n"
        "from warroom_core.db import Alert, Event, Fact, Job, Parameter, SASession, session_scope\n\n"
        "from .base import (\n"
        "    _alert,\n    _fakta_terbaru,\n    _jalankan_lt,\n    _lt_bin,\n    _ringkas_fakta,\n"
        "    _tulis_fakta,\n    root_dir,\n)\n\n"
        'log = logging.getLogger("warroom_worker.jobs")\n\n'
    ),
    "domain": (
        '"""Handler job domain: sinkronisasi verdict/parity/rekonsiliasi/gmgn/sinyal."""\n\n'
        "from __future__ import annotations\n\n"
        "import json\nimport logging\nimport os\nfrom datetime import UTC, datetime\n"
        "from pathlib import Path\nfrom typing import Any\n\n"
        "from sqlalchemy import select\n"
        "from warroom_core.db import Fact, Job, SASession, session_scope\n\n"
        "from .base import (\n"
        "    _alert,\n    _fakta_terbaru,\n    _jalankan_lt,\n    _pesan_sinyal,\n    _ringkas_fakta,\n"
        "    _tulis_fakta,\n    root_dir,\n)\n\n"
        'log = logging.getLogger("warroom_worker.jobs")\n\n'
    ),
    "llm": (
        '"""Handler job LLM & paper: learner, prompts, llm-brief, paper-eval/scan."""\n\n'
        "from __future__ import annotations\n\n"
        "import json\nimport logging\nimport os\nfrom datetime import UTC, datetime, timedelta\n"
        "from pathlib import Path\nfrom typing import Any\n\n"
        "from sqlalchemy import select\n"
        "from warroom_core.db import Fact, Job, SASession, session_scope\n\n"
        "from .base import (\n"
        "    _alert,\n    _fakta_terbaru,\n    _pelajaran_terakhir,\n    _ringkas_fakta,\n"
        "    _tulis_fakta,\n    root_dir,\n)\n\n"
        'log = logging.getLogger("warroom_worker.jobs")\n\n'
    ),
    "housekeeping": (
        '"""Handler job housekeeping: retensi."""\n\n'
        "from __future__ import annotations\n\n"
        "import logging\nfrom typing import Any\n\n"
        "from warroom_core import retention\nfrom warroom_core.db import Job, SASession\n\n"
        'log = logging.getLogger("warroom_worker.jobs")\n\n'
    ),
}


def potong(sumber: str):
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
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            blok[node.target.id] = "".join(lines[node.lineno - 1 : node.end_lineno]) + "\n\n"
    return blok


def main() -> int:
    sumber = SRC.read_text()
    blok = potong(sumber)
    OUT.mkdir(exist_ok=True)

    isi: dict[str, list[str]] = {m: [] for m in HEADERS}
    for nama, mod in PETA.items():
        if nama in blok:
            isi[mod].append(blok[nama])
        else:
            print(f"  PERINGATAN: {nama} tak ditemukan")

    for mod, bagian in isi.items():
        (OUT / f"{mod}.py").write_text(HEADERS[mod] + "".join(bagian))
        print(f"tulis {mod}.py ({len(bagian)} blok)")

    # register_handlers: ambil blok aslinya, impor handler dari modul
    reg = blok.get("register_handlers", "")
    (OUT / "_register.py").write_text(
        '"""Registrasi handler job ke schedule."""\n\n'
        "from __future__ import annotations\n\n"
        "from typing import Any\n\n"
        "from .domain import (\n"
        "    handler_gmgn_sync, handler_lpagent_sync, handler_parity_drift, handler_poly_sync,\n"
        "    handler_reconcile, handler_rekonsiliasi_crypto, handler_signal_sync,\n"
        "    handler_verdict_sync,\n)\n"
        "from .housekeeping import handler_retensi\n"
        "from .infra import (\n"
        "    handler_backup, handler_collect, handler_freshness, handler_lp_mark,\n"
        "    handler_notify, handler_publish_facts, handler_radar_update,\n"
        "    handler_refresh_snapshot, handler_source_health,\n"
        ")\n"
        "from .llm import (\n"
        "    handler_learner, handler_llm_brief, handler_paper_eval, handler_paper_scan,\n"
        "    handler_prompts_sync,\n"
        ")\n\n"
        + reg
    )
    print("tulis _register.py")

    reexp = []
    for n in PETA:
        reexp.append(f"from .{PETA[n]} import {n}  # noqa: F401")
    (OUT / "__init__.py").write_text(
        '"""Handler job worker (paket; dipecah dari jobs.py 14 Okt 2026).\n\n'
        "Re-export semua nama lama agar `from warroom_worker.jobs import X` tetap sama.\n"
        '"""\n\n'
        "from __future__ import annotations\n\n"
        + "\n".join(reexp)
        + "\nfrom ._register import register_handlers  # noqa: F401\n\n"
        + "__all__ = [\n"
        + "".join(f'    "{n}",\n' for n in PETA)
        + '    "register_handlers",\n]\n'
    )
    print("tulis __init__.py")
    SRC.unlink()
    print("jobs.py dihapus (digantikan paket jobs/)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
