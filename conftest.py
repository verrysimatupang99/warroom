"""Fixture tes lintas-paket (root conftest).

Dipakai oleh `packages/*/tests` dan `services/*/tests`. Tes yang butuh DB **dilewati**
dengan alasan jelas bila kredensial tes tidak tersedia — tidak pernah diam-diam lulus.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

TEST_ENV = Path.home() / ".config" / "warroom" / "test-db.env"

# Kunci advisory Postgres untuk seluruh sesi tes ber-DB. Angka tetap (huruf "warroom"
# sebagai heksadesimal) — bukan rahasia, hanya harus sama di semua proses.
KUNCI_DB = 0x776172726F6F6D

# Status kunci per proses — lihat `_satu_sesi_di_db`.
_kunci_kedalaman = 0
_kunci_pegang: tuple[Any, Any] | None = None


def _test_url() -> str | None:
    url = os.environ.get("WARROOM_TEST_DB_URL")
    if url:
        return url
    if TEST_ENV.exists():
        for line in TEST_ENV.read_text(encoding="utf-8").splitlines():
            if line.startswith("WARROOM_TEST_DB_URL="):
                return line.split("=", 1)[1].strip()
    return None


@contextmanager
def _satu_sesi_di_db(url: str) -> Iterator[None]:
    """Satu sesi tes memakai skema `warroom_test` pada satu waktu.

    `drop_all`/`create_all` di awal sesi menghapus tabel yang sedang dipakai sesi lain:
    dua proses pytest (mis. beberapa worktree sektor berjalan bersamaan) saling
    menjatuhkan dengan `relation "..." does not exist` — gejalanya persis seperti tes
    flaky, padahal penyebabnya jadwal. Kunci Postgres dilepas otomatis saat koneksi
    putus, jadi sesi yang mati tidak memblokir sesi berikutnya.

    Kunci dihitung per PROSES, bukan per pemanggilan: satu proses bisa memuat fixture ini
    lebih dari sekali (mis. lewat conftest paket yang mengekspor ulang), dan kunci
    advisory Postgres tidak mengenal pemilik yang sama di koneksi berbeda — permintaan
    kedua akan menunggu dirinya sendiri sampai mati.
    """
    global _kunci_kedalaman
    if not url.startswith("postgresql"):
        yield
        return

    from sqlalchemy import create_engine, text
    from sqlalchemy.pool import NullPool

    global _kunci_pegang
    if _kunci_kedalaman == 0:
        # Koneksi terpisah (di luar pool bersama) supaya `dispose_engine()` tidak ikut
        # menutup koneksi pemegang kunci.
        kunci_engine = create_engine(url, poolclass=NullPool)
        koneksi = kunci_engine.connect()
        koneksi.execute(text("select pg_advisory_lock(:k)"), {"k": KUNCI_DB})
        _kunci_pegang = (koneksi, kunci_engine)
    _kunci_kedalaman += 1
    try:
        yield
    finally:
        _kunci_kedalaman -= 1
        if _kunci_kedalaman == 0 and _kunci_pegang is not None:
            koneksi, kunci_engine = _kunci_pegang
            _kunci_pegang = None
            koneksi.close()
            kunci_engine.dispose()


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
    with _satu_sesi_di_db(url):
        Base.metadata.drop_all(engine())
        Base.metadata.create_all(engine())
        try:
            yield url
        finally:
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
