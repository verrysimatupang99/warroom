"""Tabel mt5_accounts (vault kredensial MT5 terenkripsi).

Revision ID: c5d6e7f8a9b0
Revises: b3c4d5e6f7a8
Create Date: 2026-11-02
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "c5d6e7f8a9b0"
down_revision: str | None = "b3c4d5e6f7a8"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "mt5_accounts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("login", sa.String(length=32), nullable=False),
        sa.Column("server", sa.String(length=160), nullable=False),
        sa.Column("password_enc", sa.Text(), nullable=False),
        sa.Column("password_kind", sa.String(length=16), nullable=False, server_default="investor"),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_mt5_accounts_login_server", "mt5_accounts", ["login", "server"], unique=True
    )

def downgrade() -> None:
    op.drop_index("uq_mt5_accounts_login_server", table_name="mt5_accounts")
    op.drop_table("mt5_accounts")
