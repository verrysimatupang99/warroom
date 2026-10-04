"""Backtest — dua hal wajib benar sebelum angkanya dipercaya: anti-lookahead dan hitungannya.

Kalau data masa depan bocor ke dalam keputusan, seluruh hasil backtest jadi omong kosong
yang terlihat meyakinkan. Itu jenis kesalahan yang paling mahal di sini, jadi ia diuji
secara eksplisit: jalankan data yang sama dua kali, yang kedua dengan ekor masa depan
ditambahkan — keputusan yang sama harus menghasilkan baris yang identik.
"""

from __future__ import annotations

import random
from typing import Any

import pytest

from live_trading import backtest

JAM_MS = 3_600_000


def _seri(
    n: int = 300, harga0: float = 100.0, amp: float = 8.0, period: int = 14, seed: int = 7
) -> list[list[Any]]:
    """Zigzag deterministik dengan struktur (swing) yang cukup untuk dianalisis."""
    rnd = random.Random(seed)
    out: list[list[Any]] = []
    harga, arah = harga0, 1
    for i in range(n):
        if i % period == 0:
            arah = -arah
        o = harga
        c = o + arah * amp / period * (0.4 + rnd.random())
        h = max(o, c) + abs(rnd.gauss(0, 0.35))
        lo = min(o, c) - abs(rnd.gauss(0, 0.35))
        out.append([i * JAM_MS, str(o), str(h), str(lo), str(c), "10", (i + 1) * JAM_MS - 1])
        harga = c
    return out


def _ekor_liar(n: int, mulai: int, naik: bool = True) -> list[list[Any]]:
    """Ekor masa depan yang kasar — kalau ini bocor ke keputusan, hasilnya langsung beda."""
    out: list[list[Any]] = []
    harga = 100.0
    for i in range(n):
        idx = mulai + i
        o = harga
        c = o * (1.03 if naik else 0.97)
        h = max(o, c) * 1.01
        lo = min(o, c) * 0.99
        out.append([idx * JAM_MS, str(o), str(h), str(lo), str(c), "99", (idx + 1) * JAM_MS - 1])
        harga = c
    return out


# ------------------------------------------------------------------ resample
def test_resample_membuang_candle_yang_belum_penuh() -> None:
    """Candle 4 jam yang baru terisi 2 jam tidak boleh dipakai — itu harga masa depan."""
    raw = _seri(10)  # 10 jam: 2 ember 4 jam penuh + 1 ember isi 2 jam
    hasil = backtest.resample(raw, 4)

    assert len(hasil) == 2, "ember terakhir yang belum penuh harus dibuang"
    assert hasil[0][0] == 0
    assert hasil[1][0] == 4 * JAM_MS


def test_resample_menggabungkan_ohlc_dengan_benar() -> None:
    raw = [
        [0, "10", "12", "9", "11", "1", 1],
        [JAM_MS, "11", "15", "10", "14", "2", 2],
        [2 * JAM_MS, "14", "16", "13", "13", "3", 3],
        [3 * JAM_MS, "13", "14", "8", "9", "4", 4],
    ]
    k = backtest.resample(raw, 4)[0]

    assert float(k[1]) == 10.0, "open = open candle pertama"
    assert float(k[2]) == 16.0, "high = high tertinggi"
    assert float(k[3]) == 8.0, "low = low terendah"
    assert float(k[4]) == 9.0, "close = close candle terakhir"
    assert float(k[5]) == 10.0, "volume dijumlahkan"


# --------------------------------------------------------------- anti-bocor
def _batas_kecil(monkeypatch) -> None:
    """Perkecil batas timeframe supaya pengujian tidak butuh ribuan candle sintetis."""
    from live_trading.signals import engine

    monkeypatch.setattr(engine, "TIMEFRAMES", {"1h": 100, "4h": 25, "1d": 10})


def test_keputusan_tidak_terpengaruh_data_masa_depan(monkeypatch) -> None:
    """Properti paling penting: menambah ekor masa depan tidak boleh mengubah keputusan lama."""
    _batas_kecil(monkeypatch)
    dasar = _seri(700)
    dengan_ekor = dasar + _ekor_liar(150, 700, naik=True)

    a = backtest.run_pair(get_settings_palsu(), "UJIUSDT", dasar, step_h=4, warmup_h=300)
    b = backtest.run_pair(get_settings_palsu(), "UJIUSDT", dengan_ekor, step_h=4, warmup_h=300)

    assert a, "harus ada kandidat supaya pengujian ini ada artinya"
    kunci_a = {(r["ts"], r["direction"]): r for r in a}
    kunci_b = {(r["ts"], r["direction"]): r for r in b}

    irisan = set(kunci_a) & set(kunci_b)
    assert len(irisan) >= len(kunci_a) - 2, "hampir semua keputusan harus tetap ada"

    for k in irisan:
        ra, rb = kunci_a[k], kunci_b[k]
        for field in ("entry", "sl", "tp1", "allowed", "hasil", "r"):
            assert ra[field] == rb[field], f"{field} berubah karena data masa depan: {k}"


