#!/usr/bin/env python3
"""ekspor_dialog.py — simpan daftar channel/grup dari sesi Telethon ke CSV.

Kegunaan: sebelum memutar kredensial Telegram (atau mengganti akun), catat dulu
semua channel/grup yang sudah di-join akun ini. Daftar itu jadi lembar kerja untuk
join ulang setelah akun/sesi berganti — tanpa perlu menebak dari ingatan.

Skrip ini READ-ONLY terhadap Telegram:
  - tidak mengirim pesan, tidak join/leave, tidak mengubah profil
  - hanya memanggil get_dialogs() lalu menulis CSV di disk lokal

Kredensial dibaca dari environment, sama seperti `engine.py`. Skrip tidak pernah
mencetak, mencatat, atau menyimpan API ID/hash — hanya daftar chat.

Pakai (di server, dari folder tempat `trading_session.session` berada):

    TG_API_ID=... TG_API_HASH=... python3 ekspor_dialog.py
    # atau, bila env sudah dimuat unit:
    set -a; . /etc/warroom/tg-engine.env; set +a
    python3 ekspor_dialog.py

Keluaran: dialog-<YYYYmmdd-HHMM>.csv di direktori kerja, mode 600.
Kolom: tipe,nama,id,username,terverifikasi,arahan

`arahan` = "join ulang" untuk channel/grup, "abaikan" untuk DM & bot. DM tidak
ikut disimpan namanya secara detail karena itu data pribadi, bukan sumber sinyal.
"""

from __future__ import annotations

import asyncio
import csv
import os
import sys
from datetime import UTC, datetime

try:
    from telethon import TelegramClient
except ImportError:  # pragma: no cover
    sys.exit("telethon belum terpasang. Jalankan: pip install telethon")

SESSION_NAME = os.environ.get("TG_SESSION_NAME", "trading_session")


def _wajib_env(nama: str) -> str:
    nilai = os.environ.get(nama, "").strip()
    if not nilai:
        sys.exit(
            f"{nama} kosong. Isi lewat environment, jangan hardcode:\n"
            "  set -a; . /etc/warroom/tg-engine.env; set +a"
        )
    return nilai


def _tipe(dialog) -> str:
    if dialog.is_channel:
        return "channel"
    if dialog.is_group:
        return "grup"
    if dialog.is_user:
        return "dm"
    return "lain"


def kumpulkan_baris(dialog_list) -> list[dict]:
    """Ubah daftar dialog Telethon jadi baris CSV.

    Dipisah dari I/O jaringan supaya bisa diuji tanpa koneksi Telegram.
    DM tidak menyertakan judul (nama orang) — hanya penanda agar tidak bocor ke
    berkas yang mungkin ikut tersalin ke tempat lain.
    """
    baris = []
    for d in dialog_list:
        tipe = _tipe(d)
        judul = getattr(d, "title", None)
        entitas = getattr(d, "entity", None)
        username = getattr(entitas, "username", None) or ""
        terverifikasi = bool(getattr(entitas, "verified", False))
        baris.append(
            {
                "tipe": tipe,
                "nama": (judul or "(tanpa judul)") if tipe in ("channel", "grup") else "(dm — tidak dicatat)",
                "id": str(getattr(d, "id", "")),
                "username": username if tipe in ("channel", "grup") else "",
                "terverifikasi": "ya" if terverifikasi else "tidak",
                "arahan": "join ulang" if tipe in ("channel", "grup") else "abaikan",
            }
        )
    baris.sort(key=lambda r: (r["arahan"] != "join ulang", r["tipe"], r["nama"].lower()))
    return baris


def _parse_api_id(nilai: str) -> int:
    """API ID Telegram selalu angka. Tolak lebih awal dengan pesan yang jelas."""
    try:
        return int(nilai)
    except (TypeError, ValueError):
        sys.exit(f"TG_API_ID harus angka, bukan {nilai!r}")


async def ambil_dialog() -> list[dict]:
    api_id_int = _parse_api_id(_wajib_env("TG_API_ID"))
    api_hash = _wajib_env("TG_API_HASH")

    client = TelegramClient(SESSION_NAME, api_id_int, api_hash)
    await client.connect()
    try:
        if not await client.is_user_authorized():
            sys.exit(
                f"Sesi '{SESSION_NAME}.session' tidak terotorisasi. "
                "Jalankan sekali di tempat sesi itu dibuat, atau login ulang."
            )
        me = await client.get_me()
        print(f"AKUN: {me.first_name} (@{me.username or '-'}) id={me.id}")
        dialog = await client.get_dialogs()
        return kumpulkan_baris(dialog)
    finally:
        await client.disconnect()


def tulis_csv(baris: list[dict], path: str) -> None:
    kolom = ["tipe", "nama", "id", "username", "terverifikasi", "arahan"]
    # Buka dengan mode 600 agar daftar channel tidak terbaca pengguna lain di server.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=kolom)
        w.writeheader()
        w.writerows(baris)


def main() -> None:
    baris = asyncio.run(ambil_dialog())
    stempel = datetime.now(UTC).strftime("%Y%m%d-%H%M")
    path = f"dialog-{stempel}.csv"
    tulis_csv(baris, path)

    channel = sum(1 for b in baris if b["tipe"] == "channel")
    grup = sum(1 for b in baris if b["tipe"] == "grup")
    dm = sum(1 for b in baris if b["tipe"] == "dm")
    print(f"Tersimpan: {path} (mode 600)")
    print(f"channel={channel} grup={grup} dm={dm} → wajib join ulang: {channel + grup}")


if __name__ == "__main__":
    main()
