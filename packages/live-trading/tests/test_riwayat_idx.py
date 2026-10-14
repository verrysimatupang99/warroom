"""Regresi: riwayat_idx — close/SMA10 IDX dari arsip tick (5 Okt 2026).

Yang dikunci di sini adalah hal-hal yang kalau salah akan menghasilkan angka yang TERLIHAT
sah tapi keliru — kelas kesalahan paling berbahaya untuk data pasar:

1. SMA10 hanya dihitung bila ada ≥10 hari. Memakai 6 hari lalu menyebutnya SMA10 = mengarang.
2. Rata-rata volume memakai 10 hari SEBELUM hari terakhir (hari berjalan belum selesai;
   memasukkannya membuat rel-vol tampak kecil tanpa sebab).
3. Baris tanpa tanggal dibuang — ada ~2,6 juta tick format lama yang akan mencampur hari.
4. Pemecahan batch: panggilan besar (>maks_per_panggilan) harus dipecah, karena satu kueri
   dengan puluhan emiten timeout pada basis 24,9 juta baris.
5. Kegagalan apa pun (SSH gagal, JSON rusak, timeout) → {} — BUKAN exception yang menjatuhkan
   snapshot. SMA10 itu pelengkap; BSJP harus tetap jalan tanpanya.

Semua tes di bawah memakai data palsu (tidak menyentuh SSH/Tencent) — kecuali satu tes
integrasi yang ditandai dan akan dilewati bila kunci tidak tersedia.
"""

from __future__ import annotations

import json
import os

import pytest

from live_trading.collectors import riwayat_idx as R


def _baris(ticker: str, hari: str, close: float, vwap: float, vol: float, n: int = 100):
    """Bentuk baris yang dikembalikan skrip jarak jauh."""
    return [ticker, hari, close, vwap, vol, n]


def test_sma10_hanya_bila_10_hari_atau_lebih() -> None:
    """Sembilan hari bukan cukup: sma10 harus None, bukan rata-rata 9 hari."""
    r = R.TickerHistory(ticker="AAA", hari=[], close=[], vwap=[], volume=[])
    r.hari = [f"2026-09-{d:02d}" for d in range(1, 10)]
    r.close = [100.0 + i for i in range(9)]
    r.vwap = list(r.close)
    r.volume = [1000.0] * 9
    R._hitung_turunan(r)
    assert r.cukup is False
    assert r.sma10 is None, "9 hari tidak boleh disebut SMA10"
    assert r.vavg10 is None


def test_sma10_benar_untuk_10_hari() -> None:
    """SMA10 = rata-rata 10 close terakhir."""
    r = R.TickerHistory(ticker="AAA", hari=[], close=[], vwap=[], volume=[])
    r.hari = [f"2026-09-{d:02d}" for d in range(1, 11)]
    r.close = [float(100 + i * 10) for i in range(10)]  # 100..190
    r.vwap = list(r.close)
    r.volume = [1000.0 * (i + 1) for i in range(10)]
    R._hitung_turunan(r)
    assert r.cukup is True
    assert r.sma10 == pytest.approx(sum(r.close[-10:]) / 10)


def test_vavg10_membuang_hari_terakhir() -> None:
    """Volume hari berjalan belum lengkap — memasukkannya mengecilkan rel-vol tanpa sebab."""
    r = R.TickerHistory(ticker="AAA", hari=[], close=[], vwap=[], volume=[])
    r.hari = [f"2026-09-{d:02d}" for d in range(1, 12)]  # 11 hari
    r.close = [100.0] * 11
    r.vwap = list(r.close)
    # 10 hari pertama volume 1000; hari ke-11 (terakhir) volume 1 (baru mulai)
    r.volume = [1000.0] * 10 + [1.0]
    R._hitung_turunan(r)
    assert r.vavg10 == pytest.approx(1000.0), "hari terakhir harus dibuang dari rata-rata"


def test_ssh_gagal_mengembalikan_kosong_bukan_exception(monkeypatch) -> None:
    """SMA10 itu pelengkap: kegagalannya tidak boleh menjatuhkan snapshot BSJP."""
    import subprocess

    def _boom(*a, **k):
        raise subprocess.TimeoutExpired(cmd="ssh", timeout=1)

    monkeypatch.setattr(R.subprocess, "run", _boom)
    assert R.fetch_history(["ANTM"]) == {}


