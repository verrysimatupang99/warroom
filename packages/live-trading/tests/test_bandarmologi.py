"""Tes bandarmologi — replikasi parameter broker-flow dari data Arjum. Tanpa jaringan.

Prinsip yang diuji:
  - ukuran dihitung dari field Arjum apa adanya (tidak menebak);
  - parameter yang TIDAK bisa direplikasi (bid/offer, non-reguler) dinyatakan, bukan dipalsukan;
  - skor disebut heuristik dan komponennya transparan;
  - skrining menghormati kuota (batas ticker) dan cache harian.
"""

from __future__ import annotations

from pathlib import Path

from live_trading.collectors.bandarmologi import (
    CATATAN_REPLIKASI,
    LABEL_JUJUR,
    ringkas_broker,
    skor_heuristik,
    skrining,
)


def _payload(brokers: list[dict], kode: str = "TEST") -> dict:
    return {
        "stock_code": kode,
        "broker_end_date": "2026-10-02",
        "brokers": brokers,
        "flow": {},
        "broker_levels": [],
    }


def _b(kode: str, bval=0, sval=0, bfrq=0, sfrq=0, nval=0) -> dict:
    return {
        "broker_code": kode, "broker_name": f"BROKER {kode}",
        "bval": bval, "sval": sval, "bfrq": bfrq, "sfrq": sfrq, "nval": nval,
    }


def test_ats_dihitung_dari_nilai_dibagi_frekuensi() -> None:
    """ATS = rata-rata nilai per transaksi — inti parameter 'High ATS'."""
    p = _payload([_b("AA", bval=100_000_000, bfrq=100, sval=50_000_000, sfrq=200, nval=50_000_000)])
    r = ringkas_broker(p)
    assert r["status"] == "ok"
    assert r["ats_beli"] == 1_000_000.0  # 100jt / 100 transaksi
    assert r["ats_jual"] == 250_000.0    # 50jt / 200 transaksi


def test_avg_trade_size_tidak_dibagi_nol() -> None:
    r = ringkas_broker(_payload([_b("AA", bval=1000, bfrq=0)]))
    assert r["ats_beli"] is None
    assert r["porsi_frq_beli"] is None


def test_porsi_frekuensi_beli() -> None:
    p = _payload([_b("AA", bfrq=300, sfrq=100), _b("BB", bfrq=100, sfrq=100)])
    r = ringkas_broker(p)
    assert r["frq_beli"] == 400 and r["frq_jual"] == 200
    assert r["porsi_frq_beli"] == 0.6667


def test_no_sell_terdeteksi_saat_frekuensi_jual_sangat_kecil() -> None:
    """Akumulator besar dengan hampir tidak ada transaksi jual = gejala 'No Sell'."""
    p = _payload([
        _b("AK", bval=500_000_000, bfrq=500, sval=1_000_000, sfrq=2, nval=499_000_000),
        _b("CC", bval=1_000, bfrq=1, sval=400_000_000, sfrq=400, nval=-399_999_000),
    ])
    r = ringkas_broker(p)
    assert r["no_sell"] is True
    assert r["pembeli_teratas"]["broker"] == "AK"
    assert r["penjual_teratas"]["broker"] == "CC"


def test_no_sell_false_saat_jual_ramai() -> None:
    p = _payload([
        _b("AK", bval=100, bfrq=100, sval=90, sfrq=90, nval=10),
        _b("CC", bval=10, bfrq=10, sval=20, sfrq=20, nval=-10),
    ])
    assert ringkas_broker(p)["no_sell"] is False


def test_net_nilai_agregat() -> None:
    p = _payload([_b("AA", nval=1_000), _b("BB", nval=-400), _b("CC", nval=150)])
    r = ringkas_broker(p)
    assert r["net_nilai"] == 750.0
    assert r["net_juta"] == 0.0  # 750 rupiah -> 0,0 juta


def test_broker_rusak_dilewati_bukan_bikin_gagal() -> None:
    """Broker dengan nilai rusak dilewati — termasuk frekuensinya, supaya rasio tetap koheren.

    Kalau frekuensi broker rusak tetap dijumlahkan sementara nilainya tidak, penyebut ATS
    membengkak dan hasilnya terlalu rendah tanpa error apa pun.
    """
    p = _payload([_b("AA", bval="bukan angka", bfrq=10), _b("BB", bval=100, bfrq=10)])
    r = ringkas_broker(p)
    assert r["status"] == "ok"
    assert r["ats_beli"] == 10.0  # 100 / 10 — hanya pasangan BB yang koheren
    assert r["frq_beli"] == 20.0  # tampilan total tetap apa adanya


