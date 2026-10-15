#!/usr/bin/env python3
"""Satu siklus dompet paper $20 (crypto) — jalur produksi yang sama (15 Okt 2026).

Dompet ini BUKAN kode kedua: angka & keputusan dihasilkan oleh fungsi yang sama
yang dipakai produksi (`handler_paper_scan` + `handler_paper_eval`), hanya dijalankan
dengan dua env berbeda supaya akuntansinya terpisah:

    LT_HOME=/home/admin/live-trading/state-paper20   # ledger & posisi dompet $20
    LT_EQUITY_USD=20                                  # modal paper $20 (sizing 1%/trade)

Urutan siklus:
1. `lt scan --top 20`   → tulis verdicts.jsonl dompet $20 (gerbang struktur SMC).
2. handler_paper_scan   → buka posisi paper utk kandidat yang lolos gerbang risiko.
3. handler_paper_eval   → tutup posisi yang TS/TP-nya tersentuh (harga nyata).

Jalankan lewat systemd timer (paper20-cycle.timer, tiap 15 menit) ATAU manual:
    .venv/bin/python ops/paper20_cycle.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import UTC, datetime

HOME20 = "/home/admin/live-trading/state-paper20"
ENV20 = {
    **os.environ,
    "WARROOM_STATE_DIR": HOME20,
    "LT_HOME": HOME20,
    "LT_EQUITY_USD": "20",
    "LT_PAPER": "true",
}


def _stamp() -> str:
    return datetime.now(UTC).strftime("%H:%M:%S")


def _scan() -> int:
    lt = "/home/admin/warroom/.venv/bin/lt"
    r = subprocess.run([lt, "scan", "--top", "20"], env=ENV20,
                       capture_output=True, text=True, timeout=240)
    tail = (r.stdout or "").strip().splitlines()[-1:] or [""]
    print(f"[{_stamp()}] scan rc={r.returncode} {tail[0][:120]}")
    return r.returncode


def _handler(nama: str, payload: dict) -> None:
    """Panggil handler worker yang SAMA dengan produksi (jalur tunggal)."""
    os.environ.update(ENV20)
    from warroom_core.db import Job, session_scope
    from warroom_worker.jobs.llm import handler_paper_eval, handler_paper_scan

    with session_scope() as s:
        job = Job(name=nama, payload_json=payload)
        if nama == "paper-scan":
            print(f"[{_stamp()}] scan-open:", str(handler_paper_scan(s, job))[:180])
        else:
            print(f"[{_stamp()}] eval:", str(handler_paper_eval(s, job))[:180])


def main() -> int:
    rc = _scan()
    payload = {"jam_terakhir": 6, "jeda_pair_jam": 12, "ttl_s": 21600}
    _handler("paper-scan", payload)
    _handler("paper-eval", payload)
    return rc


if __name__ == "__main__":
    sys.exit(main())
