"""Titik masuk worker (P1-T4).

    python -m warroom_worker.run --once     # satu siklus (untuk uji/cron)
    python -m warroom_worker.run            # loop; unit systemd memakai ini

Log JSON satu baris per kejadian supaya bisa dibaca journald tanpa parsing rapuh.
Tidak pernah mencetak kredensial: `safe_url()` yang dipakai untuk menyebut DB.
"""

from __future__ import annotations

import argparse
import json
import signal
import sys
import time
from datetime import UTC, datetime

from warroom_core.db import dispose_engine, safe_url, session_scope

from warroom_worker.jobs import register_handlers
from warroom_worker.schedule import ensure_jobs, run_due

__all__ = ["main", "run_once", "setup"]

_stop = False


def log(event: str, **kw: object) -> None:
    print(json.dumps({"ts": datetime.now(UTC).isoformat(), "svc": "warroom-worker", "event": event, **kw}),
          flush=True)


def _handle_signal(signum: int, _frame: object) -> None:
    global _stop
    _stop = True
    log("signal", signum=signum, note="berhenti setelah siklus ini")


def setup() -> None:
    """Siapkan handler + pastikan job terdaftar di DB."""
    register_handlers()
    with session_scope() as s:
        dibuat = ensure_jobs(s)
    if dibuat:
        log("jobs.didaftarkan", jobs=dibuat)
    log("db", target=safe_url())


def run_once() -> list[dict[str, str]]:
    with session_scope() as s:
        hasil = run_due(s)
    for h in hasil:
        log("job", **h)
    if not hasil:
        log("idle", note="tidak ada job jatuh tempo")
    return hasil


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="warroom-worker", description="War Room worker (jadwal deklaratif)")
    ap.add_argument("--once", action="store_true", help="jalankan satu siklus lalu keluar")
    ap.add_argument("--every", type=int, default=30, help="detik antar siklus (default 30)")
    args = ap.parse_args(argv)

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    setup()
    if args.once:
        run_once()
        dispose_engine()
        return 0

    log("mulai", every_s=args.every)
    while not _stop:
        try:
            run_once()
        except Exception as exc:  # noqa: BLE001 — loop tidak boleh mati karena satu siklus gagal
            log("siklus.gagal", error=f"{type(exc).__name__}: {exc}")
        for _ in range(max(1, args.every)):
            if _stop:
                break
            time.sleep(1)
    dispose_engine()
    log("berhenti")
    return 0


if __name__ == "__main__":
    sys.exit(main())