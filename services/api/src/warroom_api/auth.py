"""Auth + RBAC (P1-T3).

Peran: ``viewer`` < ``operator`` < ``owner`` (03-backend.md §7).

- Sesi: cookie ``wr_session`` (HttpOnly) → baris di tabel ``sessions``, dengan masa berlaku.
- Sandi: scrypt (stdlib) — tidak ada ketergantungan luar, format ``scrypt$n$r$p$salt$hash``.
- TOTP: opsional per pengguna. Bila pengguna punya ``totp_secret_enc``, kode wajib benar.
- Aksi live: **tidak** diimplementasikan di P1; P6 menambahkan grant
  (``grantedBy``/``messageId``/``scope``/``at``) dan mengembalikan 409 bila kurang.

Catatan kejujuran: TOTP secret disimpan apa adanya di kolom ``totp_secret_enc`` untuk P1
(DB tidak masuk repo/log). Enkripsi-at-rest dengan kunci `/etc/warroom/` adalah pekerjaan P6.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from fastapi import Cookie, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session as SASession
from warroom_core.db import Session as SessionRow
from warroom_core.db import User, session_scope

__all__ = [
    "COOKIE_NAME",
    "Role",
    "current_user",
    "has_role",
    "hash_password",
    "issue_session",
    "optional_user",
    "require_role",
    "revoke_session",
    "verify_password",
]

COOKIE_NAME = "wr_session"
SESSION_TTL = timedelta(hours=12)
Role = Literal["viewer", "operator", "owner"]


def cookie_secure() -> bool:
    """Cookie hanya lewat HTTPS. Di produksi (Caddy TLS) selalu aktif.

    Dimatikan **hanya** untuk pengujian lokal lewat `WARROOM_COOKIE_SECURE=0` — kalau tidak,
    TestClient (http) tidak akan menyimpan cookie dan uji login tidak bermakna.
    """
    return os.environ.get("WARROOM_COOKIE_SECURE", "1").strip().lower() not in {"0", "false", "no", "off"}


_ROLE_RANK: dict[str, int] = {"viewer": 1, "operator": 2, "owner": 3}

# Parameter scrypt. n=2**14 ≈ 16 MB per hash — cukup untuk satu layar operasi internal.
_SCRYPT_N, _SCRYPT_R, _SCRYPT_P = 2**14, 8, 1


def hash_password(password: str, *, salt: bytes | None = None) -> str:
    """Hash scrypt; hasilnya menyimpan parameter supaya bisa diverifikasi di masa depan."""
    if not password:
        raise ValueError("sandi kosong ditolak")
    s = salt or os.urandom(16)
    dk = hashlib.scrypt(password.encode("utf-8"), salt=s, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=32)
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${s.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Verifikasi konstan-waktu. Format tidak dikenal = False (bukan exception yang bocor)."""
    if not stored or not password:
        return False
    try:
        algo, n, r, p, salt_hex, hash_hex = stored.split("$")
        if algo != "scrypt":
            return False
        dk = hashlib.scrypt(
            password.encode("utf-8"),
            salt=bytes.fromhex(salt_hex),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(hash_hex) // 2,
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(dk.hex(), hash_hex)


def verify_totp(secret: str | None, code: str | None) -> bool:
    """TOTP opsional: bila pengguna belum punya secret, tidak ada kode yang diminta."""
    if not secret:
        return True
    if not code:
        return False
    import pyotp

    return bool(pyotp.TOTP(secret).verify(code, valid_window=1))


def issue_session(s: SASession, user: User, *, now: datetime | None = None) -> SessionRow:
    """Buat sesi baru; id acak 256-bit."""
    t0 = now or datetime.now(UTC)
    row = SessionRow(
        id=secrets.token_urlsafe(32),
        user_id=user.id,
        created_at=t0,
        expires_at=t0 + SESSION_TTL,
    )
    s.add(row)
    s.flush()
    return row


def revoke_session(s: SASession, sid: str, *, now: datetime | None = None) -> bool:
    row = s.get(SessionRow, sid)
    if row is None or row.revoked_at is not None:
        return False
    row.revoked_at = now or datetime.now(UTC)
    return True


def _lookup(sid: str) -> tuple[SessionRow, User] | None:
    with session_scope() as s:
        row = s.get(SessionRow, sid)
        if row is None or row.revoked_at is not None:
            return None
        if row.expires_at <= datetime.now(UTC):
            return None
        user = s.get(User, row.user_id)
        if user is None or not user.active:
            return None
        return row, user


def current_user(
    wr_session: Annotated[str | None, Cookie(alias=COOKIE_NAME)] = None,
) -> User:
    """Dependensi: pengguna dari cookie sesi. Tanpa cookie/kedaluwarsa → 401."""
    if not wr_session:
        raise HTTPException(status_code=401, detail="belum login")
    found = _lookup(wr_session)
    if found is None:
        raise HTTPException(status_code=401, detail="sesi tidak sah atau kedaluwarsa")
    return found[1]


def optional_user(
    wr_session: Annotated[str | None, Cookie(alias=COOKIE_NAME)] = None,
) -> User | None:
    """Seperti `current_user`, tetapi mengembalikan None (bukan 401) — untuk /metrics publik."""
    if not wr_session:
        return None
    found = _lookup(wr_session)
    return found[1] if found else None


def require_role(minimum: Role):
    """Dependensi pabrik: menolak 403 bila peran pengguna di bawah ``minimum``."""

    def _dep(user: Annotated[User, Depends(current_user)]) -> User:
        if not has_role(user, minimum):
            raise HTTPException(
                status_code=403,
                detail=f"butuh peran {minimum}; peran Anda {user.role}",
            )
        return user

    return _dep


def has_role(user: User, minimum: Role) -> bool:
    """True bila peran pengguna >= ``minimum`` (dipakai di jalur auth campuran).

    Dipisah dari `require_role` supaya endpoint yang menerima **dua** jenis
    pemanggil (sesi pengguna ATAU token layanan) tetap bisa menegakkan peran
    minimum pada jalur sesi tanpa memaksa token layanan punya peran.
    """
    return _ROLE_RANK.get(user.role, 0) >= _ROLE_RANK[minimum]


# Hash dummy konstan untuk mitigasi kebocoran waktu enumerasi username.
_DUMMY_HASH = hash_password("dummy-password-for-timing-mitigation")


def login(username: str, password: str, totp_code: str | None = None) -> str | None:
    """Verifikasi sandi (+TOTP bila terdaftar) dan kembalikan id sesi, atau None.

    Pesan gagal **tidak** membedakan "pengguna tidak ada" dan "sandi salah".
    Mitigasi enumerasi waktu: selalu jalankan verifikasi scrypt meskipun pengguna tidak ada.
    """
    with session_scope() as s:
        user = s.scalar(select(User).where(User.username == username))
        if user is None or not user.active:
            verify_password(password, _DUMMY_HASH)
            return None
        if not verify_password(password, user.pass_hash):
            return None
        if not verify_totp(user.totp_secret_enc, totp_code):
            return None
        return issue_session(s, user).id


def purge_expired(*, now: datetime | None = None) -> int:
    """Tandai sesi kedaluwarsa sebagai dicabut (dipanggil worker nanti)."""
    t = now or datetime.now(UTC)
    with session_scope() as s:
        rows = s.scalars(select(SessionRow).where(SessionRow.expires_at <= t,
                                                 SessionRow.revoked_at.is_(None))).all()
        for r in rows:
            r.revoked_at = t
        return len(rows)