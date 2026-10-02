"""Pembacaan berkas lintas-host dengan jejak bukti (P4).

Kontrak yang sama untuk semua sumber jarak jauh/lokal terlarang: ``{payload, mtime, sha256}``
(``03-backend.md`` §9). Bila gagal: **status + alasan**, bukan nilai lama dan bukan nol.

Sebagian sumber milik user lain (mis. ``/var/lib/poly-paper`` mode 700 `poly-pilot`).
Di host ini `admin` punya sudo tanpa sandi — dan domain `live-trading` sudah memakai pola
`sudo cat` yang sama. Karena itu bacaan punya jalur cadangan `sudo -n cat`, dan bila itu pun
tidak tersedia hasilnya jujur: ``tidak-izin``.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

__all__ = ["Bacaan", "baca_json", "baca_jsonl_ekor", "ringkas_dir", "sha256_teks"]


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


def _baca_mentah(p: Path, pakai_sudo: bool) -> tuple[str | None, str, bool]:
    """Kembalikan (teks, status, lewat_sudo). Status: ok | tidak-ada | tidak-izin | rusak.

    `~` di-expand di sini supaya semua pemanggil (termasuk yang memakai path dari konfigurasi)
    tidak diam-diam mencari berkas di direktori bernama harfiah ``~``.
    """
    p = p.expanduser()
    try:
        return p.read_text(encoding="utf-8", errors="replace"), "ok", False
    except FileNotFoundError:
        return None, "tidak-ada", False
    except PermissionError:
        pass
    except OSError:
        return None, "rusak", False
    if not pakai_sudo:
        return None, "tidak-izin", False
    hasil = subprocess.run(  # noqa: S603 — path dari konfigurasi tetap, bukan input pengguna
        ["sudo", "-n", "cat", str(p)], capture_output=True, text=True, check=False, timeout=30
    )
    if hasil.returncode == 0:
        return hasil.stdout, "ok", True
    if "No such file" in hasil.stderr:
        return None, "tidak-ada", False
    return None, "tidak-izin", False


def baca_json(path: str | Path, *, pakai_sudo: bool = True) -> Bacaan:
    """Baca satu berkas JSON. Tidak pernah melempar untuk masalah berkas."""
    p = Path(path)
    teks, status, sudo = _baca_mentah(p, pakai_sudo)
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


def baca_jsonl_ekor(path: str | Path, n: int = 400, *, pakai_sudo: bool = True) -> Bacaan:
    """Baca ``n`` baris terakhir JSONL. Baris rusak dilewati dan dihitung di `meta`."""
    p = Path(path)
    if pakai_sudo:
        hasil = subprocess.run(  # noqa: S603
            ["sudo", "-n", "tail", f"-{int(n)}", str(p)],
            capture_output=True, text=True, check=False, timeout=30,
        )
        if hasil.returncode == 0:
            teks, status, sudo = hasil.stdout, "ok", True
        else:
            teks, status, sudo = _baca_mentah(p, False)
    else:
        teks, status, sudo = _baca_mentah(p, False)
    if status != "ok":
        return Bacaan(path=str(p), status=status, detail=f"tidak bisa dibaca ({status})")
    baris: list[dict[str, Any]] = []
    rusak = 0
    for b in (teks or "").splitlines():
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


def ringkas_dir(path: str | Path, *, pakai_sudo: bool = True) -> dict[str, Any]:
    """Jumlah berkas + total byte satu direktori (rekursif, hanya hitung).

    Dipakai untuk katalog dataset (recorder) tanpa membaca isinya.
    """
    p = Path(path)
    perintah = ["sudo", "-n", "bash", "-c", f"find {p} -type f | wc -l; du -sb {p} | cut -f1"]
    if pakai_sudo:
        hasil = subprocess.run(  # noqa: S603
            perintah, capture_output=True, text=True, check=False, timeout=120
        )
        if hasil.returncode == 0 and hasil.stdout.strip():
            bagian = hasil.stdout.split()
            if len(bagian) >= 2:
                return {"path": str(p), "files": int(bagian[0]), "bytes": int(bagian[1]), "status": "ok"}
    try:
        files = sum(1 for _ in p.rglob("*") if _.is_file())
        total = sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
        return {"path": str(p), "files": files, "bytes": total, "status": "ok"}
    except OSError as exc:
        return {"path": str(p), "status": "tidak-izin" if isinstance(exc, PermissionError) else "rusak",
                "detail": type(exc).__name__}