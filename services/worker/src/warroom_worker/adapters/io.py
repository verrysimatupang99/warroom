"""Pembacaan berkas lintas-host dengan jejak bukti (P4).

Kontrak yang sama untuk semua sumber yang terlarang: ``{payload, mtime, sha256}``
(``03-backend.md`` §9). Bila gagal: **status + alasan**, bukan nilai lama dan bukan nol.

Kebijakan baca: berkas dibaca langsung dulu (tanpa subprocess). ``sudo -n`` hanya untuk
kombinasi perintah+path yang persis ada di allowlist sudoers; di luar itu setiap penarikan
sudo pasti ditolak (``a password is required`` di konteks systemd) dan tidak pernah dipanggil.
Kegagalan izin di-cache 10 menit supaya tidak diulang tiap tick; hasil non-ok tetap jujur
(``tidak-izin``), bukan daftar kosong yang menyamar jadi data.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

__all__ = [
    "Bacaan",
    "baca_json",
    "baca_jsonl_ekor",
    "reset_cache_gagal",
    "ringkas_dir",
    "sha256_teks",
]

# Cermin /etc/sudoers.d/warroom-poly-readonly: hanya kombinasi persis ini yang boleh
# memakai sudo, sisanya selesai dengan status jujur tanpa menyulap proses.
_CAT_SUDO = frozenset({
    "/var/lib/poly-paper/execution-paper-shadow-state.json",
    "/var/lib/poly-paper-candidate/execution-paper-shadow-state.json",
    "/var/lib/poly-paper-fade/execution-paper-shadow-state.json",
    "/var/lib/poly-paper-favorite/execution-paper-shadow-state.json",
    "/var/lib/poly-agent/agent-summary.json",
    "/var/lib/poly-agent/agent-state.json",
    "/var/lib/poly-agent/harness-heartbeat.json",
    "/var/lib/poly-pilot/snipe-live-v1-state.json",
})

_TAIL_SUDO: dict[int, frozenset[str]] = {
    400: frozenset({
        "/var/lib/poly-paper/execution-paper-shadow.jsonl",
        "/var/lib/poly-paper-candidate/execution-paper-shadow.jsonl",
        "/var/lib/poly-paper-fade/execution-paper-shadow.jsonl",
        "/var/lib/poly-paper-favorite/execution-paper-shadow.jsonl",
        "/var/lib/poly-pilot/execution-paper-shadow.jsonl",
    }),
    200: frozenset({
        "/var/lib/poly-agent/agent-lessons.jsonl",
        "/var/lib/poly-agent/agent-upgrades.jsonl",
    }),
    50: frozenset({"/var/lib/poly-agent/agent-lessons.jsonl"}),
}

_TTL_GAGAL_S = 600

_gagal: dict[str, float] = {}
_kunci_gagal = threading.Lock()


def reset_cache_gagal() -> None:
    """Bersihkan cache kegagalan izin (untuk uji; produksi cukup menunggu TTL)."""
    with _kunci_gagal:
        _gagal.clear()


def _gagal_segar(kunci: str) -> bool:
    with _kunci_gagal:
        batas = _gagal.get(kunci)
        return batas is not None and time.monotonic() < batas


def _catat_gagal(kunci: str) -> None:
    with _kunci_gagal:
        _gagal[kunci] = time.monotonic() + _TTL_GAGAL_S


@dataclass
class Bacaan:
    """Hasil pembacaan satu berkas + jejak sumbernya."""

    path: str
    status: str  # ok | tidak-ada | tidak-izin | rusak
    data: Any | None = None
    mtime: datetime | None = None
    sha256: str | None = None
    detail: str = ""
    lewat_sudo: bool = False
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status == "ok"


def sha256_teks(teks: str) -> str:
    return hashlib.sha256(teks.encode("utf-8")).hexdigest()


def _mtime(p: Path) -> datetime | None:
    try:
        return datetime.fromtimestamp(p.stat().st_mtime, tz=UTC)
    except OSError:
        return None


def _sudo_cat(p: Path) -> str | None:
    """Baca via allowlist sudo; None bila ditolak — kegagalan di-cache."""
    kunci = f"cat:{p}"
    if _gagal_segar(kunci):
        return None
    try:
        hasil = subprocess.run(  # noqa: S603 — argv tetap, path konfigurasi server
            ["sudo", "-n", "cat", str(p)], capture_output=True, text=True, check=False, timeout=30
        )
    except (OSError, subprocess.SubprocessError):
        _catat_gagal(kunci)
        return None
    if hasil.returncode == 0:
        return hasil.stdout
    _catat_gagal(kunci)
    return None


def _baca_mentah(p: Path) -> tuple[str | None, str, bool]:
    """Kembalikan (teks, status, lewat_sudo). Status: ok | tidak-ada | tidak-izin | rusak.

    ``~`` di-expand di sini supaya semua pemanggil (termasuk yang memakai path dari
    konfigurasi) tidak diam-diam mencari berkas di direktori bernama harfiah ``~``.
    """
    p = p.expanduser()
    try:
        return p.read_text(encoding="utf-8", errors="replace"), "ok", False
    except FileNotFoundError:
        return None, "tidak-ada", False
    except PermissionError:
        if str(p) in _CAT_SUDO:
            teks = _sudo_cat(p)
            if teks is not None:
                return teks, "ok", True
    except OSError:
        return None, "rusak", False
    return None, "tidak-izin", False


def baca_json(path: str | Path) -> Bacaan:
    """Baca satu berkas JSON. Tidak pernah melempar untuk masalah berkas."""
    p = Path(path)
    teks, status, sudo = _baca_mentah(p)
    if status != "ok":
        return Bacaan(path=str(p), status=status, detail=f"tidak bisa dibaca ({status})", lewat_sudo=sudo)
    try:
        data = json.loads(teks or "")
    except json.JSONDecodeError as exc:
        return Bacaan(
            path=str(p), status="rusak", detail=f"JSONDecodeError: {exc}", lewat_sudo=sudo,
            sha256=sha256_teks(teks or ""),
        )
    return Bacaan(
        path=str(p), status="ok", data=data, mtime=_mtime(p), sha256=sha256_teks(teks or ""),
        lewat_sudo=sudo,
    )


def _ekor_langsung(p: Path, n: int) -> tuple[str | None, str]:
    """Baca ``n`` baris terakhir lewat seek balik — tanpa subprocess."""
    try:
        with p.open("rb") as fh:
            pos = fh.seek(0, os.SEEK_END)
            bongkahan = b""
            while pos > 0 and bongkahan.count(b"\n") <= n:
                blok = min(1 << 20, pos)
                pos -= blok
                fh.seek(pos)
                bongkahan = fh.read(blok) + bongkahan
    except FileNotFoundError:
        return None, "tidak-ada"
    except PermissionError:
        return None, "tidak-izin"
    except OSError:
        return None, "rusak"
    teks = bongkahan.decode("utf-8", errors="replace")
    if pos > 0:
        # batas bongkahan bisa memotong satu baris — buang potongan setengah baris itu
        teks = teks.split("\n", 1)[1]
    return teks, "ok"


def _ekor_sudo(p: Path, n: int) -> str | None:
    """Ekor via allowlist sudo; None bila ditolak — kegagalan di-cache."""
    kunci = f"tail:{n}:{p}"
    if _gagal_segar(kunci):
        return None
    try:
        hasil = subprocess.run(  # noqa: S603 — argv tetap, path konfigurasi server
            ["sudo", "-n", "tail", f"-{int(n)}", str(p)],
            capture_output=True, text=True, check=False, timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        _catat_gagal(kunci)
        return None
    if hasil.returncode == 0:
        return hasil.stdout
    _catat_gagal(kunci)
    return None


def baca_jsonl_ekor(path: str | Path, n: int = 400) -> Bacaan:
    """Baca ``n`` baris terakhir JSONL. Baris rusak dilewati dan dihitung di `meta`."""
    p = Path(path).expanduser()
    teks, status = _ekor_langsung(p, n)
    sudo = False
    if status == "tidak-izin" and str(p) in _TAIL_SUDO.get(n, frozenset()):
        teks = _ekor_sudo(p, n)
        if teks is not None:
            status, sudo = "ok", True
    if status != "ok":
        return Bacaan(path=str(p), status=status, detail=f"tidak bisa dibaca ({status})", lewat_sudo=sudo)
    baris: list[dict[str, Any]] = []
    rusak = 0
    for b in (teks or "").splitlines()[-n:] if n > 0 else []:
        if not b.strip():
            continue
        try:
            d = json.loads(b)
        except json.JSONDecodeError:
            rusak += 1
            continue
        if isinstance(d, dict):
            baris.append(d)
        else:
            rusak += 1
    return Bacaan(
        path=str(p), status="ok", data=baris, mtime=_mtime(p), lewat_sudo=sudo,
        sha256=sha256_teks(teks or ""),
        meta={"baris": len(baris), "rusak": rusak, "sha256_cakupan": f"ekor {n} baris"},
    )


def ringkas_dir(path: str | Path) -> dict[str, Any]:
    """Jumlah berkas + total byte satu direktori (rekursif, hanya berkas biasa).

    Dipakai untuk katalog dataset (recorder) tanpa membaca isinya. Direktori/berkas yang
    tak terbaca karena izin → ``tidak-izin`` (di-cache), bukan hitungan nol yang menyamar.
    """
    p = Path(path).expanduser()
    kunci = f"dir:{p}"
    if _gagal_segar(kunci):
        return {"path": str(p), "status": "tidak-izin", "detail": "kegagalan izin masih ter-cache"}
    salah: list[OSError] = []
    jumlah = 0
    total = 0
    try:
        for root, _sub, berkas in os.walk(p, onerror=salah.append):
            for b in berkas:
                jumlah += 1
                try:
                    total += (Path(root) / b).stat().st_size
                except OSError as exc:
                    salah.append(exc)
    except OSError as exc:  # scandir atas biasanya sudah ditangkap via onerror
        salah.append(exc)
    if salah:
        _catat_gagal(kunci)
        izin = any(isinstance(e, PermissionError) for e in salah)
        return {"path": str(p), "status": "tidak-izin" if izin else "rusak",
                "detail": type(salah[0]).__name__}
    return {"path": str(p), "files": jumlah, "bytes": total, "status": "ok"}
