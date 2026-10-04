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