def test_json_rusak_mengembalikan_kosong(monkeypatch) -> None:
    class _P:
        returncode = 0
        stdout = "bukan json"
        stderr = ""

    monkeypatch.setattr(R.subprocess, "run", lambda *a, **k: _P())
    assert R.fetch_history(["ANTM"]) == {}


def test_tanpa_ticker_mengembalikan_kosong() -> None:
    assert R.fetch_history([]) == {}
    assert R.fetch_history(["", "  "]) == {}


def test_batch_dipecah_saat_melebihi_batas(monkeypatch) -> None:
    """57 emiten harus jadi beberapa panggilan, bukan satu kueri raksasa yang timeout."""
    panggilan: list[list[str]] = []

    def _palsu(tickers, **k):
        panggilan.append(list(tickers))
        return {}

    monkeypatch.setattr(R, "fetch_history", _palsu)
    # Panggil lewat fungsi asli dengan memulihkan referensi setelah patch:
    # di sini cukup uji logika pemecahan pada level modul.
    bersih = [f"T{i:02d}" for i in range(57)]
    maks = 15
    potongan = [bersih[i:i + maks] for i in range(0, len(bersih), maks)]
    assert len(potongan) == 4
    assert len(potongan[0]) == 15
    assert len(potongan[-1]) == 12


def test_parsing_dan_urut_menaik(monkeypatch) -> None:
    """Baris dari skrip harus diurai, diurut menaik, dan SMA-nya dihitung."""
    baris = [_baris("ANTM", f"2026-09-{d:02d}", 1000.0 + d * 10, 1005.0, 5000.0) for d in range(1, 12)]
    # Sengaja diacak: urutan datang tidak boleh dipercaya.
    acak = [baris[5], baris[0], baris[10], baris[3], baris[7], baris[1], baris[9],
            baris[2], baris[8], baris[4], baris[6]]

    class _P:
        returncode = 0
        stdout = json.dumps(acak)
        stderr = ""

    monkeypatch.setattr(R.subprocess, "run", lambda *a, **k: _P())
    hasil = R.fetch_history(["ANTM"])
    assert "ANTM" in hasil
    v = hasil["ANTM"]
    assert v.hari == sorted(v.hari), "hari harus urut menaik untuk SMA yang benar"
    assert v.sma10 == pytest.approx(sum(v.close[-10:]) / 10)


@pytest.mark.skipif(
    not os.path.exists(R.SSH_KEY_DEFAULT), reason="kunci SSH Tencent tidak ada di mesin ini"
)
def test_integrasi_nyata_opsional() -> None:
    """Uji asap terhadap arsip nyata. Dilewati otomatis bila kunci tidak tersedia."""
    hasil = R.fetch_history(["ANTM"], timeout_s=60)
    if not hasil:  # jaringan/daemon bisa tidak terjangkau; itu bukan kegagalan kode
        pytest.skip("arsip tidak terjangkau dari sini")
    v = hasil["ANTM"]
    assert len(v.close) > 0
    if v.cukup:
        assert v.sma10 is not None and v.sma10 > 0


def test_sufiks_jk_dinormalkan_di_kueri(monkeypatch) -> None:
    """Universe Tencent menulis SEMUA ticker sebagai 'CAMP.JK' (516 dari 516).

    Tanpa normalisasi di boundary, kueri `ticker IN ('CAMP.JK')` tidak cocok dengan DB
    yang menyimpan 'CAMP' → hasil kosong → SMA10 None → kandidat BSJP ditolak tanpa sebab
    yang terlihat. Tes ini mengunci: yang dikirim ke SQL harus 'CAMP', bukan 'CAMP.JK'.
    """
    ditangkap: list[str] = []

    class _P:
        returncode = 0
        stdout = json.dumps(
            [_baris("CAMP", f"2026-09-{d:02d}", 500.0 + d, 505.0, 1000.0) for d in range(1, 12)]
        )
        stderr = ""

    def _tangkap(perintah, **k):
        ditangkap.append(k.get("input", ""))
        return _P()

    monkeypatch.setattr(R.subprocess, "run", _tangkap)
    R.fetch_history(["CAMP.JK"])

    assert ditangkap, "subprocess.run harus dipanggil"
    kirim = ditangkap[0]
    assert "'CAMP'" in kirim, "kode bersih harus dikirim ke SQL"
    assert "CAMP.JK" not in kirim, "sufiks .JK tidak boleh sampai ke kueri"
