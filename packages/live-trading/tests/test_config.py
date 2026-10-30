"""Kontrak konfigurasi: path turunan konsisten dan bisa di-override via env."""

from __future__ import annotations

from pathlib import Path

from live_trading.config import Settings, get_settings


def test_paths_are_derived_from_home(tmp_path: Path) -> None:
    """Semua path harus turunan dari ``home`` — bukan dari cwd atau hardcode."""
    s = get_settings(home=tmp_path)

    assert s.state_dir == tmp_path / "state"
    assert s.secrets_dir == tmp_path / "secrets"
    assert s.journal_dir == tmp_path / "journal"
    assert s.ledger_path == tmp_path / "state" / "crypto_equity.jsonl"
    assert s.arjum_key_path == tmp_path / "secrets" / "arjum_api_key"


def test_env_override_wins(monkeypatch, tmp_path: Path) -> None:
    """Env ``LT_*`` menimpa default — ini yang menggantikan hardcode ~/.hermes."""
    monkeypatch.setenv("LT_HOME", str(tmp_path / "lain"))

    s = Settings()

    assert s.home == tmp_path / "lain"
    assert s.ledger_path == tmp_path / "lain" / "state" / "crypto_equity.jsonl"


def test_defaults_are_paper_and_bounded(tmp_path: Path) -> None:
    """Default harus aman: paper mode, ada batas rugi, ada batas posisi."""
    s = get_settings(home=tmp_path)

    assert s.paper is True
    assert s.daily_loss_limit_r > 0
    assert s.max_concurrent_positions >= 1


def test_ensure_dirs_creates_everything(tmp_path: Path) -> None:
    s = get_settings(home=tmp_path)

    s.ensure_dirs()

    for d in (s.state_dir, s.secrets_dir, s.journal_dir, s.logs_dir):
        assert d.is_dir()


def test_executor_lock_path_is_stable(tmp_path: Path) -> None:
    """Kunci satu-executor harus satu lokasi tetap, bukan path acak."""
    a = get_settings(home=tmp_path).executor_lock_path
    b = get_settings(home=tmp_path).executor_lock_path

    assert a == b
    assert a.name == "executor.lock"

def test_config_fingerprint_stabil_dan_berubah_dengan_parameter(tmp_path: Path):
    a = Settings(home=tmp_path)
    b = Settings(home=tmp_path)
    assert a.config_fingerprint() == b.config_fingerprint()
    c = Settings(home=tmp_path, risk_per_trade_pct=2.0)
    assert c.config_fingerprint() != a.config_fingerprint()
    d = Settings(home=tmp_path, daily_loss_limit_r=1.5)
    assert d.config_fingerprint() != a.config_fingerprint()
