"""Tes scrub kredensial — pola kunci dan nilai env tidak boleh lolos."""

from __future__ import annotations

from warroom_llm.scrub import REDACTED, scrub, scrub_all


def test_pola_sk_dan_bearer_dihapus() -> None:
    bersih, kena = scrub("pakai sk-ABCDEF123456 dan Bearer abcdef1234567890 ya")
    assert kena is True
    assert "sk-ABCDEF123456" not in bersih
    assert "abcdef1234567890" not in bersih
    assert REDACTED in bersih


def test_penugasan_kunci_mempertahankan_nama() -> None:
    bersih, kena = scrub("api_key=rahasia123456")
    assert kena is True
    assert "rahasia123456" not in bersih
    assert "api_key" in bersih


def test_nilai_env_dihapus(monkeypatch) -> None:
    monkeypatch.setenv("QONEK_API_KEY", "kunci-panjang-rahasia")
    bersih, kena = scrub_all("nilai kunci-panjang-rahasia di sini", ("QONEK_API_KEY",))
    assert kena is True
    assert "kunci-panjang-rahasia" not in bersih


def test_angka_fakta_tidak_ikut_terhapus() -> None:
    asli = "F1: n=1175, win=79.0%, be=77.0%, ci=[76.6,81.2]"
    bersih, kena = scrub_all(asli, ("QONEK_API_KEY",))
    assert kena is False
    assert bersih == asli


def test_teks_tanpa_kredensial_tidak_berubah() -> None:
    bersih, kena = scrub("narasi biasa tanpa kunci")
    assert bersih == "narasi biasa tanpa kunci"
    assert kena is False
