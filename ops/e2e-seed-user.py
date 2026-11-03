#!/usr/bin/env python3
"""Seed satu user e2e di DB — hanya untuk CI / DB tes, bukan produksi.

Kenapa ada: suite Playwright butuh sesi login. Di CI tidak ada user, dan
membuat user secara manual tidak mungkin. Skrip ini membuat (atau memperbarui)
satu user dengan peran ``owner`` dan **tanpa TOTP**, khusus DB sementara.

Pengaman:
- menolak jalan bila ``WARROOM_DB_URL`` menunjuk host yang bukan loopback,
  supaya tidak sengaja menyemai user ke DB produksi;
- sandi wajib diberikan lewat env, tidak pernah ditulis ke log;
- idempoten: user yang sama diperbarui, bukan diduplikasi.
"""

from __future__ import annotations

import argparse
import os
import sys
from urllib.parse import urlparse

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from warroom_api.auth import hash_password
from warroom_core.db.models import User

LOOPBACK = {"127.0.0.1", "localhost", "::1"}


def _pastikan_lokal(db_url: str) -> None:
    host = urlparse(db_url).hostname or ""
    if host not in LOOPBACK:
        raise SystemExit(
            f"DITOLAK: WARROOM_DB_URL menunjuk host non-loopback ({host!r}). "
            "Skrip ini hanya untuk DB tes lokal/CI."
        )


def main() -> int:
    p = argparse.ArgumentParser(description="Seed user e2e (CI/DB tes saja).")
    p.add_argument("--username", required=True)
    p.add_argument("--password-env", default="WARROOM_E2E_PASS",
                   help="nama env var berisi sandi (default: WARROOM_E2E_PASS)")
    p.add_argument("--role", default="owner", choices=["viewer", "operator", "owner"])
    a = p.parse_args()

    db_url = os.environ.get("WARROOM_DB_URL", "")
    if not db_url:
        raise SystemExit("DITOLAK: WARROOM_DB_URL tidak diset.")
    _pastikan_lokal(db_url)

    sandi = os.environ.get(a.password_env, "")
    if not sandi:
        raise SystemExit(f"DITOLAK: env {a.password_env} kosong.")

    mesin = create_engine(db_url)
    with Session(mesin) as s:
        user = s.scalar(select(User).where(User.username == a.username))
        if user is None:
            user = User(username=a.username, role=a.role, active=True)
            s.add(user)
            aksi = "dibuat"
        else:
            user.role = a.role
            user.active = True
            aksi = "diperbarui"
        user.pass_hash = hash_password(sandi)
        # TOTP dimatikan: suite e2e tidak bisa menebak kode TOTP.
        user.totp_secret_enc = None
        user.totp_last_counter = None
        s.commit()

    # Tidak pernah mencetak sandi.
    print(f"user e2e {aksi}: {a.username!r} peran={a.role} totp=nonaktif")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
