"""jobs: bersihkan baris nama LAMA yang tertinggal (retensi/rekonsiliasi-crypto).

Revision ID: d4e6f8a0b2c3
Revises: c3d5e7f9a1b2

Konteks: migrasi c3d5e7f9a1b2 HANYA meng-UPDATE nama BILA nama baru belum ada
(guard NOT EXISTS, agar tak langgar UNIQUE jobs_name_key). Di produksi, worker
sempat restart dengan kode baru SEBELUM migrasi jalan -> ensure_jobs sudah
membuat baris nama BARU (enabled), sehingga UPDATE c3d5e7f9a1b2 DILEWATI dan
baris nama LAMA tetap ada & enabled => job dobel jalan.

Migrasi ini menghapus baris nama LAMA bila nama BARU sudah ada (kondisi aman);
bila nama baru belum ada, ia rename seperti biasa. Idempoten.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4e6f8a0b2c3"
down_revision: str | None = "c3d5e7f9a1b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_RENAMES = [
    ("retensi", "retention"),
    ("rekonsiliasi-crypto", "reconcile-crypto"),
]


def upgrade() -> None:
    conn = op.get_bind()
    for lama, baru in _RENAMES:
        baru_ada = conn.execute(
            sa.text("SELECT 1 FROM jobs WHERE name = :n"), {"n": baru}
        ).first()
        if baru_ada:
            # Nama baru sudah ada -> hapus baris lama (duplikat), jangan rename.
            conn.execute(sa.text("DELETE FROM jobs WHERE name = :n"), {"n": lama})
        else:
            # Nama baru belum ada -> rename biasa.
            conn.execute(
                sa.text("UPDATE jobs SET name = :baru WHERE name = :lama"),
                {"lama": lama, "baru": baru},
            )


def downgrade() -> None:
    # Tak bisa dipulihkan sempurna (baris lama mungkin sudah dihapus). Sengaja
    # tidak melakukan apa pun: downgrade nama job berisiko menimpa baris baru.
    pass
