"""Tes `ekspor_dialog.py` — pembentukan baris CSV tanpa koneksi Telegram.

Fokus uji: hal yang menentukan apakah daftar hasil ekspor bisa dipakai sebagai
lembar kerja "join ulang". Kalau tipe chat salah dikenali, DM ikut masuk daftar
kerja, atau nama orang ikut tercatat, hasilnya menyesatkan dan berisiko privasi.
"""

from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("TG_API_ID", "1")
os.environ.setdefault("TG_API_HASH", "uji-bukan-rahasia")

import ekspor_dialog  # noqa: E402


class EntitasPalsu:
    def __init__(self, username=None, verified=False):
        self.username = username
        self.verified = verified


class DialogPalsu:
    """Tiruan `telethon.tl.custom.Dialog` — hanya atribut yang dipakai skrip."""

    def __init__(self, id, title=None, *, channel=False, group=False, user=False, entitas=None):
        self.id = id
        self.title = title
        self.is_channel = channel
        self.is_group = group
        self.is_user = user
        self.entity = entitas if entitas is not None else EntitasPalsu()


def _cari(baris, nama):
    return next(b for b in baris if b["nama"] == nama)


class TestKlasifikasiTipe:
    def test_channel_ditandai_join_ulang(self):
        baris = ekspor_dialog.kumpulkan_baris([DialogPalsu(1, "SahamTalk", channel=True)])
        assert baris[0]["tipe"] == "channel"
        assert baris[0]["arahan"] == "join ulang"

    def test_grup_ditandai_join_ulang(self):
        baris = ekspor_dialog.kumpulkan_baris([DialogPalsu(2, "Trader Ndeso", group=True)])
        assert baris[0]["tipe"] == "grup"
        assert baris[0]["arahan"] == "join ulang"

    def test_dm_ditandai_abaikan(self):
        baris = ekspor_dialog.kumpulkan_baris([DialogPalsu(3, "Budi", user=True)])
        assert baris[0]["tipe"] == "dm"
        assert baris[0]["arahan"] == "abaikan"

    def test_supergrup_telethon_adalah_channel_dan_grup(self):
        # Telethon menandai supergrup dengan is_channel=True DAN is_group=True.
        baris = ekspor_dialog.kumpulkan_baris([DialogPalsu(4, "RuangDegen", channel=True, group=True)])
        assert baris[0]["tipe"] == "channel"
        assert baris[0]["arahan"] == "join ulang"


class TestPrivasi:
    def test_nama_dm_tidak_dicatat(self):
        baris = ekspor_dialog.kumpulkan_baris(
            [DialogPalsu(5, "Nama Orang Asli", user=True, entitas=EntitasPalsu(username="orang"))]
        )
        assert "Nama Orang Asli" not in baris[0]["nama"]
        assert baris[0]["username"] == ""

    def test_username_hanya_untuk_channel_grup(self):
        baris = ekspor_dialog.kumpulkan_baris(
            [
                DialogPalsu(6, "Callisto FX", channel=True, entitas=EntitasPalsu(username="callisto")),
                DialogPalsu(7, "Seseorang", user=True, entitas=EntitasPalsu(username="seseorang")),
            ]
        )
        assert _cari(baris, "Callisto FX")["username"] == "callisto"
        assert _cari(baris, "(dm — tidak dicatat)")["username"] == ""


class TestUrutan:
    def test_join_ulang_di_atas_dm_di_bawah(self):
        baris = ekspor_dialog.kumpulkan_baris(
            [
                DialogPalsu(8, "Zzz DM", user=True),
                DialogPalsu(9, "SahamTalk", channel=True),
                DialogPalsu(10, "Grup A", group=True),
            ]
        )
        arahan = [b["arahan"] for b in baris]
        assert arahan == ["join ulang", "join ulang", "abaikan"]

    def test_channel_sebelum_grup(self):
        baris = ekspor_dialog.kumpulkan_baris(
            [
                DialogPalsu(11, "Grup A", group=True),
                DialogPalsu(12, "Channel B", channel=True),
            ]
        )
        assert [b["tipe"] for b in baris] == ["channel", "grup"]


class TestTulisCsv:
    def test_header_dan_isi_benar(self, tmp_path):
        baris = ekspor_dialog.kumpulkan_baris(
            [DialogPalsu(13, "Malong VIP", channel=True, entitas=EntitasPalsu(username="malongvip"))]
        )
        path = tmp_path / "dialog.csv"
        ekspor_dialog.tulis_csv(baris, str(path))

        with open(path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert list(rows[0].keys()) == [
            "tipe",
            "nama",
            "id",
            "username",
            "terverifikasi",
            "arahan",
        ]
        assert rows[0]["nama"] == "Malong VIP"
        assert rows[0]["username"] == "malongvip"

    def test_berkas_mode_600(self, tmp_path):
        # Daftar channel bisa mengungkap sumber sinyal — jangan terbaca pengguna lain.
        path = tmp_path / "dialog.csv"
        ekspor_dialog.tulis_csv([], str(path))
        assert oct(path.stat().st_mode & 0o777) == "0o600"


class TestKredensial:
    def test_env_kosong_berhenti_dengan_pesan_jelas(self, monkeypatch):
        # Skrip tidak boleh jalan dengan kredensial kosong lalu gagal misterius.
        monkeypatch.delenv("TG_API_ID", raising=False)
        with pytest.raises(SystemExit, match="TG_API_ID"):
            ekspor_dialog._wajib_env("TG_API_ID")

    def test_env_spasi_saja_dianggap_kosong(self, monkeypatch):
        monkeypatch.setenv("TG_API_ID", "   ")
        with pytest.raises(SystemExit, match="TG_API_ID"):
            ekspor_dialog._wajib_env("TG_API_ID")

    def test_api_id_bukan_angka_ditolak(self):
        with pytest.raises(SystemExit, match="harus angka"):
            ekspor_dialog._parse_api_id("abc")

    def test_api_id_angka_diterima(self):
        assert ekspor_dialog._parse_api_id("1234567") == 1234567
