"""Tabel frozen_splits: catatan split data yang dibekukan (ADR-003, P1 5 Okt 2026)

Latar: gate sudah mewajibkan ``split="frozen:<id>"``, tetapi tidak ada apa pun yang
membuat id itu *benar-benar* beku — "frozen:" hanyalah string yang bisa ditulis siapa
saja, kapan saja, termasuk setelah hasilnya dilihat. Tabel ini mengikat id ke daftar
berkas + sha256 yang dibaca, supaya bisa diverifikasi ulang.

Append-only: tidak ada alur yang boleh mengubah baris setelah ditulis.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "a1f2c3d4e5b6"
down_revision: str | None = "8b7c1d2e4f60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "frozen_splits",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("dataset", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("source", sa.String(length=400), nullable=False, server_default=""),
        sa.Column("files_json", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("manifest_hash", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("partitions_json", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("window_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("window_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rows", sa.BigInteger(), nullable=True),
        sa.Column("created_by", sa.String(length=80), nullable=False, server_default="system"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_frozen_splits_dataset", "frozen_splits", ["dataset"])


def downgrade() -> None:
    op.drop_index("ix_frozen_splits_dataset", table_name="frozen_splits")
    op.drop_table("frozen_splits")
