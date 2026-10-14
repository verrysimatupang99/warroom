"""Pengukuran hasil maju — logika pelacakan harus benar sebelum angkanya dipercaya.

Semua pengujian memakai candle buatan yang diberikan langsung, tanpa jaringan: yang diuji
adalah keputusannya (terisi? TP1 atau SL lebih dulu?), bukan koneksinya.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Any

import pytest

from live_trading import measure
from live_trading.config import get_settings

SEKARANG = dt.datetime(2026, 9, 27, 12, 0, tzinfo=dt.UTC)


def _k(o: float, hi: float, lo: float, c: float) -> list[Any]:
    return [0, str(o), str(hi), str(lo), str(c), "1"]


def _row(**kw: Any) -> dict[str, Any]:
    dasar = {
        "ts": (SEKARANG - dt.timedelta(hours=12)).isoformat(),
        "pair": "TESTUSDT",
        "direction": "LONG",
        "allowed": True,
        "tier": "PREMIUM",
        "entry": 100.0,
        "sl": 95.0,
        "tp1": 105.0,
        "rules": [{"rule": "mtf_alignment", "ok": True}, {"rule": "freshness", "ok": True}],
    }
    dasar.update(kw)
    return dasar


def test_long_kena_tp1() -> None:
    klines = [_k(100, 101, 99, 100), _k(100, 106, 100, 105)]

    hasil = measure.resolve_one(_row(), klines, now=SEKARANG)

    assert hasil["hasil"] == "tp1"
    assert hasil["r"] == pytest.approx(1.0)
    assert hasil["jam_ke_hasil"] == 2


def test_long_kena_sl_dulu() -> None:
    klines = [_k(100, 101, 99, 100), _k(100, 100, 94, 95)]

    hasil = measure.resolve_one(_row(), klines, now=SEKARANG)

    assert hasil["hasil"] == "sl"
    assert hasil["r"] == pytest.approx(-1.0)


def test_tp1_dan_sl_di_candle_yang_sama_dihitung_sl() -> None:
    """Pilihan konservatif: kalau tidak tahu mana dulu, jangan menguntungkan diri sendiri."""
    klines = [_k(100, 101, 99, 100), _k(100, 106, 94, 105)]

    hasil = measure.resolve_one(_row(), klines, now=SEKARANG)

    assert hasil["hasil"] == "sl"


def test_tidak_terisi_dalam_8_jam() -> None:
    klines = [_k(110, 112, 108, 111) for _ in range(10)]

    hasil = measure.resolve_one(_row(), klines, now=SEKARANG)

    assert hasil["hasil"] == "tidak_terisi"
    assert hasil["r"] == pytest.approx(0.0)


def test_masih_menunggu_terisi_kalau_belum_8_jam() -> None:
    klines = [_k(110, 112, 108, 111) for _ in range(3)]
    row = _row(ts=(SEKARANG - dt.timedelta(hours=2)).isoformat())

    hasil = measure.resolve_one(row, klines, now=SEKARANG)

    assert hasil["hasil"] == "menunggu_terisi"
    assert hasil["r"] is None


def test_belum_kena_apa_apa_dinilai_mark_bukan_dipaksa_nol() -> None:
    klines = [_k(100, 101, 99, 100), _k(100, 102, 99, 101)]

    hasil = measure.resolve_one(_row(), klines, now=SEKARANG)

    assert hasil["hasil"] == "terbuka"
    assert hasil["r"] == pytest.approx(0.2)  # (101-100)/5


def test_short_dicerminkan() -> None:
    row = _row(direction="SHORT", entry=100.0, sl=105.0, tp1=95.0)
    klines = [_k(100, 101, 99, 100), _k(100, 100, 94, 95)]

    hasil = measure.resolve_one(row, klines, now=SEKARANG)

    assert hasil["hasil"] == "tp1"
    assert hasil["r"] == pytest.approx(1.0)


def test_short_kena_sl() -> None:
    row = _row(direction="SHORT", entry=100.0, sl=105.0, tp1=95.0)
    klines = [_k(100, 101, 99, 100), _k(100, 106, 100, 105)]

    hasil = measure.resolve_one(row, klines, now=SEKARANG)

    assert hasil["hasil"] == "sl"


def test_kedaluwarsa_setelah_24_jam() -> None:
    baris = [_k(100, 101, 99, 100)] + [_k(100, 101.5, 99, 101) for _ in range(24)]
    row = _row(ts=(SEKARANG - dt.timedelta(hours=30)).isoformat())

    hasil = measure.resolve_one(row, baris, now=SEKARANG)

    assert hasil["hasil"] == "kedaluwarsa"
    assert hasil["r"] == pytest.approx(0.2)


def test_report_memisahkan_lolos_dan_bayangan_lalu_menilai_aturan(monkeypatch, tmp_path) -> None:
    """Inti pengukuran: kalau kandidat yang ditolak justru untung, aturan itu merugikan."""
    s = get_settings(home=tmp_path)

    def fake_outcomes(settings, *, client=None, now=None):  # noqa: ANN001, ARG001
        return [
            {"hasil": "tp1", "r": 1.0, "allowed": True, "rules_gagal": [], "pair": "A", "ts": "x"},
            {"hasil": "sl", "r": -1.0, "allowed": True, "rules_gagal": [], "pair": "B", "ts": "x"},
            # ditolak HANYA karena atr_min, dan ternyata menang
            {"hasil": "tp1", "r": 1.0, "allowed": False, "rules_gagal": ["atr_min"], "pair": "C", "ts": "x"},
            # ditolak HANYA karena freshness, dan ternyata kalah
            {
                "hasil": "sl",
                "r": -1.0,
                "allowed": False,
                "rules_gagal": ["freshness"],
                "pair": "D",
                "ts": "x",
            },
            # ditolak dua aturan -> tidak dipakai untuk menilai aturan tunggal
            {
                "hasil": "sl",
                "r": -1.0,
                "allowed": False,
                "rules_gagal": ["atr_min", "freshness"],
                "pair": "E",
                "ts": "x",
            },
        ]

    monkeypatch.setattr(measure, "outcomes_cached", fake_outcomes)
    monkeypatch.setattr(measure, "load_verdicts", lambda s_: [{"ts": str(i)} for i in range(5)])

    laporan = measure.report(s)

    assert laporan["lolos"]["n"] == 2
    assert laporan["lolos"]["expectancy_r"] == pytest.approx(0.0)
    assert laporan["lolos"]["winrate"] == pytest.approx(50.0)

    aturan = laporan["per_aturan"]
    assert aturan["atr_min"]["n"] == 1
    assert aturan["atr_min"]["expectancy_r"] == pytest.approx(1.0)
    # sampel sekecil ini TIDAK boleh menghasilkan kesimpulan: rata-ratanya positif
    # (aturan itu membuang kandidat untung) tetapi n=1 bukan bukti.
    assert aturan["atr_min"]["sampel_cukup"] is False
    assert "belum" in aturan["atr_min"]["putusan"]
    assert aturan["freshness"]["sampel_cukup"] is False
    assert "belum" in aturan["freshness"]["putusan"]


def test_resolve_one_meneruskan_harga_keputusan_dan_atr() -> None:
    """Field tambahan tidak boleh hilang tanpa suara — ini pernah terjadi dan diam-diam
    membuat skenario 'masuk di harga pasar' kehilangan harga entry-nya."""
    row = {
        "ts": "2026-01-01T00:00:00+00:00",
        "pair": "UJIUSDT",
        "direction": "LONG",
        "entry": 100.0,
        "sl": 95.0,
        "tp1": 105.0,
        "harga_keputusan": 102.0,
        "atr_pct": 1.5,
    }
    hasil = measure.resolve_one(row, [_k(102, 106, 101, 105)])

    assert hasil["harga_keputusan"] == 102.0
    assert hasil["atr_pct"] == 1.5


# ------------------------------------------------- skenario masuk di harga pasar
def _baris_pasar(**over: object) -> dict:
    row = {
        "ts": "2026-01-01T00:00:00+00:00",
        "pair": "UJIUSDT",
        "direction": "LONG",
        "entry": 100.0,
        "sl": 95.0,
        "tp1": 105.0,
        "harga_keputusan": 102.0,
    }
    row.update(over)
    return row


def test_masuk_pasar_long_kena_tp1_dengan_r_yang_dihitung_ulang() -> None:
    """Masuk di 102 dengan SL 95 dan TP1 105: risiko 7, imbalan 3 → R bukan lagi 1."""
    klines = [_k(102, 106, 101, 105)]
    hasil = measure.masuk_pasar(_baris_pasar(), klines)

    assert hasil["hasil_pasar"] == "tp1"
    assert hasil["r_pasar"] == pytest.approx(3.0 / 7.0, abs=1e-4)


def test_masuk_pasar_long_kena_sl_dulu() -> None:
    klines = [_k(102, 103, 94, 95)]
    hasil = measure.masuk_pasar(_baris_pasar(), klines)

    assert hasil["hasil_pasar"] == "sl"
    assert hasil["r_pasar"] == -1.0


def test_masuk_pasar_tanpa_harga_keputusan_tidak_dinilai() -> None:
    row = _baris_pasar()
    del row["harga_keputusan"]

    assert measure.masuk_pasar(row, [_k(100, 106, 99, 105)])["hasil_pasar"] == "tanpa_harga_keputusan"


def test_masuk_pasar_yang_sudah_melewati_target_ditolak_bukan_dipaksa() -> None:
    """Harga pasar 106 sudah di atas TP1 105 — imbalannya negatif, jadi tidak sah dinilai."""
    klines = [_k(106, 107, 105, 106)]
    hasil = measure.masuk_pasar(_baris_pasar(harga_keputusan=106.0), klines)

    assert hasil["hasil_pasar"] == "tidak_valid"
    assert hasil["r_pasar"] is None


def test_masuk_pasar_short_kena_tp1() -> None:
    row = _baris_pasar(direction="SHORT", entry=100.0, sl=105.0, tp1=95.0, harga_keputusan=98.0)
    hasil = measure.masuk_pasar(row, [_k(98, 99, 94, 95)])

    assert hasil["hasil_pasar"] == "tp1"
    assert hasil["r_pasar"] == pytest.approx(3.0 / 7.0, abs=1e-4)


def test_masuk_pasar_tanpa_kejadian_dinilai_terbuka() -> None:
    klines = [_k(102, 103, 101, 102), _k(102, 103, 101, 102)]
    hasil = measure.masuk_pasar(_baris_pasar(), klines)

    assert hasil["hasil_pasar"] == "terbuka"
    assert hasil["r_pasar"] == pytest.approx(0.0, abs=1e-6)


def test_kemenangan_target_2r_ikut_dihitung(monkeypatch, tmp_path) -> None:
    """'tp2' wajib masuk daftar hasil terisi.

    Bug nyata: nama hasil 'tp2' tidak pernah didaftarkan, jadi 1.315 trade yang menang +2R
    hilang dari perhitungan dan ringkasan melaporkan rugi -0,635R yang tidak ada
    (angka benarnya +0,025R). Tes ini menjaga daftar itu tetap lengkap.
    """
    from live_trading import backtest

    assert "tp2" in backtest.HASIL_TERISI

    rows = [
        {"r": 2.0, "hasil": "tp2", "entry": 100.0, "sl": 99.0},
        {"r": -1.0, "hasil": "sl", "entry": 100.0, "sl": 99.0},
    ]
    a = backtest.aggregate(rows, fee_per_sisi=0.0)
    assert a["semua"]["terisi"] == 2, "tp2 harus dihitung sebagai posisi terisi"
    assert a["semua"]["expectancy_r"] == pytest.approx(0.5)


def test_hasil_tp2_masuk_akhir_di_measure() -> None:
    from live_trading import measure

    assert "tp2" in measure.FINAL


def test_resolve_tp2_menghitung_target_dua_r() -> None:
    row = {
        "ts": "2026-01-01T00:00:00+00:00",
        "pair": "UJIUSDT",
        "direction": "LONG",
        "entry": 100.0,
        "sl": 95.0,
        "tp1": 105.0,
    }
    # kena 2R (110) setelah terisi di 100
    assert measure.resolve_tp2(row, [_k(100, 111, 99, 110)]) == {"hasil_tp2": "tp2", "r_tp2": 2.0}
    # kena SL lebih dulu
    assert measure.resolve_tp2(row, [_k(100, 101, 94, 95)])["hasil_tp2"] == "sl"
    # tidak pernah terisi
    assert measure.resolve_tp2(row, [_k(101, 103, 101, 102)])["hasil_tp2"] == "tidak_terisi"


def test_resolve_tp2_short() -> None:
    row = {
        "ts": "2026-01-01T00:00:00+00:00",
        "pair": "UJIUSDT",
        "direction": "SHORT",
        "entry": 100.0,
        "sl": 105.0,
        "tp1": 95.0,
    }
    assert measure.resolve_tp2(row, [_k(100, 101, 89, 90)]) == {"hasil_tp2": "tp2", "r_tp2": 2.0}


def test_ekskursi_mfe_dan_mae_dalam_satuan_r() -> None:
    """MFE/MAE dipakai untuk memilih target — harus benar arah dan satuannya."""
    row = {
        "ts": "2026-01-01T00:00:00+00:00",
        "pair": "UJIUSDT",
        "direction": "LONG",
        "entry": 100.0,
        "sl": 95.0,
        "tp1": 105.0,
    }
    # terisi di 100, sempat naik ke 108 (MFE +1.6R), turun ke 97 (MAE -0.6R)
    hasil = measure.ekskursi(row, [_k(100, 101, 99, 100), _k(100, 108, 97, 102)])

    assert hasil["r_mfe"] == pytest.approx(1.6)
    assert hasil["r_mae"] == pytest.approx(-0.6)


def test_ekskursi_short_arah_terbalik() -> None:
    row = {
        "ts": "2026-01-01T00:00:00+00:00",
        "pair": "UJIUSDT",
        "direction": "SHORT",
        "entry": 100.0,
        "sl": 105.0,
        "tp1": 95.0,
    }
    hasil = measure.ekskursi(row, [_k(100, 101, 99, 100), _k(100, 103, 92, 93)])

    assert hasil["r_mfe"] == pytest.approx(1.6), "turun ke 92 = +1.6R untuk short"
    assert hasil["r_mae"] == pytest.approx(-0.6), "naik ke 103 = -0.6R untuk short"


def test_ekskursi_tidak_terisi_tidak_dinilai() -> None:
    row = {
        "ts": "2026-01-01T00:00:00+00:00",
        "pair": "UJIUSDT",
        "direction": "LONG",
        "entry": 100.0,
        "sl": 95.0,
        "tp1": 105.0,
    }
    hasil = measure.ekskursi(row, [_k(101, 103, 101, 102)])

    assert hasil["r_mfe"] is None
    assert hasil["r_mae"] is None


def test_penetrasi_membuat_syarat_terisi_lebih_keras() -> None:
    """Asumsi paling lemah di model ini: limit kita terisi saat harga menyentuh.

    Dengan penetrasi 5 bps, harga harus menembus 99,95 — menyentuh 99,96 tidak cukup.
    """
    row = {
        "ts": "2026-01-01T00:00:00+00:00",
        "pair": "UJIUSDT",
        "direction": "LONG",
        "entry": 100.0,
        "sl": 95.0,
        "tp1": 105.0,
    }
    klines = [_k(100.5, 101.0, 99.96, 100.2)]

    longgar = measure.resolve_one(row, klines)
    ketat = measure.resolve_one(row, klines, isi_penetrasi_bps=5.0)

    assert longgar["hasil"] != "tidak_terisi", "menyentuh 100 sudah terisi"
    assert ketat["hasil"] == "tidak_terisi", "5 bps butuh tembus 99,95"


def test_penetrasi_nol_tidak_mengubah_apa_pun() -> None:
    row = {
        "ts": "2026-01-01T00:00:00+00:00",
        "pair": "UJIUSDT",
        "direction": "LONG",
        "entry": 100.0,
        "sl": 95.0,
        "tp1": 105.0,
    }
    klines = [_k(100, 106, 99, 105)]

    assert measure.resolve_one(row, klines, isi_penetrasi_bps=0.0)["hasil"] == "tp1"


def test_hold_lebih_panjang_menangkap_hasil_yang_hold_pendek_lewatkan() -> None:
    """--hold harus benar-benar berfungsi: dulu di atas 24 jam ia diabaikan diam-diam."""
    row = {
        "ts": "2026-01-01T00:00:00+00:00",
        "pair": "UJIUSDT",
        "direction": "LONG",
        "entry": 100.0,
        "sl": 95.0,
        "tp1": 105.0,
    }
    # terisi di jam 1, TP1 baru kena di jam ke-20 setelah terisi
    klines = [_k(100, 101, 99, 100)] + [_k(100, 101, 99, 100) for _ in range(18)] + [_k(100, 106, 100, 105)]

    pendek = measure.resolve_one(row, klines, hold_max_h=10)
    panjang = measure.resolve_one(row, klines, hold_max_h=24)

    assert pendek["hasil"] != "tp1", "hold pendek belum sempat kena"
    assert panjang["hasil"] == "tp1", "hold panjang harus menangkapnya"


def test_rows_target_2r_mengganti_kolom_hasil() -> None:
    """Skenario 2R memakai kolom r/hasil dari hasil_tp2 — tanpa mengubah baris aslinya."""
    from live_trading import backtest

    rows = [
        {"entry": 100.0, "sl": 95.0, "r": 1.0, "hasil": "tp1", "r_tp2": None},
        {"entry": 100.0, "sl": 95.0, "r": 1.0, "hasil": "tp1", "hasil_tp2": "sl", "r_tp2": -1.0},
    ]
    hasil = backtest.rows_target_2r(rows)

    assert len(hasil) == 1
    assert hasil[0]["hasil"] == "sl"
    assert hasil[0]["r"] == -1.0
    assert rows[1]["hasil"] == "tp1", "baris asli tidak boleh diubah"


def test_putusan_aturan_tidak_dikeluarkan_pada_sampel_kecil(monkeypatch, tmp_path) -> None:
    """n=1 tidak boleh menghasilkan kesimpulan 'berguna'/'merugikan'.

    Ini prinsip yang sudah dipegang di backtest dan harus berlaku juga di pengukuran hidup:
    't besar dari 3 pengamatan bukan bukti'.
    """
    from live_trading import measure

    rows = [
        {"allowed": False, "rules_gagal": ["atr_min"], "r": -1.0, "hasil": "sl"},
        {"allowed": True, "rules_gagal": [], "r": 1.0, "hasil": "tp1"},
    ]
    monkeypatch.setattr(measure, "outcomes_cached", lambda *a, **k: rows)
    monkeypatch.setattr(measure, "load_verdicts", lambda *a, **k: [])
    rep = measure.report(_Pengaturan(tmp_path))
    v = rep["per_aturan"]["atr_min"]
    assert v["n"] == 1
    assert v["sampel_cukup"] is False
    assert "belum" in v["putusan"]


def test_putusan_aturan_dikeluarkan_saat_sampel_cukup(monkeypatch, tmp_path) -> None:
    """n>=20 DAN |t|>=2 → putusan keluar. Di sini 25 kandidat rugi konsisten."""
    from live_trading import measure

    rows = [
        {"allowed": False, "rules_gagal": ["atr_min"], "r": r, "hasil": "sl"}
        for r in ([-1.0] * 20 + [-0.5] * 5)
    ]
    monkeypatch.setattr(measure, "outcomes_cached", lambda *a, **k: rows)
    monkeypatch.setattr(measure, "load_verdicts", lambda *a, **k: [])
    rep = measure.report(_Pengaturan(tmp_path))
    v = rep["per_aturan"]["atr_min"]
    assert v["n"] == 25
    assert v["sampel_cukup"] is True
    assert v["t"] is not None and v["t"] < -2
    assert v["putusan"] == "berguna"


def test_aturan_sampel_cukup_tapi_derau_tidak_diberi_putusan(monkeypatch, tmp_path) -> None:
    """Cukup sampel tapi |t|<2 → jangan disebut 'berguna'/'merugikan'.

    Kasus nyata: aturan 'freshness' mencapai n=21 dengan rata-rata +0,04R. Versi lama
    langsung mencapnya 'merugikan' hanya karena tandanya positif.
    """
    from live_trading import measure

    nilai = [1.0, -1.0] * 10 + [0.5]
    rows = [{"allowed": False, "rules_gagal": ["freshness"], "r": r, "hasil": "tp1"} for r in nilai]
    monkeypatch.setattr(measure, "outcomes_cached", lambda *a, **k: rows)
    monkeypatch.setattr(measure, "load_verdicts", lambda *a, **k: [])
    rep = measure.report(_Pengaturan(tmp_path))
    v = rep["per_aturan"]["freshness"]
    assert v["n"] == 21
    assert v["sampel_cukup"] is True
    assert v["putusan"] == "tidak bisa dibedakan dari derau"


class _Pengaturan:
    """Settings seadanya untuk report() — hanya butuh state_dir."""

    def __init__(self, tmp: object) -> None:
        from pathlib import Path

        self.state_dir = Path(str(tmp))
        self.state_dir.mkdir(parents=True, exist_ok=True)


def test_rows_masuk_pasar_melewati_baris_tanpa_harga() -> None:
    """Baris lama (sebelum harga disimpan) tidak boleh dipaksa masuk skenario ini."""
    rows = [
        {"entry": 100.0, "sl": 95.0, "r": 1.0, "hasil": "tp1"},
        {
            "entry": 100.0,
            "sl": 95.0,
            "r": 1.0,
            "hasil": "tp1",
            "harga_keputusan": 102.0,
            "r_pasar": -1.0,
            "hasil_pasar": "sl",
        },
    ]
    hasil = measure.rows_entering_market(rows)

    assert len(hasil) == 1
    assert hasil[0]["entry"] == 102.0
    assert hasil[0]["r"] == -1.0
    assert hasil[0]["hasil"] == "sl"


# ------------------------------------------------------------------ cache 1H


def test_cache_hasil_final_tidak_diambil_dua_kali(monkeypatch, tmp_path) -> None:
    """Dashboard membangun snapshot tiap 15 menit — hasil final tidak boleh dihitung ulang."""
    s = get_settings(home=tmp_path)
    s.state_dir.mkdir(parents=True, exist_ok=True)
    ts = (dt.datetime.now(dt.UTC) - dt.timedelta(hours=30)).isoformat()
    (s.state_dir / "verdicts.jsonl").write_text(
        json.dumps(
            {
                "ts": ts,
                "pair": "AAUSDT",
                "direction": "LONG",
                "allowed": True,
                "tier": "STANDAR",
                "entry": 100.0,
                "sl": 95.0,
                "tp1": 105.0,
                "rules": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    panggilan = {"n": 0}

    def fake_fetch(settings, pair, start_ms, limit, client):  # noqa: ANN001, ARG001
        panggilan["n"] += 1
        return [[0, "100", "101", "99", "100", "1"], [0, "100", "106", "100", "105", "1"]]

    monkeypatch.setattr(measure, "_fetch_1h", fake_fetch)

    pertama = measure.outcomes_cached(s)
    kedua = measure.outcomes_cached(s)

    assert pertama[0]["hasil"] == "tp1"
    assert panggilan["n"] == 1, "pengambilan kedua harus memakai cache, bukan jaringan"
    assert kedua[0]["r"] == pytest.approx(1.0)


def test_cache_diisi_ulang_kalau_hasil_belum_final(monkeypatch, tmp_path) -> None:
    """Kandidat yang masih terbuka harus terus diikuti, bukan dibekukan."""
    s = get_settings(home=tmp_path)
    s.state_dir.mkdir(parents=True, exist_ok=True)
    ts = (dt.datetime.now(dt.UTC) - dt.timedelta(hours=2)).isoformat()
    (s.state_dir / "verdicts.jsonl").write_text(
        json.dumps(
            {
                "ts": ts,
                "pair": "BBUSDT",
                "direction": "LONG",
                "allowed": True,
                "tier": "STANDAR",
                "entry": 100.0,
                "sl": 95.0,
                "tp1": 105.0,
                "rules": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    panggilan = {"n": 0}

    def fake_fetch(settings, pair, start_ms, limit, client):  # noqa: ANN001, ARG001
        panggilan["n"] += 1
        return [[0, "100", "101", "99", "100", "1"], [0, "100", "102", "99", "101", "1"]]

    monkeypatch.setattr(measure, "_fetch_1h", fake_fetch)

    measure.outcomes_cached(s)
    measure.outcomes_cached(s)

    assert panggilan["n"] == 2, "hasil belum final -> harus dicek lagi"


def test_outcomes_hanya_melacak_yang_sudah_cukup_umur(monkeypatch, tmp_path) -> None:
    s = get_settings(home=tmp_path)
    s.state_dir.mkdir(parents=True, exist_ok=True)
    baru = (dt.datetime.now(dt.UTC) - dt.timedelta(minutes=5)).isoformat()
    (s.state_dir / "verdicts.jsonl").write_text(
        json.dumps(
            {
                "ts": baru,
                "pair": "BARUUSDT",
                "direction": "LONG",
                "allowed": True,
                "tier": "PREMIUM",
                "entry": 1.0,
                "sl": 0.9,
                "tp1": 1.1,
                "rules": [{"rule": "atr_min", "ok": False}],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    assert measure.outcomes(s) == [], "kandidat berumur 5 menit belum boleh dinilai"
