"""Status daur hidup setup per strategi — dari baris verdict + candle 1H.

Yang dikunci:
1. Walk per candle menghormati urutan fill -> hasil; SL menang bila satu candle
   menyentuh keduanya (konservatif, sama dengan measure).
2. Jendela tunggu 8 jam -> EXPIRED; batas tahan 24 jam setelah terisi -> EXPIRED.
3. Hasil definitif measure menang atas status harga; tanpa bahan -> status None + alasan.
4. Ringkasan TERPISAH per strategi: sebaran status + setup terakhir masing-masing.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from live_trading.signals import lifecycle as lc

TS = dt.datetime(2026, 10, 10, 0, 0, tzinfo=dt.UTC)
BASE_MS = int(TS.timestamp() * 1000)
JAM_MS = 3_600_000


def _k(jam: float, *, low: float, high: float, close: float) -> list[Any]:
    t = BASE_MS + int(jam * JAM_MS)
    return [t, str(close), str(high), str(low), str(close), "10", t + JAM_MS, "0", 0, "5", "0", "0"]


def _row(**kw: Any) -> dict[str, Any]:
    dasar: dict[str, Any] = {
        "ts": TS.isoformat(),
        "pair": "TESTUSDT",
        "direction": "LONG",
        "entry": 100.0,
        "sl": 97.0,
        "tp1": 103.0,
        "poi_low": 99.0,
        "poi_high": 101.0,
        "strategy": "legacy-smc",
    }
    dasar.update(kw)
    return dasar


def _sekarang(jam: float) -> dt.datetime:
    return TS + dt.timedelta(hours=jam)


def test_waiting_saat_harga_jauh_dari_zona() -> None:
    klines = [_k(h, low=102.0, high=105.0, close=104.0) for h in range(3)]
    st = lc.status_live(_row(), klines, sekarang=_sekarang(3))
    assert st is not None
    assert st.status == "WAITING"
    assert st.di_zona is False and st.terisi is False


def test_in_area_saat_sentuh_zona_belum_terisi() -> None:
    klines = [_k(0, low=100.5, high=102.0, close=101.0), _k(1, low=100.6, high=101.5, close=101.2)]
    st = lc.status_live(_row(), klines, sekarang=_sekarang(2))
    assert st is not None
    assert st.status == "IN_AREA"
    assert st.di_zona is True and st.terisi is False


def test_running_saat_terisi_belum_ada_hasil() -> None:
    klines = [_k(0, low=99.5, high=102.0, close=101.0), _k(1, low=99.6, high=101.8, close=101.2)]
    st = lc.status_live(_row(), klines, sekarang=_sekarang(2))
    assert st is not None
    assert st.status == "RUNNING"
    assert "terisi" in st.alasan


def test_tp_dan_sl_menghormati_urutan_candle() -> None:
    tp = lc.status_live(_row(), [_k(0, low=99.5, high=103.5, close=103.0)], sekarang=_sekarang(1))
    assert tp is not None and tp.status == "TP"
    sl = lc.status_live(_row(), [_k(0, low=96.0, high=101.0, close=98.0)], sekarang=_sekarang(1))
    assert sl is not None and sl.status == "SL"


def test_satu_candle_sentuh_sl_dan_tp_dihitung_sl() -> None:
    """Konservatif: hasil tidak boleh dibaguskan oleh asumsi urutan yang menguntungkan."""
    klines = [_k(0, low=96.0, high=104.0, close=103.0)]
    st = lc.status_live(_row(), klines, sekarang=_sekarang(1))
    assert st is not None and st.status == "SL"


def test_jendela_tunggu_habis_jadi_expired() -> None:
    klines = [_k(h, low=102.0, high=105.0, close=104.0) for h in range(10)]
    st = lc.status_live(_row(), klines, sekarang=_sekarang(10))
    assert st is not None
    assert st.status == "EXPIRED"
    assert "8 jam" in st.alasan


def test_belum_terisi_tapi_jendela_belum_habis_tetap_waiting() -> None:
    klines = [_k(h, low=102.0, high=105.0, close=104.0) for h in range(7)]
    st = lc.status_live(_row(), klines, sekarang=_sekarang(7.5))
    assert st is not None and st.status == "WAITING"


def test_batas_tahan_24_jam_setelah_terisi() -> None:
    klines = [_k(0, low=99.5, high=101.0, close=100.5)]
    klines += [_k(h, low=99.6, high=102.0, close=101.5) for h in range(1, 26)]
    st = lc.status_live(_row(), klines, sekarang=_sekarang(30))
    assert st is not None
    assert st.status == "EXPIRED"
    assert "batas tahan" in st.alasan


def test_level_tidak_lengkap_mengembalikan_none() -> None:
    row = _row()
    del row["sl"]
    assert lc.status_live(row, [_k(0, low=99.0, high=101.0, close=100.0)]) is None
    assert lc.status_live(_row(), []) is None


def _outcome_status(hasil: str) -> str:
    st = lc.status_dari_outcome({"hasil": hasil})
    assert st is not None
    return st.status


def test_status_dari_outcome_measure() -> None:
    assert _outcome_status("tp1") == "TP"
    assert _outcome_status("sl") == "SL"
    assert _outcome_status("terbuka") == "RUNNING"
    assert _outcome_status("tidak_terisi") == "EXPIRED"
    assert _outcome_status("kedaluwarsa") == "EXPIRED"
    # hasil yang belum definitif / tidak bisa dinilai -> None (bukan status karangan)
    assert lc.status_dari_outcome({"hasil": "menunggu_terisi"}) is None
    assert lc.status_dari_outcome({"hasil": "gagal_ambil_data"}) is None
    assert lc.status_dari_outcome(None) is None


def test_nilai_baris_prioritas_measure_lalu_harga() -> None:
    klines = [_k(0, low=99.5, high=102.0, close=101.0)]
    akhir = lc.nilai_baris(_row(), klines=klines, outcome={"hasil": "tp1"}, sekarang=_sekarang(1))
    assert akhir["status"] == "TP" and akhir["sumber"] == "measure"

    live = lc.nilai_baris(_row(), klines=klines, sekarang=_sekarang(1))
    assert live["status"] == "RUNNING" and live["sumber"] == "harga"

    kosong = lc.nilai_baris(_row())
    assert kosong["status"] is None
    assert kosong["sumber"] is None
    assert "tidak ada bahan" in kosong["alasan"]


def test_ringkas_terpisah_per_strategi() -> None:
    daftar = [
        lc.nilai_baris(_row(ts="2026-10-10T00:00:00+00:00"), outcome={"hasil": "tp1"}),
        lc.nilai_baris(_row(ts="2026-10-10T02:00:00+00:00"), outcome={"hasil": "sl"}),
        lc.nilai_baris(
            _row(ts="2026-10-10T04:00:00+00:00", strategy="smc-fibonacci-smart-golden-pullback-v1"),
            klines=[_k(0, low=99.5, high=102.0, close=101.0)],
            sekarang=_sekarang(5),
        ),
    ]
    ringkas = lc.ringkas_per_strategi(daftar)
    assert set(ringkas) == {"legacy-smc", "smc-fibonacci-smart-golden-pullback-v1"}

    legacy = ringkas["legacy-smc"]
    assert legacy["jumlah"] == 2
    assert legacy["sebaran"] == {"TP": 1, "SL": 1}
    assert legacy["terakhir"]["ts"] == "2026-10-10T02:00:00+00:00", "harus baris terbaru strategi itu"
    assert legacy["terakhir"]["status"] == "SL"

    golden = ringkas["smc-fibonacci-smart-golden-pullback-v1"]
    assert golden["sebaran"] == {"RUNNING": 1}, "status digabung lintas strategi = tujuan tidak tercapai"


def test_ringkas_menghitung_baris_tanpa_status_terpisah() -> None:
    ringkas = lc.ringkas_per_strategi([lc.nilai_baris(_row())])
    slot = ringkas["legacy-smc"]
    assert slot["jumlah"] == 1
    assert slot["berstatus"] == 0
    assert slot["tanpa_status"] == 1
    assert slot["sebaran"] == {}
    assert slot["terakhir"]["status"] is None


def test_strategi_baris_default_untuk_baris_lama() -> None:
    assert lc.strategi_baris({}) == "legacy-smc"
    assert lc.strategi_baris({"strategy": "x"}) == "x"
