"""Sidik jari kode yang BENAR-BENAR dimuat proses.

Latar (temuan audit 22 Okt 2026, TINGGI-4):
    ``/api/v1/build`` mengembalikan ``WARROOM_BUILD_ID`` dari ``/etc/warroom/build.env``.
    Nilai itu ditulis saat deploy dan dibandingkan dengan nilai yang dihitung di sesi
    deploy yang sama — jadi gate selalu cocok dengan dirinya sendiri dan tidak pernah
    menangkap drift. Kasus nyata 23 Okt 2026: API melayani
    ``build_id=f0c8e02-...`` sementara ``git HEAD`` sudah ``b861549`` (4 commit di
    depan), termasuk endpoint ``/api/v1/komuter/health`` yang tidak ada di commit
    yang dilaporkan.

Pendekatan:
    Hitung SHA-256 atas isi berkas sumber paket yang diimpor proses (bukan git HEAD).
    Hasilnya adalah sidik jari kode yang sedang berjalan, tidak bisa "basi" karena
    dihitung dari byte yang benar-benar ada di disk saat proses start.
"""

from __future__ import annotations

import hashlib
import os
from functools import lru_cache
from pathlib import Path
from typing import Iterable

# Berkas non-kode yang tetap memengaruhi perilaku runtime.
SUFFIX = (".py", ".json", ".toml", ".txt", ".j2")
# Direktori yang tidak menentukan perilaku kode.
SKIP_DIRS = {"__pycache__", ".pytest_cache", ".ruff_cache", "node_modules", ".git", "tests"}


def _akar_paket() -> list[Path]:
    """Direktori paket yang diimpor proses ini, dihitung dari lokasi modulnya."""
    akar: list[Path] = []
    kandidat = [
        Path(__file__).resolve().parent,  # warroom_core
    ]
    for nama_modul in ("warroom_api", "live_trading"):
        try:  # warroom_api hanya ada di proses API; live_trading = paket domain
            modul = __import__(nama_modul)
            lokasi = getattr(modul, "__file__", None)
            if lokasi:
                kandidat.append(Path(lokasi).resolve().parent)
        except Exception:  # pragma: no cover - worker tidak mengimpor warroom_api
            continue

    for p in kandidat:
        if p.is_dir() and p not in akar:
            akar.append(p)
    return akar


def _berkas(akar: Iterable[Path]) -> list[Path]:
    hasil: list[Path] = []
    for base in akar:
        for root, dirs, files in os.walk(base):
            dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
            for nama in sorted(files):
                if nama.endswith(SUFFIX):
                    hasil.append(Path(root) / nama)
    return sorted(hasil)


@lru_cache(maxsize=1)
def kode_fingerprint() -> str:
    """SHA-256 isi berkas sumber yang dimuat proses, 12 heksadesimal pertama.

    Di-cache: nilainya tidak boleh berubah selama proses hidup (kalau berubah,
    artinya ada berkas ditimpa di bawah proses yang sedang jalan — justru
    kondisi yang ingin dideteksi, dan itu urusan gate deploy, bukan endpoint).
    """
    h = hashlib.sha256()
    for path in _berkas(_akar_paket()):
        try:
            h.update(path.name.encode("utf-8", "replace"))
            h.update(b"\0")
            h.update(path.read_bytes())
            h.update(b"\0")
        except OSError:
            # Berkas hilang/izin ditolak saat hashing: catat sebagai penanda,
            # jangan diam-diam dilewati (itu akan menyamarkan drift).
            h.update(f"UNREADABLE:{path}".encode("utf-8", "replace"))
    return h.hexdigest()[:12]


@lru_cache(maxsize=1)
def jumlah_berkas() -> int:
    """Jumlah berkas yang ikut dihitung (untuk bukti di laporan build)."""
    return len(_berkas(_akar_paket()))


def info_build() -> dict[str, object]:
    """Gabungan semua identitas yang dipakai gate deploy."""
    from warroom_core import build_id as label_build_id

    return {
        "build_id": label_build_id(),  # label deploy (env), dipertahankan untuk kompatibilitas
        "kode_fingerprint": kode_fingerprint(),  # sidik jari isi kode yang JALAN
        "berkas_dihitung": jumlah_berkas(),
    }
