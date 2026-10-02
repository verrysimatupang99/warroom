"""Scrub kredensial (pola `scrub()` Polymarket) dari prompt, jawaban, dan log.

Kenapa dua lapis: pola menangkap kunci yang ditulis dalam format khas (`sk-...`,
`Bearer ...`, `api_key=...`), sedangkan pencocokan *nilai env* menangkap kunci asli
yang tersalin apa adanya tanpa format khas. Tanpa lapis kedua, kunci acak panjang
bisa lolos. Nilai kunci tidak pernah dicetak — hanya diganti penanda.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterable

__all__ = ["DEFAULT_KEY_ENVS", "REDACTED", "SECRET_PATTERNS", "scrub", "scrub_all", "scrub_env"]

REDACTED = "[REDACTED]"

# Sengaja spesifik supaya angka fakta (n=1175, 79.0%) tidak ikut terhapus.
_HEAD_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bsk-[A-Za-z0-9_\-]{6,}\b"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]{8,}"),
)
_ASSIGN_PATTERN = re.compile(
    r"(?i)\b(api[_-]?key|apikey|secret|token|passwd|password|authorization)\b"
    r"(\s*[:=]\s*[\"']?)([A-Za-z0-9._\-]{6,})"
)
SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (*_HEAD_PATTERNS, _ASSIGN_PATTERN)

# Nama env yang lazim memuat kunci (fallback bila pemanggil tidak menyebut daftar).
DEFAULT_KEY_ENVS: tuple[str, ...] = (
    "HERMES_CUSTOM_NUTARALINE_CO_UK_API_KEY",
    "QONEK_API_KEY",
)


def _redact_assign(m: re.Match[str]) -> str:
    # Pertahankan nama kunci agar konteks tetap terbaca; hanya nilainya yang dihapus.
    return f"{m.group(1)}{m.group(2)}{REDACTED}"


def scrub(text: str, secret_values: Iterable[str] | None = None) -> tuple[str, bool]:
    """Ganti pola kunci + nilai rahasia yang diberikan. Kembalikan ``(teks_bersih, ada_perubahan)``."""
    if not text:
        return text, False
    out = text
    for pat in _HEAD_PATTERNS:
        out = pat.sub(REDACTED, out)
    out = _ASSIGN_PATTERN.sub(_redact_assign, out)
    for val in secret_values or ():
        if val and len(val) >= 6 and val in out:
            out = out.replace(val, REDACTED)
    return out, out != text


def scrub_env(text: str, env_names: Iterable[str] = DEFAULT_KEY_ENVS) -> tuple[str, bool]:
    values = [os.environ.get(name, "") for name in env_names]
    return scrub(text, [v for v in values if v])


def scrub_all(
    text: str,
    env_names: Iterable[str] | None = None,
    secret_values: Iterable[str] | None = None,
) -> tuple[str, bool]:
    """Scrub pola + nilai env (default daftar kunci platform) + nilai rahasia eksplisit."""
    names = tuple(env_names) if env_names is not None else DEFAULT_KEY_ENVS
    values = [os.environ.get(name, "") for name in names]
    if secret_values:
        values.extend(secret_values)
    return scrub(text, [v for v in values if v])
