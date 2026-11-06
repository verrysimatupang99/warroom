"""Tes pembatas cakupan listener Telegram (patch DM).

Latar: `@client.on(events.NewMessage)` tanpa filter membuat engine memproses
**setiap** pesan yang terlihat akun — termasuk DM pribadi. Pesan DM ikut masuk
klasifikasi, dan bisa tersimpan bila kebetulan kena kata kunci trading.

Filter di sini adalah gerbang pertama (murah, sebelum I/O apa pun). Filter
blacklist/whitelist lama tetap berlaku dan tidak diubah.
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("TG_API_ID", "1")
os.environ.setdefault("TG_API_HASH", "uji-bukan-rahasia")

import engine  # noqa: E402


class TestBolehDiproses:
    def test_channel_lolos(self):
        assert engine.boleh_diproses(is_private=False, is_bot=False) is True

    def test_grup_lolos(self):
        assert engine.boleh_diproses(is_private=False, is_bot=False) is True

    def test_dm_dibuang(self):
        assert engine.boleh_diproses(is_private=True, is_bot=False) is False

    def test_bot_dibuang_walau_dm(self):
        # Bot bukan sumber sinyal; pesannya biasanya notifikasi.
        assert engine.boleh_diproses(is_private=True, is_bot=True) is False

    def test_dm_dari_bot_tetap_dibuang(self):
        assert engine.boleh_diproses(is_private=True, is_bot=True) is False


class TestFlagEnv:
    def test_default_dm_dibuang(self):
        assert engine.IZINKAN_DM is False

    def test_env_bisa_mengaktifkan_lagi(self, monkeypatch):
        # Escape hatch: perilaku lama tetap bisa dipulihkan tanpa mengubah kode.
        monkeypatch.setenv("TG_IZINKAN_DM", "1")
        importlib.reload(engine)
        assert engine.IZINKAN_DM is True
        assert engine.boleh_diproses(is_private=True, is_bot=False) is True
        monkeypatch.delenv("TG_IZINKAN_DM", raising=False)
        importlib.reload(engine)
        assert engine.IZINKAN_DM is False

    def test_env_kosong_berarti_mati(self, monkeypatch):
        monkeypatch.setenv("TG_IZINKAN_DM", "")
        importlib.reload(engine)
        assert engine.IZINKAN_DM is False
