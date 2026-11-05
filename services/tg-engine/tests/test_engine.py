"""Tes logika penyaring/klasifikasi listener Telegram.

`engine.py` sebelumnya tidak ada di repo sama sekali (di-gitignore karena memuat
API_ID/API_HASH), sehingga logika yang menentukan sinyal mana yang disimpan tidak
pernah diuji maupun ditinjau. Tes ini mengunci perilakunya.

Kredensial palsu diset SEBELUM impor: modul menolak start tanpa `TG_API_ID`/
`TG_API_HASH`, dan itu justru perilaku yang ingin dipertahankan.
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("TG_API_ID", "1")
os.environ.setdefault("TG_API_HASH", "uji-bukan-rahasia")

import engine  # noqa: E402


class TestKlasifikasi:
    def test_forex_dari_kata_kunci(self):
        assert engine.classify_message("XAUUSD buy limit 3980", "") == "FOREX"

    def test_saham_dari_kata_kunci(self):
        assert engine.classify_message("IHSG naik, BBRI breakout", "") == "SAHAM"

    def test_crypto_dari_kata_kunci(self):
        assert engine.classify_message("BTC long 97000", "") == "CRYPTO"

    def test_obrolan_biasa_jadi_general(self):
        assert engine.classify_message("halo semua, selamat pagi", "") == "GENERAL"

    def test_channel_dikenal_menang_atas_skor_kata(self):
        # "Saham Sukses Berkah" dipetakan SAHAM walau teks menyebut gold
        assert engine.classify_message("gold naik", "Saham Sukses Berkah") == "FOREX"
        assert engine.classify_message("ihsg menguat", "SahamTalk") == "SAHAM"

    def test_petunjuk_nama_channel_dipakai_saat_skor_nol(self):
        assert engine.classify_message("pagi", "Malong Freemium") == "FOREX"
        assert engine.classify_message("pagi", "RuangDegen") == "CRYPTO"


class TestBlacklist:
    def test_grup_spam_dikenali(self):
        assert engine.is_blacklisted("Kaum Hasrat") is True
        assert engine.is_blacklisted("Gudang138 Slot") is True

    def test_channel_trading_tidak_kena_blacklist(self):
        assert engine.is_blacklisted("Callisto FX") is False


class TestKredensial:
    def test_tanpa_env_modul_menolak_start(self, monkeypatch):
        monkeypatch.delenv("TG_API_ID", raising=False)
        monkeypatch.delenv("TG_API_HASH", raising=False)
        with pytest.raises(RuntimeError, match="TG_API_ID"):
            importlib.reload(engine)
        # Pulihkan modul untuk tes lain.
        monkeypatch.setenv("TG_API_ID", "1")
        monkeypatch.setenv("TG_API_HASH", "uji-bukan-rahasia")
        importlib.reload(engine)

    def test_api_id_harus_angka(self, monkeypatch):
        monkeypatch.setenv("TG_API_ID", "bukan-angka")
        with pytest.raises(RuntimeError, match="harus angka"):
            importlib.reload(engine)
        monkeypatch.setenv("TG_API_ID", "1")
        importlib.reload(engine)
