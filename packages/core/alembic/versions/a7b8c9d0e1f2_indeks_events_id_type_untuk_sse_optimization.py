"""indeks_events_id_type_untuk_sse_optimization

Revision ID: a7b8c9d0e1f2
Revises: f10b7d251d17
Create Date: 2026-10-22 16:36:50.000000+00:00

Catatan: Mengoptimalkan pemindaian SSE event stream (Index Cond id + type)
sesuai temuan audit Hermes TINGGI-5.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = 'a7b8c9d0e1f2'
down_revision: str | None = 'f10b7d251d17'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index('ix_events_id_type', 'events', ['id', 'type'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_events_id_type', table_name='events')
