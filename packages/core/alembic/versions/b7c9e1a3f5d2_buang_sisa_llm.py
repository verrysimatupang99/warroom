"""buang sisa LLM: tabel llm_calls dan prompts

Revision ID: b7c9e1a3f5d2
Revises: d6e8f0a2b4c6
Create Date: 2026-11-04

Keputusan owner: worker LLM dibuang (3 Nov 2026) dan sinyal kini murni rumus +
data, jadi tidak ada lagi yang menulis ke `llm_calls` maupun `prompts`.
Panggilan LLM terakhir 2026-11-03 16:18, seluruhnya gagal (`ok=false`).

Yang TIDAK disentuh: `proposals` dan parameter `ai.kill_switch`. Keduanya bagian
dari bounded-autonomy (usulan perubahan parameter + gate verdict), bukan LLM, dan
masih dibaca `formula.py`/`strategi.py` sebagai pengaman.

`downgrade()` membuat ulang struktur kosong — data historis tidak dikembalikan.
Itu disengaja: tabelnya sudah mati, dan memulihkan 2.172 baris audit tanpa
konsumen hanya menambah utang.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "b7c9e1a3f5d2"
down_revision: str | None = "d6e8f0a2b4c6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Index ikut terhapus bersama tabelnya di Postgres — jangan drop terpisah,
    # itu gagal dengan UndefinedObject. Urutan dibalik juga: `prompts` tidak punya
    # foreign key ke `llm_calls`, jadi aman.
    op.drop_table("llm_calls")
    op.drop_table("prompts")


def downgrade() -> None:
    op.create_table(
        "prompts",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("role", sa.String(40), nullable=False),
        sa.Column("version", sa.String(40), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("schema_json", JSONB, nullable=False, server_default=sa.text("'{}'")),
        sa.Column("contoh_json", JSONB, nullable=False, server_default=sa.text("'[]'")),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("role", "version", name="uq_prompts_role_version"),
    )
    op.create_table(
        "llm_calls",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("role", sa.String(40), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("model", sa.String(80), nullable=False, server_default=""),
        sa.Column("prompt_version", sa.String(40), nullable=False, server_default=""),
        sa.Column("tokens_in", sa.Integer()),
        sa.Column("tokens_out", sa.Integer()),
        sa.Column("cost_usd", sa.Numeric(12, 6)),
        sa.Column("latency_ms", sa.Integer()),
        sa.Column("ok", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("fallback_from", sa.String(40)),
        sa.Column("error_code", sa.String(60)),
        sa.Column("result_hash", sa.String(64)),
        sa.Column("fact_ids", JSONB, nullable=False, server_default=sa.text("'[]'")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_llm_calls_role_created", "llm_calls", ["role", "created_at"]
    )
