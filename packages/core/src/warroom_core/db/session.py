"""Koneksi DB — satu tempat, kredensial tidak pernah dicetak.

Sumber URL, berurutan:

1. env `WARROOM_DB_URL` (dipakai unit systemd lewat `EnvironmentFile=`),
2. berkas root-only `/etc/warroom/db.env` (pola `/etc/poly-pilot/*`),
3. gagal → `RuntimeError` dengan pesan yang **tidak** memuat kredensial.

`safe_url()` dipakai untuk log: menyembunyikan sandi.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session as SASession
from sqlalchemy.orm import sessionmaker

__all__ = ["db_url", "dispose_engine", "engine", "safe_url", "session_scope"]

ENV_FILE = Path("/etc/warroom/db.env")
_URL_RE = re.compile(r"^WARROOM_DB_URL=(.+)$", re.MULTILINE)

_engine: Engine | None = None
_Session: sessionmaker[SASession] | None = None


def _from_env_file() -> str | None:
    if not ENV_FILE.exists():
        return None
    try:
        text = ENV_FILE.read_text(encoding="utf-8", errors="replace")
    except PermissionError:
        return None
    m = _URL_RE.search(text)
    return m.group(1).strip().strip("\"'") if m else None


def db_url() -> str:
    """URL SQLAlchemy. Melempar RuntimeError bila tidak ada — tanpa membocorkan kredensial."""
    url = os.environ.get("WARROOM_DB_URL") or _from_env_file()
    if not url:
        raise RuntimeError(
            "WARROOM_DB_URL tidak ditemukan. Set env var, atau letakkan di "
            f"{ENV_FILE} (mode 600, root). Tidak ada kredensial yang dicetak di sini."
        )
    return url


def safe_url(url: str | None = None) -> str:
    """URL tanpa sandi — hanya untuk log/pesan error."""
    raw = url or os.environ.get("WARROOM_DB_URL") or _from_env_file() or ""
    return re.sub(r"://([^:/@]+):[^@]*@", r"://\1:***@", raw)


def engine() -> Engine:
    """Engine proses-tunggal (lazy). `pool_pre_ping` supaya koneksi mati tidak jadi 500 misterius."""
    global _engine
    if _engine is None:
        _engine = create_engine(db_url(), pool_pre_ping=True, future=True)
    return _engine


def dispose_engine() -> None:
    global _engine, _Session
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _Session = None


@contextmanager
def session_scope() -> Iterator[SASession]:
    """Transaksi ringkas: commit bila sukses, rollback bila gagal."""
    global _Session
    if _Session is None:
        _Session = sessionmaker(bind=engine(), expire_on_commit=False, future=True)
    s = _Session()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()