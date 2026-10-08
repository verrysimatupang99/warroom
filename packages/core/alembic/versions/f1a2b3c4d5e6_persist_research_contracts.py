"""Persist versioned research contracts and artifact provenance.

Revision ID: f1a2b3c4d5e6
Revises: edc4c7a26d32
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f1a2b3c4d5e6"
down_revision: tuple[str, str] = ("a1f2c3d4e5b6", "edc4c7a26d32")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "research_runs",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("research_key", sa.String(length=120), nullable=False),
        sa.Column("hypothesis_id", sa.String(length=120), nullable=False),
        sa.Column("hypothesis_version", sa.String(length=80), nullable=False),
        sa.Column("hypothesis_json", postgresql.JSONB(), nullable=False),
        sa.Column("hypothesis_hash", sa.String(length=64), nullable=False),
        sa.Column("execution_json", postgresql.JSONB(), nullable=False),
        sa.Column("execution_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="draft"),
        sa.Column("provenance_json", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("research_key", "hypothesis_hash", "execution_hash", name="uq_research_runs_version"),
        sa.CheckConstraint("status IN ('draft', 'running', 'completed', 'failed', 'invalid')", name="ck_research_runs_status"),
        sa.CheckConstraint("execution_json ->> 'mode' IN ('paper', 'shadow')", name="ck_research_runs_research_only"),
    )
    op.create_index("ix_research_runs_key_created", "research_runs", ["research_key", "created_at"])
    op.create_table(
        "research_records",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("research_run_id", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("uri", sa.String(length=400), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="observed"),
        sa.Column("provenance_json", postgresql.JSONB(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["research_run_id"], ["research_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("research_run_id", "uri", "sha256", name="uq_research_records_artifact"),
        sa.CheckConstraint("status IN ('observed', 'validated', 'rejected')", name="ck_research_records_status"),
    )
    op.create_index("ix_research_records_run_created", "research_records", ["research_run_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_research_records_run_created", table_name="research_records")
    op.drop_table("research_records")
    op.drop_index("ix_research_runs_key_created", table_name="research_runs")
    op.drop_table("research_runs")
