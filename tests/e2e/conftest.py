"""
E2E Test Configuration and Fixtures for Dual Track E2E Test Suite.
Sprint 4 / US-18: Requirement-driven Opaque-Box E2E Testing.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Generator, Iterator
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

# Ensure all application modules are on sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SERVICES_API_SRC = PROJECT_ROOT / "services" / "api" / "src"
PACKAGES_CORE_SRC = PROJECT_ROOT / "packages" / "core" / "src"
SERVICES_TG_ENGINE = PROJECT_ROOT / "services" / "tg-engine"

for path in (SERVICES_API_SRC, PACKAGES_CORE_SRC, SERVICES_TG_ENGINE, PROJECT_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from warroom_api.app import app
from warroom_api import auth
from warroom_api.auth_ea import verify_mt5_or_admin
from warroom_core.db.models import User
import warroom_api.routers.tencent as tencent_module


@pytest.fixture(scope="session")
def project_root() -> Path:
    """Return root directory of the warroom project."""
    return PROJECT_ROOT


@pytest.fixture(scope="session")
def docs_dir(project_root: Path) -> Path:
    """Return documentation directory path."""
    return project_root / "docs"


@pytest.fixture(scope="session")
def apps_web_dir(project_root: Path) -> Path:
    """Return frontend application directory path."""
    return project_root / "apps" / "web"


@pytest.fixture
def mock_operator_user() -> User:
    """Return a mock operator user instance."""
    return User(id=101, username="e2e_operator", role="operator", active=True)


@pytest.fixture
def mock_viewer_user() -> User:
    """Return a mock viewer user instance."""
    return User(id=102, username="e2e_viewer", role="viewer", active=True)


@pytest.fixture
def test_client(mock_operator_user: User) -> Generator[TestClient, None, None]:
    """
    Authenticated TestClient fixture with default operator privileges.
    Cleans up dependency overrides after test.
    """
    app.dependency_overrides[auth.current_user] = lambda: mock_operator_user
    app.dependency_overrides[verify_mt5_or_admin] = lambda: None
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.pop(auth.current_user, None)
    app.dependency_overrides.pop(verify_mt5_or_admin, None)


@pytest.fixture
def viewer_client(mock_viewer_user: User) -> Generator[TestClient, None, None]:
    """TestClient fixture with viewer privileges."""
    app.dependency_overrides[auth.current_user] = lambda: mock_viewer_user
    app.dependency_overrides[verify_mt5_or_admin] = lambda: None
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.pop(auth.current_user, None)
    app.dependency_overrides.pop(verify_mt5_or_admin, None)


@pytest.fixture
def unauthenticated_client() -> Generator[TestClient, None, None]:
    """TestClient fixture with no authenticated session or override."""
    app.dependency_overrides.pop(auth.current_user, None)
    app.dependency_overrides.pop(verify_mt5_or_admin, None)
    with TestClient(app) as client:
        yield client


@pytest.fixture
def tmp_deal_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Fixture to safely isolate deal CSV logging to a temporary directory."""
    temp_csv = tmp_path / "deals_e2e.csv"
    monkeypatch.setattr(tencent_module, "DEAL_LOG", temp_csv)
    return temp_csv


@pytest.fixture
def reset_telemetry_state() -> Generator[None, None, None]:
    """Ensure in-memory telemetry state and subscribers are cleanly reset."""
    original_accounts = dict(tencent_module.latest_mt5_by_account)
    original_subscribers = list(tencent_module._telemetry_subscribers)
    yield
    tencent_module.latest_mt5_by_account.clear()
    tencent_module.latest_mt5_by_account.update(original_accounts)
    tencent_module._telemetry_subscribers.clear()
    tencent_module._telemetry_subscribers.extend(original_subscribers)


@pytest.fixture
def env_pure_technical(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force pure technical mode environment configuration."""
    monkeypatch.setenv("WARROOM_LAYA_INFERENSI", "0")
    monkeypatch.delenv("WARROOM_LAYA_ENABLE", raising=False)


@pytest.fixture
def env_laya_ai(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force Laya AI mode environment configuration."""
    monkeypatch.setenv("WARROOM_LAYA_INFERENSI", "1")
    monkeypatch.setenv("WARROOM_LAYA_ENABLE", "1")
