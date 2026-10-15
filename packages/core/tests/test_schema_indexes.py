"""Pengujian integritas indeks skema basis data dan rantai migrasi Alembic."""

from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from warroom_core.db.models import Base


def test_indeks_leaderboard_dan_splits_terdaftar_di_metadata() -> None:
    # Verifikasi keberadaan indeks penunjang query leaderboard dan split beku.
    strategies_indexes = {idx.name for idx in Base.metadata.tables["strategies"].indexes}
    assert "ix_strategies_area_status" in strategies_indexes

    trades_indexes = {idx.name for idx in Base.metadata.tables["trades"].indexes}
    assert "ix_trades_strategy_id" in trades_indexes
    assert "ix_trades_mode_strategy_closed" in trades_indexes
    assert "ix_trades_closed_at" in trades_indexes

    splits_indexes = {idx.name for idx in Base.metadata.tables["frozen_splits"].indexes}
    assert "ix_frozen_splits_dataset" in splits_indexes


def test_rantai_migrasi_alembic_tunggal_dan_valid() -> None:
    # Memastikan tidak ada percabangan migrasi (branch heads) yang tidak terintegrasi.
    ini_path = Path(__file__).resolve().parents[1] / "alembic.ini"
    cfg = Config(str(ini_path))
    scripts = ScriptDirectory.from_config(cfg)

    heads = scripts.get_heads()
    assert len(heads) == 1
    assert heads[0] == "f10b7d251d17"
