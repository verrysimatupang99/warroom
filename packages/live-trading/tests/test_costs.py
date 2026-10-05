"""Regresi: biaya eksekusi TERUKUR, bukan diasumsikan (P2 roadmap 5 Okt 2026).

Yang dikunci:
1. Slippage dihitung dari buku NYATA pada ukuran posisi yang benar (pair tipis > pair besar).
2. Buku tak tersedia → ditandai ``asumsi=True`` dengan slippage None — tidak pernah
   memakai angka karangan yang terlihat terukur.
3. ``be_stop_dari_bps`` memakai biaya terukur, bukan 0,1% yang dipatok.
"""

from __future__ import annotations

from live_trading.execution import costs


def _buku(pair: str, mid: float, level_bps: list[tuple[float, float]]) -> dict:
    """Buku sintetis: level_bps = [(jarak_bps, notional_usd), ...] untuk KEDUA sisi."""
    def blok(sisi: str) -> dict:
        levels = []
        cum = 0.0
        for bps, notional in level_bps:
            cum += notional
            harga = mid * (1 + bps / 10000.0) if sisi == "ask" else mid * (1 - bps / 10000.0)
            levels.append({"bps": bps, "price": harga, "notional_usd": notional, "cum_notional_usd": cum})
        return {"pair": pair, "side": sisi, "mid": mid, "best": levels[0]["price"] if levels else mid,
                "levels": levels, "total_notional_usd": cum}

    return {"pair": pair, "mid": mid, "bid": blok("bid"), "ask": blok("ask")}


def test_slippage_dihitung_dari_buku_nyata() -> None:
    """Buku tipis: size harus menelan level lebih dalam → slippage lebih besar."""
    tipis = _buku("THIN", 1.0, [(1.0, 50.0), (4.0, 100.0), (10.0, 500.0)])
    tebal = _buku("DEEP", 1.0, [(0.1, 100000.0)])

    b_tipis = costs.biaya_dari_depth(tipis, sisi_masuk="ask", size_usd=120.0, sisi_keluar="bid")
    b_tebal = costs.biaya_dari_depth(tebal, sisi_masuk="ask", size_usd=120.0, sisi_keluar="bid")

    assert b_tipis["asumsi"] is False
    # size 120 > 50 → harus menelan level 4 bps → rata-rata 2 bps
    assert b_tipis["slippage_bps_masuk"] == 2.0
    # buku tebal: size muat di level 0,1 bps → rata-rata 0,05 bps
    assert b_tebal["slippage_bps_masuk"] == 0.05
    assert b_tipis["total_bps"] > b_tebal["total_bps"]


def test_buku_tak_tersedia_ditandai_asumsi_tanpa_angka_palsu() -> None:
    kosong = {"pair": "X", "error": "buku kosong (salah satu sisi tidak ada)"}
    b = costs.biaya_dari_depth(kosong, sisi_masuk="ask", size_usd=100.0, sisi_keluar="bid")
    assert b["asumsi"] is True
    assert b["slippage_bps_masuk"] is None  # bukan 0, bukan angka karangan
    assert b["slippage_bps_keluar"] is None
    assert b["total_bps"] == costs.FEE_TAKER_BPS_PER_SISI * 2  # hanya fee


def test_fee_dihitung_dua_sisi_saat_keluar_diberi() -> None:
    buku = _buku("P", 100.0, [(0.0, 100000.0)])
    masuk_saja = costs.biaya_dari_depth(buku, sisi_masuk="ask", size_usd=100.0)
    bolak_balik = costs.biaya_dari_depth(buku, sisi_masuk="ask", size_usd=100.0, sisi_keluar="bid")
    assert masuk_saja["fee_bps"] == costs.FEE_TAKER_BPS_PER_SISI
    assert bolak_balik["fee_bps"] == costs.FEE_TAKER_BPS_PER_SISI * 2
    assert bolak_balik["total_bps"] > masuk_saja["total_bps"]


def test_be_stop_dari_bps_terukur() -> None:
    # 12 bps → stop 0,12% di atas entry untuk LONG
    assert costs.be_stop_dari_bps("LONG", 100.0, 12.0) == 100.12
    assert costs.be_stop_dari_bps("SHORT", 100.0, 12.0) == 99.88
    # biaya terukur (12 bps) LEBIH JAUH dari asumsi lama (10 bps) — arah konservatif
    assert costs.be_stop_dari_bps("LONG", 100.0, 12.0) > costs.be_stop_dari_bps("LONG", 100.0, 10.0)


def test_ringkas_jujur_soal_sumber() -> None:
    buku = _buku("P", 100.0, [(2.0, 100000.0)])
    terukur = costs.biaya_dari_depth(buku, sisi_masuk="ask", size_usd=100.0)
    assert "terukur" in costs.ringkas(terukur)
    asumsi = costs.biaya_asumsi(alasan="jaringan mati")
    assert "ASUMSI" in costs.ringkas(asumsi)
    assert "slippage tak terukur" in costs.ringkas(asumsi)