def test_payload_kosong_tidak_menebak() -> None:
    assert ringkas_broker({})["status"] == "belum-cukup-data"
    assert ringkas_broker({"brokers": []})["status"] == "belum-cukup-data"


def test_skor_komponen_transparan() -> None:
    """Skor 0..100; keempat komponen menyala sekaligus dengan bobot yang bisa dilacak."""
    kuat = _payload([
        # AK: akumulator besar, tidak pernah jual -> No Sell
        _b("AK", bval=5_000, bfrq=50, sval=0, sfrq=0, nval=5_000),
        # CC: sisi jual kecil nilainya dan jarang -> ATS beli > ATS jual, frekuensi beli dominan
        _b("CC", bval=5_000, bfrq=100, sval=500, sfrq=100, nval=100),
    ])
    r = ringkas_broker(kuat)
    assert r["ats_beli"] == 66.7           # 10.000 / 150  -> (+20)
    assert r["ats_jual"] == 5.0            # 500 / 100
    assert r["porsi_frq_beli"] == 0.6      # 150 / 250     -> (+40)
    assert r["net_nilai"] == 5_100.0       # (+)           -> (+30)
    assert r["no_sell"] is True            # AK: sfrq 0    -> (+10)
    assert r["pembeli_teratas"]["broker"] == "AK"
    # 0,6*40 + 30 + 20 + 10 = 84
    assert skor_heuristik(r) == 84.0


def test_skor_nol_untuk_data_kurang() -> None:
    assert skor_heuristik({"status": "belum-cukup-data"}) == 0.0


def test_setiap_keluaran_membawa_label_jujur() -> None:
    """Ini aturan utamanya: replikasi cara ukur tidak boleh tampak seperti jaminan untung."""
    out = skrining(["AAAA"], Path("/tmp/tidak-dipakai"), ambil=lambda k: _payload([_b("AA", bfrq=1, sfrq=1)]))
    assert LABEL_JUJUR in out["catatan"]
    assert any("bid/offer" in c.lower() for c in out["catatan"])
    assert CATATAN_REPLIKASI[0] in out["catatan"]


def test_skrining_mengurutkan_berdasarkan_skor(tmp_path: Path) -> None:
    payloads = {
        "KUAT": _payload([
            _b("AK", bval=900, bfrq=450, sval=5, sfrq=2, nval=500),
            _b("CC", bval=5, bfrq=5, sval=900, sfrq=200, nval=-500),
        ], "KUAT"),
        "LEMAH": _payload([
            _b("DD", bval=10, bfrq=100, sval=900, sfrq=100, nval=-100),
            _b("EE", bval=1, bfrq=1, sval=50, sfrq=50, nval=-10),
        ], "LEMAH"),
    }
    out = skrining(["LEMAH", "KUAT"], tmp_path, ambil=lambda k: payloads[k])
    assert [r["kode"] for r in out["hasil"]] == ["KUAT", "LEMAH"]
    assert out["hasil"][0]["skor_heuristik"] > out["hasil"][1]["skor_heuristik"]


def test_skrining_menghormati_batas_kuota_ticker(tmp_path: Path) -> None:
    """Kuota Arjum 6000/hari untuk SELURUH pemakaian — batas ticker harus keras."""
    dipanggil: list[str] = []

    def ambil(k: str) -> dict:
        dipanggil.append(k)
        return _payload([_b("AA", bfrq=1, sfrq=1)], k)

    out = skrining([f"K{i}" for i in range(20)], tmp_path, maks_ticker=3, ambil=ambil)
    assert len(dipanggil) == 3
    assert out["maks_ticker"] == 3
    assert out["diperiksa"] == ["K0", "K1", "K2"]


def test_skrining_memakai_cache_pada_hari_yang_sama(tmp_path: Path) -> None:
    n = {"kali": 0}

    def ambil(k: str) -> dict:
        n["kali"] += 1
        return _payload([_b("AA", bfrq=1, sfrq=1)], k)

    skrining(["AAAA"], tmp_path, ambil=ambil)
    skrining(["AAAA"], tmp_path, ambil=ambil)
    assert n["kali"] == 1  # panggilan kedua dari cache, kuota tidak terbakar


