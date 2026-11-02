"""Enkripsi sandi MT5 vault (Fernet, kunci dari file/env).

Kunci dicari di: `WARROOM_MT5_VAULT_KEY` (env, base64 Fernet key) →
`/etc/warroom/mt5_vault.key` → `~/.warroom/mt5_vault.key`.

Jika kunci tidak tersedia: `key_available()` False, endpoint tulis vault
menolak. Kunci TIDAK PERNAH dikirim ke klien.
"""
from __future__ import annotations

import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

_KEY_PATHS = ("/etc/warroom/mt5_vault.key", str(Path.home() / ".warroom" / "mt5_vault.key"))

class VaultKeyError(RuntimeError):
    """Kunci vault tidak tersedia/tidak valid."""

def _load_fernet() -> Fernet | None:
    env = os.environ.get("WARROOM_MT5_VAULT_KEY", "").strip()
    if env:
        try:
            return Fernet(env.encode())
        except Exception as exc:  # pragma: no cover - konfigurasi salah
            raise VaultKeyError(f"WARROOM_MT5_VAULT_KEY tidak valid: {exc}") from exc
    for p in _KEY_PATHS:
        try:
            data = Path(p).read_bytes().strip()
            if data:
                return Fernet(data)
        except FileNotFoundError:
            continue
        except Exception as exc:  # pragma: no cover
            raise VaultKeyError(f"Kunci vault {p} tidak valid: {exc}") from exc
    return None

def key_available() -> bool:
    try:
        return _load_fernet() is not None
    except VaultKeyError:
        return False

def encrypt(plaintext: str) -> str:
    f = _load_fernet()
    if f is None:
        raise VaultKeyError("Kunci vault tidak tersedia")
    return f.encrypt(plaintext.encode()).decode()

def decrypt(token: str) -> str:
    f = _load_fernet()
    if f is None:
        raise VaultKeyError("Kunci vault tidak tersedia")
    try:
        return f.decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise VaultKeyError("Token tidak cocok dengan kunci vault") from exc
