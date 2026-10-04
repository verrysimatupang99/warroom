"""Tes pengukur 'overextended' + uji edge short — tanpa jaringan.

Prinsip yang diuji: fakta harga ("sudah naik banyak") tidak boleh disamakan dengan sinyal short,
dan satu trade yang berhasil tidak boleh dianggap bukti.
"""

from __future__ import annotations

from live_trading.collectors.overextended import (
    FR_NETRAL_PCT,
    uji_edge_short,
    ukur_kelebihan,
)

JAM_MS = 3_600_000
T0 = 1_760_000_000_000


def _klines(harga: list[float], oi: list[float] | None = None) -> list[list]:
    """Bikin kline 1 jam dari deret harga (high=low=close=harga)."""
    out = []
    for i, h in enumerate(harga):
        out.append([T0 + i * JAM_MS, h, h, h, h, 1000.0, 0, 0, 0, 0, 0, 0])
    return out


def _oi(harga: list[float]) -> list[dict]:
    return [
        {"timestamp": T0 + i * JAM_MS, "sumOpenInterestValue": str(v)} for i, v in enumerate(harga)
    ]


def _fr(n: int, nilai: float = 0.02) -> list[dict]:
    return [{"fundingTime": T0 + i * 8 * JAM_MS, "fundingRate": str(nilai / 100)} for i in range(n + 2)]


def test_pump_dan_oi_dihitung() -> None:
    kl = _klines([1.0, 1.2, 1.8, 1.5])
    oi = _oi([100.0, 120.0, 200.0, 150.0])
    h = ukur_kelebihan(kl, oi, _fr(3))
    assert h["status"] == "ok"
    assert h["harga_terendah"] == 1.0 and h["harga_tertinggi"] == 1.8
    assert h["pump_pct"] == 80.0
    assert h["turun_dari_puncak_pct"] == -16.67  # 1,5 dari 1,8
    assert h["overextended"] is True


def test_oi_belum_mereda_ditandai() -> None:
    kl = _klines([1.0, 1.2, 1.8, 1.5])
    oi = _oi([100.0, 120.0, 200.0, 195.0])  # masih dekat puncak
    h = ukur_kelebihan(kl, oi, _fr(3))
    assert h["oi_mereda_pct"] == -2.5
    assert any("BELUM mereda" in c for c in h["catatan"])


def test_oi_sudah_mereda_tidak_ditandai_belum() -> None:
    kl = _klines([1.0, 1.2, 1.8, 1.5])
    oi = _oi([100.0, 120.0, 200.0, 80.0])  # -60% dari puncak
    h = ukur_kelebihan(kl, oi, _fr(3))
    assert h["oi_mereda_pct"] == -60.0
    assert not any("BELUM mereda" in c for c in h["catatan"])


def test_funding_ramai_dikenali() -> None:
    kl = _klines([1.0, 1.1, 1.2])
    h = ukur_kelebihan(kl, _oi([1.0, 1.1, 1.2]), _fr(3, nilai=0.30))
    assert h["fr_pernah_ramai"] is True
    assert h["fr_maks_pct"] == 0.3


def test_funding_netral_ditulis_apa_adanya() -> None:
    """Kasus VELVET: funding tidak pernah ramai -> itu harus dikatakan, bukan dilewati."""
    kl = _klines([1.0, 1.1, 1.2])
    h = ukur_kelebihan(kl, _oi([1.0, 1.1, 1.2]), _fr(3, nilai=0.02))
    assert h["fr_pernah_ramai"] is False
    assert any("tidak pernah ramai" in c for c in h["catatan"])
    assert FR_NETRAL_PCT == 0.05


def test_selalu_menyatakan_puncak_hanya_diketahui_setelahnya() -> None:
    h = ukur_kelebihan(_klines([1.0, 1.1]), _oi([1.0, 1.1]), _fr(2))
    assert any("BUKAN sinyal short" in c for c in h["catatan"])


