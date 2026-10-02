"""Transport notifikasi (P1-T8).

Aturan: transport **tidak pernah** menerima kredensial di dalam payload. Token dikirim lewat
header, dibaca dari env/berkas root-only, dan tidak pernah dicatat ke log.

`HttpTransport` bisa diarahkan ke webhook apa pun (mis. bridge Telegram); tes memakai server
HTTP lokal sungguhan supaya "terkirim" terbukti, bukan diasumsikan.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

__all__ = [
    "DeliveryResult",
    "HttpTransport",
    "NullTransport",
    "TelegramTransport",
    "Transport",
    "transport_from_env",
]

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


class TelegramTransport:
    """Kirim langsung ke Bot API Telegram (tanpa bridge tambahan).

    Butuh tiga hal dari owner di `/etc/warroom/notifier.env` (mode 600, root):

        WARROOM_TELEGRAM_BOT_TOKEN=...
        WARROOM_TELEGRAM_CHAT_ID=...
        WARROOM_TELEGRAM_THREAD_ID=...   # opsional: topik di dalam grup

    Token **tidak pernah** masuk ke badan pesan, log, atau repo. Pesan memuat subjek,
    tingkat, pesan, dan aksi yang disarankan — tanpa satu pun angka yang tidak berasal
    dari fakta.
    """

    name = "telegram"

    def __init__(
        self,
        token: str,
        chat_id: str,
        thread_id: str | None = None,
        timeout_s: float = 8.0,
        api_base: str | None = None,
    ) -> None:
        self.token = token
        self.chat_id = chat_id
        self.thread_id = thread_id
        self.timeout_s = timeout_s
        # api_base bisa ditimpa untuk pengujian (server lokal), tanpa mengubah produksi.
        self.api_base = (api_base or os.environ.get("WARROOM_TELEGRAM_API_BASE")
                         or "https://api.telegram.org").rstrip("/")

    @property
    def url(self) -> str:
        return f"{self.api_base}/bot{self.token}/sendMessage"

    def send(self, subject: str, message: str, severity: str, payload: dict) -> DeliveryResult:
        aksi = str(payload.get("suggested_action") or "").strip()
        teks = f"[{severity.upper()}] {subject}\n{message}"
        if aksi:
            teks += f"\n\nYang bisa dilakukan: {aksi}"
        body: dict[str, object] = {
            "chat_id": self.chat_id,
            "text": teks,
            "disable_web_page_preview": True,
        }
        if self.thread_id:
            body["message_thread_id"] = self.thread_id
        req = urllib.request.Request(
            self.url,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:  # noqa: S310
                return DeliveryResult(200 <= resp.status < 300, f"telegram {resp.status}")
        except urllib.error.HTTPError as exc:
            # Badan respons bisa memuat id chat, bukan token — tetap dipotong pendek.
            return DeliveryResult(False, f"telegram http {exc.code}")
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
    """Pilih transport dari env/berkas root-only.

    Urutan: Telegram (bila token+chat ada) → webhook HTTP → Null (alert tetap di DB,
    tidak pernah diklaim terkirim).
    """
    import os

    token = os.environ.get("WARROOM_TELEGRAM_BOT_TOKEN") or _from_file("WARROOM_TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("WARROOM_TELEGRAM_CHAT_ID") or _from_file("WARROOM_TELEGRAM_CHAT_ID")
    if token and chat:
        thread = os.environ.get("WARROOM_TELEGRAM_THREAD_ID") or _from_file("WARROOM_TELEGRAM_THREAD_ID")
        return TelegramTransport(token, chat, thread)

    url = os.environ.get("WARROOM_ALERT_WEBHOOK") or _from_file("WARROOM_ALERT_WEBHOOK")
    if url:
        wtoken = os.environ.get("WARROOM_ALERT_TOKEN") or _from_file("WARROOM_ALERT_TOKEN")
        return HttpTransport(url, wtoken)
    return NullTransport()