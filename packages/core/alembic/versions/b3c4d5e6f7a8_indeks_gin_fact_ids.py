"""indeks GIN fact_ids untuk retensi

Revision ID: b3c4d5e6f7a8
Revises: a7b8c9d0e1f2

Masalah: retention.rencana() menjalankan NOT EXISTS korelatif pada
events.fact_ids (JSONB array) dan alerts.fact_ids TANPA indeks GIN.
Pada 23 Okt 2026 query itu menggantung 7m28s (dua query harus di-kill)
karena memindai 48 ribu events untuk setiap 66 ribu facts.

Indeks GIN membuat operator @> (containment) bisa memakai index scan,
sehingga penjaga "jangan hapus fakta yang masih dirujuk" tetap murah.

Catatan: di produksi indeks ini sudah dibuat CONCURRENTLY lebih dulu
(supaya tidak mengunci tabel); migrasi memakai IF NOT EXISTS agar aman
dijalankan ulang pada database yang sudah punya indeks.
"""
from __future__ import annotations

from alembic import op

revision = "b3c4d5e6f7a8"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_events_fact_ids_gin "
        "ON events USING gin (fact_ids)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_alerts_fact_ids_gin "
        "ON alerts USING gin (fact_ids)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_events_fact_ids_gin")
    op.execute("DROP INDEX IF EXISTS ix_alerts_fact_ids_gin")
