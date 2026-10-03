"""Fixture tes lintas-paket (root conftest).

Dipakai oleh `packages/*/tests` dan `services/*/tests`. Tes yang butuh DB **dilewati**
dengan alasan jelas bila kredensial tes tidak tersedia — tidak pernah diam-diam lulus.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

TEST_ENV = Path.home() / ".config" / "warroom" / "test-db.env"


def _test_url() -> str | None:
    url = os.environ.get("WARROOM_TEST_DB_URL")
    if url:
        return url
    if TEST_ENV.exists():
        for line in TEST_ENV.read_text(encoding="utf-8").splitlines():
            if line.startswith("WARROOM_TEST_DB_URL="):
                return line.split("=", 1)[1].strip()
    return None


@pytest.fixture(scope="session", autouse=True)
def _no_secure_cookie() -> None:
    """TestClient memakai http://testserver — cookie `secure` tidak akan tersimpan.

    Produksi tetap `secure=True` (Caddy TLS); ini hanya untuk pengujian lokal.
    """
    os.environ.setdefault("WARROOM_COOKIE_SECURE", "0")


@pytest.fixture(scope="session")
def db() -> str:
    """Basis data tes terpisah (`warroom_test`); tes tidak pernah menyentuh DB produksi."""
    url = _test_url()
    if not url:
        pytest.skip("WARROOM_TEST_DB_URL tidak tersedia — tes DB dilewati (bukan lulus)")
    os.environ["WARROOM_DB_URL"] = url

    from warroom_core.db import Base, dispose_engine, engine

    dispose_engine()
    Base.metadata.drop_all(engine())
    Base.metadata.create_all(engine())
    yield url
    dispose_engine()


@pytest.fixture
def bersihkan_db(db):
    """Isolasi tes lintas berkas: kosongkan tabel yang dipakai bersama."""
    from warroom_core.db import Alert, Event, Fact, Job, LLMCall, Strategy, session_scope

    with session_scope() as s:
        s.query(Fact).delete()
        s.query(Event).delete()
        s.query(Alert).delete()
        s.query(Strategy).delete()
        s.query(Job).delete()
        s.query(LLMCall).delete()
    yield


@pytest.fixture
def client(db: str):
    from fastapi.testclient import TestClient
    from warroom_api.app import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def make_user(db: str):
    """Buat pengguna + sesi; kembalikan (username, cookie_value)."""

    def _make(username: str, role: str = "viewer", password: str = "rahasia-uji-123") -> tuple[str, str]:
        from warroom_api import auth
        from warroom_core.db import User, session_scope

        with session_scope() as s:
            user = User(username=username, role=role, pass_hash=auth.hash_password(password))
            s.add(user)
            s.flush()
            sid = auth.issue_session(s, user).id
        return username, sid

    return _make