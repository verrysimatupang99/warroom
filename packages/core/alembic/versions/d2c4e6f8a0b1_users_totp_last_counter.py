"""users: kolom totp_last_counter untuk anti-replay TOTP.

Revision ID: d2c4e6f8a0b1
Revises: f1a2b3c4d5e6

Latar: kode TOTP dalam jendela valid_window=1 bisa dipakai ulang selama
counter-nya masih cocok. `login()` kini menyimpan counter kode yang cocok
dan menolak kode dengan counter <= tersimpan, sehingga satu kode hanya
berlaku untuk satu sesi.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d2c4e6f8a0b1"
down_revision: str | None = "f1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("totp_last_counter", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "totp_last_counter")
