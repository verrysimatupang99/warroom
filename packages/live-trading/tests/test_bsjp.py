"""Regresi: BSJP — Beli Sore Jual Pagi (5 Okt 2026).

Yang dikunci — semuanya soal kejujuran angka, bukan sekadar "kode jalan":
1. Tanpa harga buka/tutup harian, mode WAJIB "proksi" dan edge_rata_pct None — bukan 0.
2. Win-rate Arjum tidak boleh disebut edge BSJP; catatan kejujuran wajib ada.
3. Skor hanya dihitung dari komponen yang benar-benar ada; tanpa data → None, bukan 0.
4. RSI tinggi MENURUNKAN skor (BSJP beli sore — RSI ekstrem = risiko beli di puncak).
5. Ticker di TradingView yang belum masuk screener tetap tampil (belum dinilai, bukan tidak ada).
"""

from __future__ import annotations

from live_trading.signals.bsjp import susun_peringkat

SCREENER = [
    {"stock_code": "SAPX", "stock_name": "Satria Antaran", "bucket": "RISIKO PANTULAN",
     "wr_event": 69.0, "potential": 16.0, "drawdown": -5.0},
    {"stock_code": "DSSA", "stock_name": "Dian Swastatika", "bucket": "AKUMULASI",
     "wr_event": 60.0, "potential": 8.0, "drawdown": -12.0},
]
TV = [
    {"ticker": "SAPX", "rsi14": 75.2, "ema_state": "naik", "atr": 49.4, "volume": 684639500},
    {"ticker": "ARCI", "rsi14": 55.0, "ema_state": "naik", "atr": 10.0, "volume": 1000},
]


def test_tanpa_harga_harian_mode_proksi_dan_edge_None() -> None:
    """Inti: data sekarang tidak bisa menghitung edge overnight. Jangan pura-pura bisa."""
    p = susun_peringkat(SCREENER, TV)
    assert p.mode == "proksi"
    assert p.edge_rata_pct is None, "edge tidak boleh 0 — itu berarti 'terukur nol'"
    assert p.n_sampel == 0
    assert "BELUM TERUKUR" in p.catatan_kejujuran
    assert "bukan hasil BSJP" in p.catatan_kejujuran.lower() or "PROKSI" in p.catatan_kejujuran


def test_mode_jendela_saat_edge_terukur() -> None:
    p = susun_peringkat(SCREENER, TV, edge_jendela_pct=0.42, n_jendela=120)
    assert p.mode == "jendela"
    assert p.edge_rata_pct == 0.42
    assert p.n_sampel == 120
    assert "terukur" in p.catatan_kejujuran


def test_skor_hanya_dari_komponen_yang_ada() -> None:
    """Tanpa potensi/WR/drawdown → skor None, bukan 0."""
    p = susun_peringkat([{"stock_code": "XXXX"}], [])
    k = p.kandidat[0]
    assert k.skor is None
    assert k.ticker == "XXXX"


def test_rsi_tinggi_menurunkan_skor() -> None:
    """RSI di atas ideal (70) harus kena penalti, dan alasannya tercatat."""
    p = susun_peringkat(SCREENER, TV)
    sapx = next(k for k in p.kandidat if k.ticker == "SAPX")
    assert sapx.skor is not None
    assert any("RSI" in c for c in sapx.catatan)
    assert any("kurang ideal" in c for c in sapx.catatan)


def test_rsi_ekstrem_penalti_lebih_berat() -> None:
    """RSI >= 80 = risiko beli di puncak → penalti lebih besar dan alasannya berbeda."""
    tv_ekstrem = [{"ticker": "SAPX", "rsi14": 85.0, "ema_state": "naik"}]
    biasa = susun_peringkat(SCREENER, TV)
    ekstrem = susun_peringkat(SCREENER, tv_ekstrem)
    s_biasa = next(k for k in biasa.kandidat if k.ticker == "SAPX").skor
    s_ekstrem = next(k for k in ekstrem.kandidat if k.ticker == "SAPX").skor
    assert s_biasa is not None and s_ekstrem is not None
    assert s_ekstrem < s_biasa, "RSI ekstrem harus menurunkan skor lebih banyak"
    assert any("puncak" in c for c in next(k for k in ekstrem.kandidat if k.ticker == "SAPX").catatan)


def test_ticker_tv_tanpa_screener_tetap_tampil() -> None:
    p = susun_peringkat(SCREENER, TV)
    arci = next((k for k in p.kandidat if k.ticker == "ARCI"), None)
    assert arci is not None, "ticker yang belum dinilai Arjum tetap harus terlihat"
    assert arci.skor is None
    assert any("belum dinilai" in c for c in arci.catatan)


def test_peringkat_urut_skor_tertinggi_dulu() -> None:
    p = susun_peringkat(SCREENER, TV)
    skor = [k.skor for k in p.kandidat if k.skor is not None]
    assert skor == sorted(skor, reverse=True)


def test_kosong_total() -> None:
    p = susun_peringkat(None, None)
    assert p.ada is False
    assert p.kandidat == []
    assert p.edge_rata_pct is None