def test_jendela_mengikuti_batas_timeframe_hidup(monkeypatch) -> None:
    """Jendela backtest harus diturunkan dari batas hidup, bukan angka sendiri."""
    from live_trading.signals import engine

    monkeypatch.setattr(engine, "TIMEFRAMES", {"1h": 200, "4h": 200, "1d": 120})
    assert backtest.jendela_h1() == 2880, "1d butuh 120*24 = 2880 candle 1H"

    monkeypatch.setattr(engine, "TIMEFRAMES", {"1h": 100, "4h": 50, "1d": 20})
    assert backtest.jendela_h1() == 480, "4h butuh 50*4 = 200; 1d 20*24 = 480"


# ------------------------------------------------------------------ duplikat
def test_duplikat_dalam_jendela_dilewati() -> None:
    import datetime as dt

    riwayat = [{"ts": dt.datetime(2026, 1, 1, tzinfo=dt.UTC), "arah": "long", "zona": (100.0, 110.0)}]

    dekat = dt.datetime(2026, 1, 1, 3, tzinfo=dt.UTC)
    jauh = dt.datetime(2026, 1, 2, 3, tzinfo=dt.UTC)

    assert backtest._duplikat(riwayat, dekat, "long", (102.0, 108.0), 12.0) is True
    assert backtest._duplikat(riwayat, jauh, "long", (102.0, 108.0), 12.0) is False
    assert backtest._duplikat(riwayat, dekat, "short", (102.0, 108.0), 12.0) is False
    assert backtest._duplikat(riwayat, dekat, "long", (200.0, 210.0), 12.0) is False


# --------------------------------------------------------------- penghitungan
def test_aggregate_menghitung_dan_menilai_aturan() -> None:
    rows = [
        # ditolak freshness sendirian, lalu rugi -> aturan berguna
        {"allowed": False, "hasil": "sl", "r": -1.0, "rules_gagal": ["freshness"]},
        {"allowed": False, "hasil": "sl", "r": -1.0, "rules_gagal": ["freshness"]},
        # ditolak sl_distance sendirian, lalu untung -> aturan merugikan
        {"allowed": False, "hasil": "tp1", "r": 2.0, "rules_gagal": ["sl_distance"]},
        # lolos
        {"allowed": True, "hasil": "tp1", "r": 2.0, "rules_gagal": []},
        {"allowed": True, "hasil": "tidak_terisi", "r": 0.0, "rules_gagal": []},
        # belum bisa dinilai
        {"allowed": True, "hasil": "menunggu_terisi", "r": None, "rules_gagal": []},
    ]
    a = backtest.aggregate(rows)

    assert a["n_kandidat"] == 6
    assert a["n_dinilai"] == 5, "yang menunggu terisi tidak dihitung"
    assert a["n_terisi"] == 4
    assert a["fill_rate_pct"] == 80.0
    assert a["lolos"]["n"] == 2
    assert a["lolos"]["expectancy_r"] == 1.0, "(2.0 + 0.0) / 2"
    assert a["ditolak"]["n"] == 3
    assert a["per_aturan"]["freshness"]["putusan"] == "berguna"
    assert a["per_aturan"]["sl_distance"]["putusan"] == "merugikan"


def test_aggregate_per_aturan_hanya_yang_menolak_sendirian() -> None:
    """Kandidat yang gagal dua aturan tidak bisa dipakai menilai salah satu aturannya."""
    rows = [
        {"allowed": False, "hasil": "sl", "r": -1.0, "rules_gagal": ["freshness", "atr_min"]},
    ]
    a = backtest.aggregate(rows)

    assert a["per_aturan"] == {}, "gagal dua aturan -> tidak masuk penilaian per aturan"