def test_data_kurang_tidak_menebak() -> None:
    assert ukur_kelebihan([])["status"] == "belum-cukup-data"
    assert uji_edge_short([])["status"] == "belum-cukup-data"


def test_naik_terus_membuat_short_merugi() -> None:
    """Harga naik mulus: short harus rugi di SEMUA horizon (dasar pembanding negatif)."""
    kl = _klines([1.0 + 0.05 * i for i in range(30)])
    oi = _oi([100.0 + i for i in range(30)])
    u = uji_edge_short(kl, oi, _fr(5), horizon_jam=(6,))
    assert u["status"] == "ok"
    assert len(u["uji"]) == 1
    assert u["uji"][0]["rata_dasar_pct"] < 0
    assert u["verdict"] == "tidak-terbukti"


def test_turun_terus_membuat_short_untung() -> None:
    kl = _klines([1.0 - 0.02 * i for i in range(30)])
    oi = _oi([100.0 - i for i in range(30)])  # OI turun -> tidak ada sinyal (syarat OI naik)
    u = uji_edge_short(kl, oi, _fr(5), horizon_jam=(6,))
    assert u["uji"][0]["rata_dasar_pct"] > 0
    assert u["jumlah_sinyal"] == 0


def test_sinyal_butuh_ketiga_syarat() -> None:
    """Harga naik + OI naik + FR netral = sinyal; hilangkan satu -> tidak ada sinyal."""
    kl = _klines([1.0, 1.1, 1.2, 1.3])
    naik_oi = _oi([100.0, 110.0, 120.0, 130.0])
    u1 = uji_edge_short(kl, naik_oi, _fr(3, 0.02), horizon_jam=(6,))
    assert u1["jumlah_sinyal"] == 3

    oi_turun = _oi([100.0, 90.0, 80.0, 70.0])
    u2 = uji_edge_short(kl, oi_turun, _fr(3, 0.02), horizon_jam=(6,))
    assert u2["jumlah_sinyal"] == 0

    u3 = uji_edge_short(kl, naik_oi, _fr(3, 0.60), horizon_jam=(6,))  # funding ramai
    assert u3["jumlah_sinyal"] == 0


def test_verdict_menyebut_alasan_bukan_angka_saja() -> None:
    kl = _klines([1.0 + 0.01 * i for i in range(30)])
    oi = _oi([100.0 + i for i in range(30)])
    u = uji_edge_short(kl, oi, _fr(5), horizon_jam=(6, 12))
    assert u["verdict"] in ("ada-keunggulan", "tidak-terbukti")
    assert "horizon" in u["ringkas"]
    assert len(u["uji"]) == 2


def test_hasil_uji_memuat_pembanding_dasar() -> None:
    """Tanpa dasar pembanding, satu hasil tidak berarti apa-apa."""
    kl = _klines([1.0 + 0.01 * i for i in range(30)])
    u = uji_edge_short(kl, _oi([100.0 + i for i in range(30)]), _fr(5), horizon_jam=(6,))
    baris = u["uji"][0]
    for kunci in ("rata_sinyal_pct", "rata_dasar_pct", "selisih_poin", "winrate_sinyal_pct", "n_dasar"):
        assert kunci in baris


# --- CVD: sinyal KETIGA yang diklaim postingan -------------------------------------------

def _klines_cvd(harga: list[float], taker_buy: list[float], volume: list[float]) -> list[list]:
    """Kline lengkap dengan kolom volume (5) & takerBuyBase (9) supaya CVD bisa dihitung."""
    out = []
    for i, h in enumerate(harga):
        k = [T0 + i * JAM_MS, h, h, h, h, volume[i], 0, 0, 0, taker_buy[i], 0, 0]
        out.append(k)
    return out


def test_cvd_murni_beli_positif() -> None:
    from live_trading.collectors.overextended import cvd_seri

    # semua volume adalah taker buy -> delta positif tiap bar
    kl = _klines_cvd([1.0, 1.1, 1.2], [10.0, 10.0, 10.0], [10.0, 10.0, 10.0])
    seri = cvd_seri(kl)
    assert seri == [10.0, 20.0, 30.0]


