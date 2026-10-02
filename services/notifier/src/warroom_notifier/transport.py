"""Transport notifikasi (P1-T8).

Aturan: transport **tidak pernah** menerima kredensial di dalam payload. Token dikirim lewat
header, dibaca dari env/berkas root-only, dan tidak pernah dicatat ke log.

`HttpTransport` bisa diarahkan ke webhook apa pun (mis. bridge Telegram); tes memakai server
HTTP lokal sungguhan supaya "terkirim" terbukti, bukan diasumsikan.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

__all__ = ["DeliveryResult", "HttpTransport", "NullTransport", "Transport", "transport_from_env"]

ENV_FILE = Path("/etc/warroom/notifier.env")


class Transport(Protocol):
    name: str

    def send(self, subject: str, message: str, severity: str, payload: dict) -> DeliveryResult: ...


@dataclass(frozen=True)
class DeliveryResult:
    ok: bool
    detail: str


class NullTransport:
    """Tanpa tujuan terkonfigurasi: alert tetap tercatat di DB, tidak diklaim terkirim."""

    name = "null"

    def send(self, subject: str, message: str, severity: str, payload: dict) -> DeliveryResult:
        return DeliveryResult(False, "tidak ada transport terkonfigurasi (alert hanya di DB)")


class HttpTransport:
    """POST JSON ke webhook. Timeout pendek supaya worker tidak tersandera."""

    name = "http"

    def __init__(self, url: str, token: str | None = None, timeout_s: float = 8.0) -> None:
        self.url = url
        self.token = token
        self.timeout_s = timeout_s

    def send(self, subject: str, message: str, severity: str, payload: dict) -> DeliveryResult:
        body = json.dumps(
            {"subject": subject, "message": message, "severity": severity, "detail": payload},
            ensure_ascii=False,
        ).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        req = urllib.request.Request(self.url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:  # noqa: S310 — URL dari config root-only
                return DeliveryResult(200 <= resp.status < 300, f"http {resp.status}")
        except urllib.error.HTTPError as exc:
            return DeliveryResult(False, f"http {exc.code}")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            return DeliveryResult(False, f"{type(exc).__name__}: {exc}")


def _env_file() -> Path:
    import os

    return Path(os.environ.get("WARROOM_NOTIFIER_ENV_FILE", str(ENV_FILE)))


def _from_file(key: str) -> str | None:
    """Baca nilai dari berkas env root-only.

    Catatan penting: `Path.exists()` **melempar** `PermissionError` (bukan mengembalikan False)
    bila direktori induknya 700 milik root. Karena itu seluruh akses berkas dibungkus —
    transport hanya boleh gagal dengan hasil "tidak dikonfigurasi", bukan exception.
    """
    path = _env_file()
    try:
        if not path.exists():
            return None
        teks = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    for baris in teks.splitlines():
        if baris.startswith(f"{key}="):
            return baris.split("=", 1)[1].strip().strip("\"'")
    return None


def transport_from_env() -> Transport:
    """URL webhook dari env `WARROOM_ALERT_WEBHOOK` atau berkas root-only; default Null."""
    import os

    url = os.environ.get("WARROOM_ALERT_WEBHOOK") or _from_file("WARROOM_ALERT_WEBHOOK")
    if not url:
        return NullTransport()
    token = os.environ.get("WARROOM_ALERT_TOKEN") or _from_file("WARROOM_ALERT_TOKEN")
    return HttpTransport(url, token)