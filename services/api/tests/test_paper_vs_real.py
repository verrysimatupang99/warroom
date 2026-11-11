"""Tes agregat laporan paper-vs-real (fungsi murni, tanpa DB).

Angka yang diuji: trade forex NYATA dinilai dari `pnl_usd`, trade crypto PAPER
dari `r`. Seri tidak masuk win-rate, dan data kosong menghasilkan `null` — bukan
0% yang menyesatkan.
"""

from __future__ import annotations

from warroom_api import paper_real


def _fx(pnl: str, simbol: str = "EURUSD", iso: str = "2026-11-01 10:00:00") -> dict:
    return {"iso": iso, "symbol": simbol, "pnl_usd": pnl, "market": "forex",
            "status": "closed_deal", "sumber": "mt5-forwardtest"}


def _paper(r: float, simbol: str = "BTCUSDT", iso: str = "2026-11-02 11:00:00") -> dict:
    return {"iso": iso, "symbol": simbol, "r": r, "market": "crypto", "sumber": "paper-crypto"}


def test_real_menghitung_menang_rugi_seri_dan_net():
    trades = [_fx("5.00"), _fx("-2.00"), _fx("0"), _fx("1.31", simbol="XAUUSD")]
    hasil = paper_real.ringkas_real(trades)
    assert hasil["n"] == 4
    assert hasil["menang"] == 2
    assert hasil["rugi"] == 1
    assert hasil["seri"] == 1
    assert hasil["net_usd"] == 4.31
    # Seri tidak dihitung: 2 menang / (2 menang + 1 rugi).
    assert hasil["winrate_pct"] == 66.7
    assert hasil["simbol"] == ["EURUSD", "XAUUSD"]
    assert hasil["rentang_tanggal"] == {"awal": "2026-11-01 10:00:00",
                                        "akhir": "2026-11-01 10:00:00"}


def test_real_tanpa_data_mengirim_null_bukan_nol():
    hasil = paper_real.ringkas_real([])
    assert hasil["n"] == 0
    assert hasil["menang"] == 0 and hasil["rugi"] == 0 and hasil["seri"] == 0
    assert hasil["winrate_pct"] is None
    assert hasil["net_usd"] is None
    assert hasil["rentang_tanggal"] is None
    assert hasil["simbol"] == []


def test_real_mengabaikan_pnl_kosong_dari_sumber_lama():
    """Baris tanpa pnl_usd tidak boleh dihitung menang maupun seri."""
    trades = [_fx(""), _fx(None), _fx("3.00")]
    hasil = paper_real.ringkas_real(trades)
    assert hasil["n"] == 3
    assert hasil["menang"] == 1
    assert hasil["rugi"] == 0
    assert hasil["seri"] == 0
    assert hasil["net_usd"] == 3.00


def test_paper_memakai_r_bukan_usd():
    trades = [_paper(2.0), _paper(1.5), _paper(-1.0), _paper(0.0)]
    hasil = paper_real.ringkas_paper(trades)
    assert hasil["n"] == 4
    assert hasil["menang"] == 2
    assert hasil["rugi"] == 1
    assert hasil["total_r"] == 2.5
    assert hasil["winrate_pct"] == 66.7


def test_paper_tanpa_data_mengirim_null():
    hasil = paper_real.ringkas_paper([])
    assert hasil["n"] == 0
    assert hasil["winrate_pct"] is None
    assert hasil["total_r"] is None


def test_banding_memisahkan_dua_blok_dan_membawa_peringatan():
    forex = [_fx("2.00"), _fx("-1.00"), _fx("-0.50")]
    crypto = [_paper(3.0), _paper(-1.0), _paper(2.0)]
    hasil = paper_real.banding(forex, crypto)
    assert hasil["real"]["n"] == 3
    assert hasil["real"]["winrate_pct"] == 33.3
    assert hasil["real"]["net_usd"] == 0.5
    assert hasil["real"]["status"] == "closed_deal"
    assert hasil["real"]["sumber"] == "mt5-forwardtest"
    assert hasil["paper"]["n"] == 3
    assert hasil["paper"]["winrate_pct"] == 66.7
    assert hasil["paper"]["total_r"] == 4.0
    assert hasil["paper"]["sumber"] == "paper-crypto"
    assert "paper != uang nyata" in hasil["peringatan"]


def test_banding_tahan_terhadap_none():
    hasil = paper_real.banding(None, None)
    assert hasil["real"]["n"] == 0
    assert hasil["paper"]["n"] == 0
    assert hasil["real"]["winrate_pct"] is None
    assert hasil["paper"]["total_r"] is None
