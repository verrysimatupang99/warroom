"""Heat skor & filter funding/OI — terpisah per strategi.

Yang dikunci:
1. Profil per strategi benar-benar terpisah: mengubah profil satu strategi tidak
   mengubah penilaian strategi lain.
2. Konteks tak terbaca -> n/a (skor None / filter ok=None), bukan 0 dan bukan "lolos".
3. Filter hanya menolak dengan alasan yang bisa dibaca; funding berlawanan arah dan
   OI mengempis adalah satu-satunya dua penolakan.
"""

from __future__ import annotations

import pytest

from live_trading.signals import heat

KONTEKS_PANAS = {
    "funding_pct": 0.02,
    "oi_delta_pct": 12.0,
    "taker_ratio": 1.4,
    "volume_24j_usd_m": 800.0,
    "chg24h_pct": -4.0,
}


def test_heat_terpisah_per_strategi() -> None:
    """Bobot berbeda -> skor berbeda dari konteks yang sama; itu inti pemisahan."""
    golden = heat.heat_strategi(heat.STRATEGI_GOLDEN, KONTEKS_PANAS)
    legacy = heat.heat_strategi(heat.STRATEGI_LEGACY, KONTEKS_PANAS)
    assert golden.skor is not None and legacy.skor is not None
    assert golden.skor != legacy.skor, "profil berbeda harus menghasilkan skor berbeda"
    assert golden.cakupan == legacy.cakupan == 1.0


def test_heat_strategi_tak_dikenal_pakai_bobot_netral() -> None:
    h = heat.heat_strategi("strategi-baru", {"volume_24j_usd_m": 500.0})
    assert h.skor == 50
    assert h.cakupan == 0.2, "1 dari 5 komponen berbobot 1,0"


def test_heat_tanpa_konteks_skor_none() -> None:
    h = heat.heat_strategi(heat.STRATEGI_LEGACY, {})
    assert h.skor is None
    assert h.cakupan == 0.0
    assert "n/a" in h.catatan


def test_heat_nol_terukur_bukan_tidak_terbaca() -> None:
    h = heat.heat_strategi(heat.STRATEGI_LEGACY, {"funding_pct": 0.0})
    assert h.skor == 0
    assert h.cakupan > 0, "funding 0% adalah pengukuran nyata (pasar tenang)"


def test_heat_bobot_bisa_ditimpa_eksplisit() -> None:
    h = heat.heat_strategi(
        heat.STRATEGI_GOLDEN,
        {"volume_24j_usd_m": 100.0},
        bobot={"volume_24j_usd_m": 2.0},
    )
    assert h.skor == 10


def test_filter_menolak_funding_ekstrem_searah_posisi() -> None:
    long_mahal = heat.filter_funding_oi(heat.STRATEGI_LEGACY, "long", {"funding_pct": 0.08})
    assert long_mahal.ok is False
    assert "terlambat" in long_mahal.alasan

    short_murah = heat.filter_funding_oi(heat.STRATEGI_LEGACY, "short", {"funding_pct": -0.08})
    assert short_murah.ok is False


def test_filter_tidak_menolak_funding_ekstrem_berlawanan_arah() -> None:
    """Funding sangat positif = long ramai; SHORT justru tidak dilarang oleh aturan ini."""
    hasil = heat.filter_funding_oi(heat.STRATEGI_LEGACY, "short", {"funding_pct": 0.08})
    assert hasil.ok is True


def test_filter_menolak_oi_mengempis_dua_arah() -> None:
    long_empis = heat.filter_funding_oi(heat.STRATEGI_LEGACY, "long", {"oi_delta_pct": -12.0})
    short_empis = heat.filter_funding_oi(heat.STRATEGI_LEGACY, "short", {"oi_delta_pct": -12.0})
    assert long_empis.ok is False and short_empis.ok is False
    assert "menguap" in long_empis.alasan


def test_filter_satu_aturan_terbaca_tetap_dinilai() -> None:
    """OI tak terbaca bukan alasan menolak: aturan itu n/a, sisanya tetap dievaluasi."""
    hasil = heat.filter_funding_oi(heat.STRATEGI_GOLDEN, "long", {"funding_pct": 0.01})
    assert hasil.ok is True
    oi_rule = next(a for a in hasil.aturan if a["aturan"] == "oi_mengempis")
    assert oi_rule["dievaluasi"] is False
    assert "tidak terbaca" in oi_rule["alasan"]


def test_filter_data_kosong_ok_none_bukan_lolos() -> None:
    hasil = heat.filter_funding_oi(heat.STRATEGI_LEGACY, "long", {})
    assert hasil.ok is None
    assert "tidak dievaluasi" in hasil.alasan
    assert all(a["dievaluasi"] is False for a in hasil.aturan)


def test_ambang_filter_terpisah_per_strategi(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mengubah ambang satu strategi tidak boleh mengubah penilaian strategi lain."""
    monkeypatch.setitem(
        heat.PROFIL_FILTER,
        heat.STRATEGI_GOLDEN,
        heat.AmbangFilter(funding_ekstrem_pct=0.01),
    )
    konteks = {"funding_pct": 0.02}
    keras = heat.filter_funding_oi(heat.STRATEGI_GOLDEN, "long", konteks)
    lunak = heat.filter_funding_oi(heat.STRATEGI_LEGACY, "long", konteks)
    assert keras.ok is False, "ambang golden 0,01% -> 0,02% sudah ekstrem"
    assert lunak.ok is True, "ambang legacy tetap 0,05% -> tidak terpengaruh"


def test_ambang_filter_validasi() -> None:
    with pytest.raises(ValueError):
        heat.AmbangFilter(funding_ekstrem_pct=0.0)
    with pytest.raises(ValueError):
        heat.AmbangFilter(oi_mengempis_pct=5.0)


def test_konteks_dari_agents_dan_snapshot() -> None:
    hasil_agents = {
        "agents": {
            "orderflow": {"data": {"funding_pct": 0.03, "taker_ratio": 1.2}},
            "whale": {"data": {"oi_delta_24h_pct": 8.5}},
        }
    }
    k = heat.konteks_dari_agents(hasil_agents)
    assert k["funding_pct"] == 0.03
    assert k["oi_delta_pct"] == 8.5
    assert k["taker_ratio"] == 1.2
    assert k["volume_24j_usd_m"] is None

    snap = {
        "funding": 0.01,
        "taker": 1.1,
        "quote_vol": 250.0,
        "chg24h": -3.2,
    }
    s = heat.konteks_dari_snapshot(snap)
    assert s["volume_24j_usd_m"] == 250.0
    assert s["oi_delta_pct"] is None, "snapshot memuat level OI, bukan delta"

    assert heat.konteks_dari_agents(None) == {}
    assert heat.konteks_dari_snapshot(None) == {}


def test_konteks_agents_rusak_tidak_melempar() -> None:
    assert heat.konteks_dari_agents({"agents": {"orderflow": None}})["funding_pct"] is None
    assert heat.konteks_dari_agents({"agents": "bukan-dict"})["funding_pct"] is None
