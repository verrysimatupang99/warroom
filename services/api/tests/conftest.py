"""Fixture khusus API — sisanya ada di conftest root."""

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


@pytest.fixture(scope="session")
def db_url_tersedia() -> bool:
    """Penanda cepat: apakah tes DB bisa dijalankan."""
    return _test_url() is not None