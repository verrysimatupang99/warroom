"""Kontrak siklus hidup setup (Waiting -> In Area -> Running -> TP/SL).

Yang dikunci:
1. Status diturunkan dari level & rentang harga — bukan tebakan; tanpa level valid = None.
2. Urutan mengikat: tidak boleh mundur, tidak boleh melompati IN_AREA menuju RUNNING.
3. SL menang atas TP bila keduanya tersentuh di jendela yang sama (konservatif).
4. Status akhir tidak dinilai ulang.
"""

from __future__ import annotations

import pytest
from warroom_core.strategy_lifecycle import (
    LABEL_STATUS,
    STATUS_AKHIR,
    STATUS_SETUP,
    SetupStatus,
    status_dari,
    status_dari_harga,
    transisi_diizinkan,
)


def _status(
    harga: float,
    *,
    min_: float | None = None,
    max_: float | None = None,
    arah: str = "long",
    entry: float = 99.5,
    sl: float = 97.0,
    tp1: float = 103.0,
    zona_low: float = 99.0,
    zona_high: float = 101.0,
    dimulai_dari: str = "WAITING",
    isi_penetrasi_bps: float = 0.0,
) -> SetupStatus:
    hasil = status_dari_harga(
        arah=arah,
        entry=entry,
        sl=sl,
        tp1=tp1,
        harga=harga,
        harga_min=min_,
        harga_max=max_,
        zona_low=zona_low,
        zona_high=zona_high,
        dimulai_dari=dimulai_dari,
        isi_penetrasi_bps=isi_penetrasi_bps,
    )
    assert hasil is not None
    return hasil


def test_enam_status_lengkap_dengan_label() -> None:
    assert STATUS_SETUP == ("WAITING", "IN_AREA", "RUNNING", "TP", "SL", "EXPIRED")
    assert STATUS_AKHIR == {"TP", "SL", "EXPIRED"}
    assert set(LABEL_STATUS) == set(STATUS_SETUP)


def test_waiting_saat_harga_belum_sentuh_zona() -> None:
    s = _status(102.5)
    assert s.status == "WAITING"
    assert s.di_zona is False and s.terisi is False
    assert "zona" in s.alasan


def test_in_area_saat_sentuh_zona_tapi_belum_terisi() -> None:
    """Zona 99–101, entry 99.5: harga turun ke 100.5 = masuk area, belum terisi."""
    s = _status(102.0, min_=100.5, max_=102.5)
    assert s.status == "IN_AREA"
    assert s.di_zona is True and s.terisi is False


def test_running_saat_terisi_belum_kena_level_hasil() -> None:
    s = _status(101.0, min_=99.4, max_=102.0)
    assert s.status == "RUNNING"
    assert s.terisi is True


def test_tp_dan_sl_dari_rentang_harga() -> None:
    assert _status(103.5, min_=99.4, max_=103.5).status == "TP"
    sl = _status(98.0, min_=96.9, max_=102.0)
    assert sl.status == "SL"
    assert sl.terisi is True


def test_both_tersentuh_dihitung_sl_konservatif() -> None:
    """SL dan TP kena di jendela yang sama: SL yang dipakai — angka tidak dibaguskan."""
    s = _status(103.0, min_=96.9, max_=103.5)
    assert s.status == "SL"
    assert "konservatif" in s.alasan


def test_target_tanpa_terisi_tidak_bisa_menang() -> None:
    """Harga lari ke TP tanpa pernah masuk entry: tetap menunggu, bukan TP."""
    s = _status(104.0, min_=102.0, max_=104.5)
    assert s.status == "WAITING"


def test_short_simetris() -> None:
    def s(harga: float, *, min_: float | None = None, max_: float | None = None) -> SetupStatus:
        return _status(harga, min_=min_, max_=max_, arah="short", entry=100.5, sl=103.0, tp1=97.0)

    assert s(98.0, min_=96.5, max_=98.8).status == "WAITING"
    assert s(99.5, min_=98.8, max_=99.9).status == "IN_AREA"
    assert s(99.0, min_=98.0, max_=101.2).status == "RUNNING"
    assert s(96.5, min_=96.5, max_=101.2).status == "TP"
    assert s(103.5, min_=98.0, max_=103.5).status == "SL"