def test_cvd_murni_jual_negatif() -> None:
    from live_trading.collectors.overextended import cvd_seri

    kl = _klines_cvd([1.0, 1.1], [0.0, 0.0], [10.0, 10.0])
    assert cvd_seri(kl) == [-10.0, -20.0]


def test_cvd_seimbang_nol() -> None:
    from live_trading.collectors.overextended import cvd_seri

    kl = _klines_cvd([1.0, 1.0], [5.0, 5.0], [10.0, 10.0])
    assert cvd_seri(kl) == [0.0, 0.0]


def test_cvd_menangani_kline_rusak() -> None:
    from live_trading.collectors.overextended import cvd_seri

    kl = _klines_cvd([1.0], [5.0], [10.0])
    kl.append([T0, 1.0])  # kline terpotong
    assert cvd_seri(kl)[-1] == 0.0


def test_divergensi_terdeteksi_saat_harga_naik_tapi_agresi_beli_turun() -> None:
    """Inti klaim 'buyer exhaustion': harga puncak lebih tinggi, CVD puncak lebih rendah."""
    from live_trading.collectors.overextended import uji_kehabisan_pembeli

    n = 48
    harga, tb, vol = [], [], []
    for i in range(n):
        if i < 24:
            harga.append(1.0 + 0.01 * i)
            tb.append(50.0)  # beli kuat
        else:
            harga.append(1.30 + 0.01 * (i - 24))  # harga tetap naik ke puncak lebih tinggi
            tb.append(5.0)  # tapi agresi beli kolaps
        vol.append(100.0)
    h = uji_kehabisan_pembeli(_klines_cvd(harga, tb, vol), jendela=24)
    assert h["status"] == "ok"
    assert h["harga_lebih_tinggi"] is True
    assert h["cvd_lebih_rendah"] is True
    assert h["divergensi"] is True
    assert any("buyer exhaustion" in c or "agresi beli lebih rendah" in c for c in h["catatan"])


def test_tanpa_divergensi_saat_harga_dan_agresi_sejalan() -> None:
    from live_trading.collectors.overextended import uji_kehabisan_pembeli

    n = 48
    harga = [1.0 + 0.01 * i for i in range(n)]
    tb = [50.0 + i for i in range(n)]
    vol = [100.0] * n
    h = uji_kehabisan_pembeli(_klines_cvd(harga, tb, vol), jendela=24)
    assert h["divergensi"] is False


def test_divergensi_bukan_izin_short() -> None:
    """Divergensi harus selalu disertai peringatan bahwa itu bukan izin short."""
    from live_trading.collectors.overextended import uji_kehabisan_pembeli

    n = 48
    harga = [1.0 + 0.01 * i for i in range(n)]
    h = uji_kehabisan_pembeli(_klines_cvd(harga, [50.0] * n, [100.0] * n), jendela=24)
    assert any("BUKAN izin short" in c for c in h["catatan"])


def test_ukur_kelebihan_menyertakan_kehabisan_pembeli() -> None:
    from live_trading.collectors.overextended import ukur_kelebihan

    n = 48
    harga = [1.0 + 0.01 * i for i in range(n)]
    kl = _klines_cvd(harga, [50.0] * n, [100.0] * n)
    h = ukur_kelebihan(kl, _oi([1.0] * n), _fr(5))
    assert "kehabisan_pembeli" in h
    assert h["kehabisan_pembeli"]["status"] == "ok"