def test_skrining_mendedup_kode_kembar(tmp_path: Path) -> None:
    dipanggil: list[str] = []

    def ambil(k: str) -> dict:
        dipanggil.append(k)
        return _payload([_b("AA", bfrq=1, sfrq=1)], k)

    skrining(["AAAA", "AAAA", "BBBB"], tmp_path, ambil=ambil)
    assert dipanggil == ["AAAA", "BBBB"]


def test_skrining_mencatat_kode_yang_gagal(tmp_path: Path) -> None:
    def ambil(k: str) -> dict:
        if k == "RUSAK":
            raise RuntimeError("kuota habis")
        return _payload([_b("AA", bfrq=1, sfrq=1)], k)

    out = skrining(["RUSAK", "OK"], tmp_path, ambil=ambil)
    assert out["jumlah"] == 1
    assert any("RUSAK" in g for g in out["galat"])


def test_skrining_wajib_fungsi_ambil(tmp_path: Path) -> None:
    import pytest

    with pytest.raises(ValueError):
        skrining(["AAAA"], tmp_path)


# --- #1: uji apakah broker-flow berguna, ke riwayat -------------------------------------

def _acc(tanggal: list[str], nval_per_broker: dict[str, list[float]]) -> dict:
    """Bentuk payload broker_accumulation seperti Arjum."""
    return {
        "code": "TEST",
        "start_date": tanggal[0],
        "end_date": tanggal[-1],
        "series": [
            {
                "broker_code": bk,
                "broker_name": f"BROKER {bk}",
                "points": [{"date": t, "nval": v} for t, v in zip(tanggal, nval, strict=True)],
            }
            for bk, nval in nval_per_broker.items()
        ],
    }


def _hist(tanggal: list[str], tutup: list[float]) -> dict:
    return {"stock_code": "TEST", "frame": "daily",
            "rows": [{"date": t, "close": c} for t, c in zip(tanggal, tutup, strict=True)]}


def _hari(n: int) -> list[str]:
    return [f"2026-01-{i+1:02d}" for i in range(n)]


def test_seri_broker_menjumlahkan_lintas_broker() -> None:
    from live_trading.collectors.bandarmologi import seri_broker

    t = _hari(5)
    s = seri_broker(_acc(t, {"AA": [10, -5, 20, 0, 7], "BB": [5, 3, -2, 0, -1]}))
    assert len(s) == 5
    assert s[0]["net_total"] == 15.0      # 10 + 5
    assert s[0]["akum_positif"] == 2
    assert s[1]["net_total"] == -2.0      # -5 + 3
    assert s[1]["akum_negatif"] == 1
    assert s[3]["net_total"] == 0.0       # nol tidak dihitung positif/negatif


def test_seri_broker_menangani_payload_kosong() -> None:
    from live_trading.collectors.bandarmologi import seri_broker

    assert seri_broker({}) == []
    assert seri_broker({"series": [{"points": []}]}) == []


def test_uji_riwayat_butuh_data_cukup() -> None:
    from live_trading.collectors.bandarmologi import test_history

    assert test_history({}, {})["status"] == "belum-cukup-data"


def test_uji_riwayat_sinyal_bagus_dibanding_dasar() -> None:
    """Hari net-broker-positif diikuti kenaikan sementara pasar justru net turun -> unggul.

    Pasar sengaja dibuat NET TURUN (naik 3% di hari sinyal, turun 3,2% di hari lain) supaya
    keunggulan sinyal tidak bisa disalahartikan sebagai efek pasar naik.
    """
    from live_trading.collectors.bandarmologi import test_history

    t = _hari(60)
    tutup, v = [], 100.0
    for i in range(60):
        tutup.append(v)
        v *= 1.03 if i % 2 == 0 else 0.968
    acc = _acc(t, {"AA": [1000.0 if i % 2 == 0 else -1000.0 for i in range(60)]})
    r = test_history(acc, _hist(t, tutup), horizon_hari=(3, 5))
    assert r["status"] == "ok"
    assert r["hari_sinyal"] > 0
    assert r["dasar_positif_semua"] is False
    assert r["verdict"] == "ada-keunggulan"
    assert r["jumlah_lebih_baik"] == 2
    for u in r["uji"]:
        assert u["rata_sinyal_pct"] > 0
        assert u["rata_sinyal_pct"] > u["rata_dasar_pct"]


