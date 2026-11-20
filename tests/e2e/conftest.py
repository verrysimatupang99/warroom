"""Global E2E test fixtures, HTTP clients, and environment configuration."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

# Ensure primary account is 452009427 before warroom modules are loaded
os.environ.setdefault("WARROOM_MT5_PRIMARY_ACCOUNT", "452009427")
os.environ.setdefault("WARROOM_COOKIE_SECURE", "0")

import httpx
import pytest
from fastapi.testclient import TestClient
from warroom_api import auth
from warroom_api.app import app
from warroom_api.auth_ea import get_expected_service_token

# Token sintetis untuk CI / mesin tanpa /etc/warroom. Bukan kredensial nyata:
# hanya dipakai tes TestClient in-process, tidak pernah keluar jaringan.
CI_FALLBACK_TOKEN = "ci-test-token-not-a-secret"


def _load_service_token() -> str:
    """Dynamically resolve the production service token without hardcoding secrets."""
    token = get_expected_service_token()
    if token:
        return token
    # Secondary fallback to systemd service env file
    env_file = Path("/etc/warroom/service_token.env")
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("WARROOM_SERVICE_TOKEN="):
                val = line.split("=", 1)[1].strip()
                return val.strip(chr(39)).strip(chr(34))
    # CI / developer tanpa file env: pakai token sintetis agar tes TestClient
    # (in-process, tanpa jaringan) tidak menggantung pada rahasia produksi.
    return CI_FALLBACK_TOKEN


def _ensure_test_db() -> None:
    """Ensure test DB URL is loaded for isolated TestClient sessions."""
    if not os.environ.get("WARROOM_DB_URL"):
        test_env = Path.home() / ".config" / "warroom" / "test-db.env"
        if test_env.exists():
            for line in test_env.read_text(encoding="utf-8").splitlines():
                if line.startswith("WARROOM_TEST_DB_URL="):
                    os.environ["WARROOM_DB_URL"] = line.split("=", 1)[1].strip()
    os.environ.setdefault("WARROOM_COOKIE_SECURE", "0")


@pytest.fixture(scope="session")
def service_token() -> str:
    """Retrieve the dynamically loaded War Room service token."""
    token = _load_service_token()
    if not token:
        pytest.fail("WARROOM_SERVICE_TOKEN is not available in environment or /etc/warroom/service_token.env")
    return token


@pytest.fixture(scope="session")
def auth_headers(service_token: str) -> dict[str, str]:
    """Default X-Warroom-Token headers for authenticated MT5 endpoints."""
    return {"X-Warroom-Token": service_token}


@pytest.fixture(scope="session")
def api_base_url() -> str:
    """Base URL for live local warroom-api service."""
    return os.environ.get("WARROOM_API_BASE_URL", "http://127.0.0.1:8800")


@pytest.fixture(scope="session")
def web_base_url() -> str:
    """Base URL for live local warroom-web UI service."""
    return os.environ.get("WARROOM_WEB_BASE_URL", "http://127.0.0.1:3100")


@pytest.fixture(scope="session")
def cloud_base_url() -> str:
    """Public reverse proxy domain for War Room cockpit."""
    return "https://polywarroom.vps.webdock.cloud"


@pytest.fixture
def live_client(api_base_url: str) -> Iterator[httpx.Client]:
    """Synchronous HTTP client configured for live warroom-api endpoints."""
    with httpx.Client(base_url=api_base_url, timeout=10.0) as client:
        yield client


@pytest.fixture
async def live_async_client(api_base_url: str) -> AsyncIterator[httpx.AsyncClient]:
    """Asynchronous HTTP client configured for live warroom-api endpoints."""
    async with httpx.AsyncClient(base_url=api_base_url, timeout=10.0) as client:
        yield client


@pytest.fixture
def live_web_client(web_base_url: str) -> Iterator[httpx.Client]:
    """Synchronous HTTP client configured for live warroom-web endpoints."""
    with httpx.Client(base_url=web_base_url, timeout=10.0) as client:
        yield client


@pytest.fixture
def admin_cookie_header() -> dict[str, str]:
    """Create or retrieve an admin user session cookie for protected admin endpoints."""
    _ensure_test_db()
    from warroom_core.db import User, session_scope

    with session_scope() as s:
        user = s.query(User).filter(User.username == "e2e-admin").first()
        if not user:
            user = User(
                username="e2e-admin",
                role="owner",
                pass_hash=auth.hash_password("admin-e2e-password"),
            )
            s.add(user)
            s.flush()
        sid = auth.issue_session(s, user).id
    return {"Cookie": f"{auth.COOKIE_NAME}={sid}"}


@pytest.fixture
def test_client() -> Iterator[TestClient]:
    """Isolated TestClient fixture backed by test DB schema."""
    _ensure_test_db()
    with TestClient(app) as client:
        yield client
