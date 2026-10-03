"""alerts: kolom attempts & last_error untuk notifier (W5 lanjutan)

Revision ID: 8b7c1d2e4f60
Revises: edc4c7a26d32
Create Date: 2026-10-03 08:55:00+00:00

Latar: percobaan kirim alert dulu dihitung dari event `alert.sent` (satu query per alert,
dan alert yang macet tetap menghabiskan jatah `limit`). Kolom eksplisit di tabel `alerts`
membuat batas percobaan terlihat langsung di UI dan murah dibaca.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "8b7c1d2e4f60"
down_revision: str | None = "edc4c7a26d32"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "alerts",
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("alerts", sa.Column("last_error", sa.String(length=200), nullable=True))
    # Isi dari riwayat event yang sudah ada supaya angka di UI tidak mundur ke nol.
    op.execute(
        """
        UPDATE alerts a SET attempts = sub.n
        FROM (
            SELECT (payload_json->>'alert_id')::bigint AS aid, count(*) AS n
            FROM events
            WHERE type = 'alert.sent' AND payload_json ? 'alert_id'
            GROUP BY 1
        ) sub
        WHERE a.id = sub.aid
        """
    )
    op.execute(
        """
        UPDATE alerts a SET last_error = sub.detail
        FROM (
            SELECT DISTINCT ON ((payload_json->>'alert_id')::bigint)
                   (payload_json->>'alert_id')::bigint AS aid,
                   payload_json->>'detail' AS detail
            FROM events
            WHERE type = 'alert.sent' AND payload_json ? 'alert_id'
              AND payload_json->>'ok' = 'false'
            ORDER BY (payload_json->>'alert_id')::bigint, id DESC
        ) sub
        WHERE a.id = sub.aid
        """
    )


def downgrade() -> None:
    op.drop_column("alerts", "last_error")
    op.drop_column("alerts", "attempts")
