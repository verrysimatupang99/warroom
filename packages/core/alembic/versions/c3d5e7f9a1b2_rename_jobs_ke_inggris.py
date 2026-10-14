"""jobs: rename dua job ke Bahasa Inggris (retensi->retention, rekonsiliasi-crypto->reconcile-crypto).

Revision ID: c3d5e7f9a1b2
Revises: d2c4e6f8a0b1

Latar: penamaan kode dinormalisasi ke Bahasa Inggris (ADR penamaan). Nama job
adalah identifier DATA di tabel `jobs`, jadi rename butuh migrasi agar job lama
tidak jadi yatim (ensure_jobs hanya menambah bila nama baru tak ada).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3d5e7f9a1b2"
down_revision: str | None = "d2c4e6f8a0b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_RENAMES = [
    ("retensi", "retention"),
    ("rekonsiliasi-crypto", "reconcile-crypto"),
]


def upgrade() -> None:
    for lama, baru in _RENAMES:
        # Hanya ganti bila nama lama ada dan nama baru belum dipakai (idempoten).
        op.execute(
            sa.text(
                "UPDATE jobs SET name = :baru "
                "WHERE name = :lama AND NOT EXISTS "
                "(SELECT 1 FROM jobs WHERE name = :baru)"
            ).bindparams(lama=lama, baru=baru)
        )


def downgrade() -> None:
    for lama, baru in _RENAMES:
        op.execute(
            sa.text(
                "UPDATE jobs SET name = :lama "
                "WHERE name = :baru AND NOT EXISTS "
                "(SELECT 1 FROM jobs WHERE name = :lama)"
            ).bindparams(lama=lama, baru=baru)
        )
