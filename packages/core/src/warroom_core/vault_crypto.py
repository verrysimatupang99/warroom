"""Enkripsi at-rest untuk gudang kredensial generik (reuse Fernet MT5 vault)."""
from __future__ import annotations

import json

from cryptography.fernet import InvalidToken

from warroom_core.mt5_crypto import VaultKeyError, decrypt, encrypt

__all__ = ["VaultKeyError", "extra_decode", "extra_encode", "vault_decrypt", "vault_encrypt"]


def vault_encrypt(plain: str) -> str:
    return encrypt(plain)


def vault_decrypt(token: str) -> str:
    try:
        return decrypt(token)
    except InvalidToken as exc:  # pragma: no cover - kunci dirotasi
        raise VaultKeyError("token kredensial tidak valid") from exc


def extra_encode(d: dict[str, str]) -> str:
    """Enkripsi dict ekstra (mis. passphrase) jadi satu blob."""
    return vault_encrypt(json.dumps(d))


def extra_decode(blob: str) -> dict[str, str]:
    return json.loads(vault_decrypt(blob))