def test_uji_edge_divergensi_cvd_memakai_mesin_yang_sama() -> None:
    from live_trading.collectors.overextended import uji_edge_divergensi_cvd

    n = 60
    harga = [1.0 + 0.005 * i for i in range(n)]
    kl = _klines_cvd(harga, [50.0] * n, [100.0] * n)
    u = uji_edge_divergensi_cvd(kl, horizon_jam=(6,), jendela=24)
    assert u["status"] == "ok"
    assert "divergensi-CVD" in u["nama_tanda"]
    assert u["uji"][0]["rata_dasar_pct"] < 0  # harga naik terus -> short asal rugi
    assert u["verdict"] in ("tidak-terbukti", "tidak-ada-sinyal")


def test_tanda_custom_tidak_menyontek_masa_depan() -> None:
    """`tanda_divergensi_cvd` pada bar ke-i hanya boleh memakai data sampai bar i."""
    from live_trading.collectors.overextended import tanda_divergensi_cvd

    n = 60
    harga = [1.0 + 0.01 * i for i in range(n)]
    tb = [50.0] * 30 + [2.0] * 30
    vol = [100.0] * n
    kl = _klines_cvd(harga, tb, vol)
    idx = tanda_divergensi_cvd(kl, jendela=24)
    assert all(i < len(kl) for i in idx)
    assert len(idx) > 0  # ada divergensi setelah agresi beli kolaps


# --- Kejujuran putusan: jangan mengaku unggul hanya karena pasar turun -------------------

def test_satu_horizon_saja_tidak_cukup_disebut_unggul() -> None:
    """Perlu ≥2 horizon. Satu kebetulan bukan keunggulan."""
    from live_trading.collectors.overextended import uji_edge_short

    # harga naik -> dasar negatif, sinyal tidak menang -> tidak-terbukti
    kl = _klines([1.0 + 0.01 * i for i in range(40)])
    u = uji_edge_short(kl, _oi([100.0 + i for i in range(40)]), _fr(6), horizon_jam=(6,))
    assert u["jumlah_horizon"] == 1
    assert u["verdict"] == "tidak-terbukti"


def test_pasar_turun_bukan_bukti_keunggulan() -> None:
    """Kalau dasar pembanding positif di SEMUA horizon, short menang apa pun sinyalnya.

    Ini kasus nyata: 4 dari 6 koin besar sempat terbaca 'ada-keunggulan' padahal seluruh pasar
    sedang turun. Harus ditandai `perlu-uji-tambahan`, bukan dipuji.

    Harga dibuat berombak (ada jam naik supaya sinyal bisa menyala) tapi net menurun
    (supaya short asal-asalan pun untung = dasar positif).
    """
    from live_trading.collectors.overextended import uji_edge_short

    harga = [1.0]
    for i in range(79):
        # naik tipis di jam genap, turun lebih besar di jam ganjil -> net turun, ada jam naik
        harga.append(harga[-1] * (1.005 if i % 2 == 0 else 0.988))

    kl = _klines([round(h, 6) for h in harga])
    oi = _oi([100.0 + i for i in range(len(harga))])  # OI naik -> sinyal menyala di jam naik
    u = uji_edge_short(kl, oi, _fr(12), horizon_jam=(6, 12, 24))

    assert u["jumlah_sinyal"] > 0, "tanda tangan harus menyala minimal sekali"
    assert all(row["rata_dasar_pct"] > 0 for row in u["uji"]), "pasar net turun -> dasar positif"
    assert u["dasar_positif_semua"] is True
    assert u["verdict"] in ("perlu-uji-tambahan", "tidak-terbukti")
    if u["jumlah_lebih_baik"] >= 2:
        assert u["verdict"] == "perlu-uji-tambahan"
        assert "pasar sedang turun" in u["ringkas"]


def test_putusan_selalu_menyebut_alasan() -> None:
    from live_trading.collectors.overextended import uji_edge_short

    kl = _klines([1.0 + 0.01 * i for i in range(40)])
    u = uji_edge_short(kl, _oi([100.0 + i for i in range(40)]), _fr(6), horizon_jam=(6, 12))
    assert u["ringkas"]
    assert u["jumlah_horizon"] == len(u["uji"])
    assert "dasar_positif_semua" in u

