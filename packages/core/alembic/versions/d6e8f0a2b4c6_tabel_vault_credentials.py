"""tabel vault_credentials untuk gudang kredensial generik

Revision ID: d6e8f0a2b4c6
Revises: c5d6e7f8a9b0
Create Date: 2026-11-02

Gudang kredensial generik: simpan endpoint + API key/secret platform manapun
(salin-tempel manual, BUKAN auto-login). Polymarket sengaja tidak didukung.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d6e8f0a2b4c6"
down_revision: str | None = "c5d6e7f8a9b0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "vault_credentials",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("platform", sa.String(64), nullable=False),
        sa.Column("label", sa.String(128), nullable=False),
        sa.Column("endpoint", sa.Text(), nullable=True),
        sa.Column("api_key_enc", sa.Text(), nullable=True),
        sa.Column("api_secret_enc", sa.Text(), nullable=True),
        sa.Column("extra_enc", sa.Text(), nullable=True),
        sa.Column("aktif", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "dibuat",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("diubah", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("platform", "label", name="uq_vault_platform_label"),
    )
    op.create_index(
        "ix_vault_credentials_platform", "vault_credentials", ["platform"]
    )


def downgrade() -> None:
    op.drop_index("ix_vault_credentials_platform", table_name="vault_credentials")
    op.drop_table("vault_credentials")