def test_uji_riwayat_menolak_menyebut_unggul_saat_pasar_naik_terus() -> None:
    """Kalau dasar positif di SEMUA horizon, keunggulan belum bisa dipercaya — ditandai jujur.

    Versi pasar-naik dari tes di atas: sinyalnya tetap lebih baik di kedua horizon, tapi
    karena seluruh pasar naik, modul menolak menyebutnya `ada-keunggulan`.
    """
    from live_trading.collectors.bandarmologi import test_history

    t = _hari(60)
    tutup, v = [], 100.0
    for i in range(60):
        tutup.append(v)
        if i % 2 == 0:
            v *= 1.03
    acc = _acc(t, {"AA": [1000.0 if i % 2 == 0 else -1000.0 for i in range(60)]})
    r = test_history(acc, _hist(t, tutup), horizon_hari=(3, 5))
    assert r["jumlah_lebih_baik"] == 2          # sinyal memang menang di kedua horizon
    assert r["dasar_positif_semua"] is True     # tapi pasar naik terus
    assert r["verdict"] == "perlu-uji-tambahan"  # jadi TIDAK disebut unggul


def test_horizon_genap_bisa_menghapus_selisih() -> None:
    """Kontrol untuk tes di atas: pada horizon genap efeknya memang nol, dan modul jujur."""
    from live_trading.collectors.bandarmologi import test_history

    t = _hari(60)
    tutup, v = [], 100.0
    for i in range(60):
        tutup.append(v)
        if i % 2 == 0:
            v *= 1.03
    acc = _acc(t, {"AA": [1000.0 if i % 2 == 0 else -1000.0 for i in range(60)]})
    r = test_history(acc, _hist(t, tutup), horizon_hari=(10,))
    assert r["uji"][0]["selisih_poin"] == 0.0
    assert r["verdict"] == "tidak-terbukti"


def test_uji_riwayat_sinyal_tidak_berguna() -> None:
    """Harga naik terus tanpa peduli broker -> sinyal tidak lebih baik dari dasar."""
    from live_trading.collectors.bandarmologi import test_history

    t = _hari(60)
    nval = [100.0 * (1.01 ** i) for i in range(60)]
    acc = _acc(t, {"AA": [500.0] * 60, "BB": [-400.0] * 60})  # net selalu +100
    r = test_history(acc, _hist(t, nval), horizon_hari=(5, 10, 20))
    assert r["status"] == "ok"
    # SEMUA hari jadi sinyal -> sinyal == dasar -> tidak ada selisih
    for u in r["uji"]:
        if "selisih_poin" in u:
            assert abs(u["selisih_poin"]) < 0.01


def test_uji_riwayat_menandai_efek_pasar() -> None:
    """Kalau dasar positif di semua horizon, keunggulan belum bisa dipercaya."""
    from live_trading.collectors.bandarmologi import test_history

    t = _hari(60)
    tutup = [100.0 * (1.02 ** i) for i in range(60)]  # pasar naik kuat
    acc = _acc(t, {"AA": [1000.0 if i % 3 == 0 else -100.0 for i in range(60)]})
    r = test_history(acc, _hist(t, tutup), horizon_hari=(5, 10, 20))
    assert r["dasar_positif_semua"] is True
    assert r["verdict"] in ("perlu-uji-tambahan", "tidak-terbukti")


def test_uji_riwayat_selalu_menyebut_batasnya() -> None:
    from live_trading.collectors.bandarmologi import test_history

    t = _hari(60)
    tutup = [100.0 + i for i in range(60)]
    acc = _acc(t, {"AA": [100.0] * 60})
    r = test_history(acc, _hist(t, tutup))
    gab = " ".join(r["catatan"])
    assert "dasar pembanding = SEMUA hari" in gab
    assert "tidak punya endpoint historis" in gab
    assert "bukti lemah" in gab


def test_uji_riwayat_harga_rusak_dilewati() -> None:
    from live_trading.collectors.bandarmologi import test_history

    t = _hari(60)
    h = _hist(t, [100.0] * 60)
    h["rows"][10]["close"] = None
    acc = _acc(t, {"AA": [100.0] * 60})
    r = test_history(acc, h)
    assert r["status"] == "ok"
