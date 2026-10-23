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
    # Memastikan rantai migrasi linear (satu head) dan setiap revisi bisa ditelusuri
    # dari head sampai base. Nama head TIDAK di-hardcode: dulu tes ini mengunci
    # "a7b8c9d0e1f2", sehingga setiap migrasi baru (mis. indeks events(id,type) dan
    # GIN fact_ids) memutus tes padahal migrasinya benar. Yang penting adalah
    # bentuk rantainya, bukan nomor revisinya.
    ini_path = Path(__file__).resolve().parents[1] / "alembic.ini"
    cfg = Config(str(ini_path))
    scripts = ScriptDirectory.from_config(cfg)

    heads = scripts.get_heads()
    assert len(heads) == 1, f"migrasi bercabang, ada {len(heads)} head: {heads}"

    # Telusuri head -> base. get_revision() melempar bila berkas revisi hilang,
    # jadi rantai yang bolong tetap gagal di sini.
    terlihat: list[str] = []
    revisi = scripts.get_revision(heads[0])
    while revisi is not None:
        terlihat.append(revisi.revision)
        turun = revisi.down_revision
        if isinstance(turun, tuple):
            assert len(turun) == 1, f"merge migration tidak diharapkan: {revisi.revision}"
            turun = turun[0]
        revisi = scripts.get_revision(turun) if turun else None

    assert terlihat, "rantai migrasi kosong"
    assert len(terlihat) == len(set(terlihat)), f"revisi berulang di rantai: {terlihat}"