def test_isi_penetrasi_bps_menulang_syarat_terisi() -> None:
    """Sentuh entry (99,2 ≤ entry 99,5) belum tentu terisi: syarat menembus 50 bps
    menggeser level isi ke 99,003 — di bawah itu baru dianggap terisi."""
    tanpa = _status(100.0, min_=99.2, max_=101.0)
    assert tanpa.status == "RUNNING"
    dengan = _status(100.0, min_=99.2, max_=101.0, isi_penetrasi_bps=50.0)
    assert dengan.status == "IN_AREA"
    dalam = _status(100.0, min_=98.9, max_=101.0, isi_penetrasi_bps=50.0)
    assert dalam.status == "RUNNING"


def test_level_tidak_valid_mengembalikan_none() -> None:
    assert status_dari_harga(arah="long", entry=0.0, sl=97.0, tp1=103.0, harga=100.0) is None
    assert status_dari_harga(arah="long", entry=99.5, sl=97.0, tp1=103.0, harga=0.0) is None


def test_status_akhir_tidak_dinilai_ulang() -> None:
    s = _status(102.0, min_=96.0, max_=104.0, dimulai_dari="SL")
    assert s.status == "SL"
    assert "tidak dinilai ulang" in s.alasan


def test_kemunduran_status_ditahan() -> None:
    """Setup yang sudah RUNNING tidak boleh kembali WAITING hanya karena jendela menyempit."""
    s = _status(105.0, dimulai_dari="RUNNING")
    assert s.status == "RUNNING"
    assert "dipertahankan" in s.alasan


def test_transisi_diizinkan_mengikuti_urutan() -> None:
    assert transisi_diizinkan("WAITING", "IN_AREA") is True
    assert transisi_diizinkan("WAITING", "RUNNING") is True
    assert transisi_diizinkan("IN_AREA", "RUNNING") is True
    assert transisi_diizinkan("IN_AREA", "EXPIRED") is True
    assert transisi_diizinkan("RUNNING", "TP") is True
    assert transisi_diizinkan("RUNNING", "SL") is True
    assert transisi_diizinkan("RUNNING", "EXPIRED") is True
    assert transisi_diizinkan("WAITING", "WAITING") is True
    assert transisi_diizinkan("TP", "TP") is True
    assert transisi_diizinkan("RUNNING", "WAITING") is False
    assert transisi_diizinkan("RUNNING", "IN_AREA") is False
    assert transisi_diizinkan("TP", "RUNNING") is False
    assert transisi_diizinkan("EXPIRED", "IN_AREA") is False
    assert transisi_diizinkan("WAITING", "TP") is False, "TP tanpa terisi = melompat"
    assert transisi_diizinkan("IN_AREA", "SL") is False, "SL hanya setelah terisi penuh"


def test_transisi_nama_tidak_dikenal_ditolak() -> None:
    with pytest.raises(ValueError):
        transisi_diizinkan("WAITING", "DONE")
    with pytest.raises(ValueError):
        transisi_diizinkan("HIDUP", "RUNNING")


def test_status_dari_menahan_transisi_tidak_sah() -> None:
    hasil = status_dari(lama="RUNNING", baru="WAITING", alasan="uji")
    assert hasil.status == "RUNNING"
    sah = status_dari(lama="WAITING", baru="EXPIRED", alasan="jendela tunggu habis")
    assert sah.status == "EXPIRED"
    assert sah.alasan == "jendela tunggu habis"


def test_status_tanpa_alasan_ditolak() -> None:
    with pytest.raises(ValueError):
        SetupStatus(status="WAITING", alasan="   ")
    with pytest.raises(ValueError):
        SetupStatus(status="SELESAI", alasan="kata yang tidak ada di kontrak")


def test_to_dict_membawa_label_dan_alasan() -> None:
    d = _status(102.5).to_dict()
    assert d["status"] == "WAITING"
    assert d["label"] == LABEL_STATUS["WAITING"]
    assert d["alasan"]