def test_keyakinan_butuh_t_besar_dan_sampel_cukup() -> None:
    """t besar dari 3 pengamatan bukan bukti — dua syarat harus terpenuhi."""
    tiga = [{"allowed": True, "hasil": "tp1", "r": v, "rules_gagal": []} for v in (2.0, 2.1, 2.2)]
    b3 = backtest.aggregate(tiga)["lolos"]
    assert b3["t_stat"] is not None and b3["t_stat"] > 2
    assert b3["keyakinan"] == "lemah", "n=3 tidak boleh disebut kuat"

    banyak = [
        {"allowed": True, "hasil": "tp1", "r": 1.0 if i % 5 else -1.0, "rules_gagal": []} for i in range(30)
    ]
    b30 = backtest.aggregate(banyak)["lolos"]
    assert b30["t_stat"] is not None and b30["t_stat"] > 2
    assert b30["keyakinan"] == "kuat"


def test_biaya_dihitung_dalam_satuan_r() -> None:
    """SL 1% dari harga + fee 0,05%/sisi = 0,10R biaya. Bukan detail kecil."""
    rows = [{"allowed": True, "hasil": "tp1", "r": 2.0, "rules_gagal": [], "entry": 100.0, "sl": 99.0}]
    b = backtest.aggregate(rows, fee_per_sisi=0.0005)["lolos"]

    assert b["biaya_rata_r"] == pytest.approx(0.1), "(2 x 0.0005 x 100) / 1"
    assert b["expectancy_bersih_r"] == pytest.approx(1.9), "2.0R kotor - 0.1R biaya"


def test_aturan_dinilai_setelah_biaya_bukan_sebelum() -> None:
    """Aturan yang 'merugikan' tipis bisa berubah jadi berguna setelah biaya — dan sebaliknya."""
    # kandidat ditolak aturan X: kotor +0.10R, tapi biaya 0.20R -> bersih -0.10R (berguna)
    rows = [{"allowed": False, "hasil": "tp1", "r": 1.1, "rules_gagal": ["x"], "entry": 200.0, "sl": 199.0}]
    b = backtest.aggregate(rows, fee_per_sisi=0.0005)["per_aturan"]["x"]

    assert b["expectancy_terisi_r"] == pytest.approx(1.1)
    assert b["expectancy_bersih_r"] == pytest.approx(0.9), "biaya 2x0.0005x200/1 = 0.2R"
    assert b["putusan"] == "merugikan"


def test_uji_beda_membedakan_kelompok() -> None:
    """Yang kita punya bukan 'apakah rata-ratanya > 0', tapi 'apakah dua kelompok berbeda'."""
    sama = backtest.uji_beda([1.0, -1.0] * 50, [1.0, -1.0] * 50)
    assert sama["beda_r"] == 0.0
    assert sama["keterangan"] == "tidak bisa dibedakan dari derau"

    beda = backtest.uji_beda([1.0, 1.1, 0.9] * 20, [-1.0, -1.1, -0.9] * 20)
    assert beda["beda_r"] == 2.0
    assert beda["t"] is not None and beda["t"] > 2
    assert beda["keterangan"] == "beda nyata"


def test_uji_beda_ragam_nol_tidak_meledak() -> None:
    sama = backtest.uji_beda([1.0, 1.0, 1.0], [1.0, 1.0, 1.0])
    assert sama["keterangan"] == "ragam nol"


def test_uji_klaster_menghitung_per_pair_bukan_per_kandidat() -> None:
    """Satu pair = satu unit. Ribuan kandidat dari 3 pair bukan ribuan bukti."""
    rows = []
    for pair, nilai in (("A", 1.0), ("B", -1.0), ("C", 0.5)):
        for _ in range(50):
            rows.append(
                {
                    "pair": pair,
                    "allowed": True,
                    "hasil": "tp1",
                    "r": nilai,
                    "entry": 100.0,
                    "sl": 99.0,
                    "rules_gagal": [],
                }
            )
            rows.append(
                {
                    "pair": pair,
                    "allowed": False,
                    "hasil": "sl",
                    "r": -1.0,
                    "entry": 100.0,
                    "sl": 99.0,
                    "rules_gagal": ["x"],
                }
            )

    hasil = backtest.uji_klaster(rows, fee_per_sisi=0.0)

    assert hasil["n_pair"] == 3, "tiga pair, bukan seratus kandidat"
    # selisih per pair: (1.0 - -1.0)=2.0 ; (-1.0 - -1.0)=0.0 ; (0.5 - -1.0)=1.5
    assert hasil["beda_r"] == pytest.approx(1.1667, abs=1e-3)


def test_uji_klaster_pair_terlalu_sedikit_tidak_mengklaim() -> None:
    rows = [{"pair": "A", "allowed": True, "hasil": "tp1", "r": 1.0, "entry": 100.0, "sl": 99.0}]
    assert backtest.uji_klaster(rows)["keterangan"] == "pair terlalu sedikit"


def get_settings_palsu():
    from live_trading.config import get_settings

    return get_settings()
