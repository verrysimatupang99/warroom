"""Regresi: BSJP — Beli Sore Jual Pagi (5 Okt 2026).

Berkas ini sudah dua kali berubah bentuk, dan tes di bawah mengunci pelajaran dari keduanya.

Versi pertama: modulnya cuma bisa memberi PROKSI, dan tesnya mengunci kejujuran itu
(mode "proksi", edge None bukan 0). Itu benar saat itu, tapi bukan keadaan akhir.

Versi sekarang: filter BSJP yang sudah diuji walk-forward dipindah dari Tencent
(`idx_bsjp_watch.py`). Jadi yang harus dikunci sekarang BUKAN lagi "mode proksi", melainkan:

1. Filter benar-benar diterapkan — kandidat gagal band chg / harga / nilai / rel-vol DITOLAK.
2. Tier STRONG = close ≥ 1,03×SMA10 DAN chg di 6–12%; di luar itu ARA.
3. Tanpa SMA10 → kandidat DITOLAK dengan alasan. Meloloskan berarti mengarang dasar tier.
4. Angka net WAJIB berlabel bersumber, dan `terverifikasi_di_warroom` False selama edge belum
   dihitung ulang di sini. Ini penjaga utama: jangan sampai angka Tencent tampak seperti
   hasil ukur War Room.
5. Kalau edge benar-benar dihitung di sini (`edge_jendela_pct`), mode jadi "terukur" dan
   `terverifikasi_di_warroom` True — jalur promosi ke angka sendiri harus tetap ada.
6. Kosong = "tidak ada yang lolos", bukan "rusak"; tetap ada penjelasannya.
"""

from __future__ import annotations

from live_trading.signals.bsjp import PARAM, susun_peringkat

# Kandidat yang lolos: harga 1200 (≥100), nilai > 1e9, chg di band.
# SAPX: close 1200, SMA10 1000 → ext 1,20 ≥ 1,03; chg 8,0 → di band STRONG 6–12 → STRONG.
# DSSA: close 1200, SMA10 1000 → ext 1,20; tapi chg 3,0 → di luar band STRONG → ARA.
SCREENER = [
    {"stock_code": "SAPX", "stock_name": "Satria Antaran", "bucket": "AKUMULASI",
     "wr_event": 69.0, "potensi": 16.0, "drawdown": -5.0},
    {"stock_code": "DSSA", "stock_name": "Dian Swastatika", "bucket": "AKUMULASI",
     "wr_event": 60.0, "potensi": 8.0, "drawdown": -12.0},
]
TV = [
    {"ticker": "SAPX", "close": 1200.0, "chg": 8.0, "volume": 5_000_000,
     "sma10": 1000.0, "vavg10": 2_000_000, "rsi14": 62.0, "ema_state": "naik", "atr": 49.4},
    {"ticker": "DSSA", "close": 1200.0, "chg": 3.0, "volume": 5_000_000,
     "sma10": 1000.0, "vavg10": 2_000_000, "rsi14": 55.0, "ema_state": "naik", "atr": 10.0},
]


def test_filter_diterapkan_kandidat_di_luar_band_ditolak() -> None:
    """chg di luar 2–25% harus ditolak, bukan cuma diberi catatan."""
    p = susun_peringkat(
        [], [{"ticker": "XXXX", "close": 1200.0, "chg": 40.0, "volume": 5_000_000,
              "sma10": 1000.0, "vavg10": 2_000_000}]
    )
    assert p.kandidat == []
    assert p.ditolak_filter == 1
    assert p.ada is False


def test_tanpa_sma10_ditolak_dengan_alasan() -> None:
    """Aturan #3: tanpanya, tier STRONG tidak punya dasar — tolak, jangan karang."""
    p = susun_peringkat([], [{"ticker": "YYYY", "close": 1200.0, "chg": 8.0,
                              "volume": 5_000_000}])
    assert p.kandidat == [], "kandidat tanpa SMA10 tidak boleh lolos"
    assert p.ditolak_filter == 1


def test_tier_strong_dan_ara_terpisah_benar() -> None:
    """STRONG = ext ≥ 1,03×SMA10 DAN chg 6–12%. Di luar band → ARA, bukan STRONG."""
    p = susun_peringkat(SCREENER, TV)
    sapx = next(k for k in p.kandidat if k.ticker == "SAPX")
    dssa = next(k for k in p.kandidat if k.ticker == "DSSA")
    assert sapx.tier == "STRONG", "chg 8,0 + ext 1,20 → STRONG"
    assert dssa.tier == "ARA", "chg 3,0 di luar band STRONG 6–12 → ARA"
    assert p.strong == 1 and p.ara == 1


def test_angka_bersumber_dan_tidak_diklaim_terverifikasi() -> None:
    """Penjaga utama: angka Tencent tidak boleh tampak seperti hasil ukur War Room."""
    p = susun_peringkat(SCREENER, TV)
    assert p.mode == "bersumber"
    assert p.terverifikasi_di_warroom is False
    assert p.edge_rata_pct is None, "edge terukur tetap None — belum dihitung di sini"
    assert "walk-forward" in p.sumber_angka.lower()
    assert "belum dihitung ulang" in p.catatan_kejujuran.lower()


def test_net_est_dari_sumber_bukan_nol() -> None:
    """Estimasi net harus terisi dari PARAM, dan STRONG memakai angka subset."""
    p = susun_peringkat(SCREENER, TV)
    sapx = next(k for k in p.kandidat if k.ticker == "SAPX")
    dssa = next(k for k in p.kandidat if k.ticker == "DSSA")
    assert sapx.net_est_pct == PARAM["net_strong_pct"] == 0.86
    assert dssa.net_est_pct == PARAM["net_ara_pct"] == 1.06
    assert p.net_est_pct is not None and p.net_est_pct != 0


def test_mode_terukur_saat_edge_dihitung_di_sini() -> None:
    """Jalur promosi harus tetap ada: begitu edge dihitung di sini, mode berubah."""
    p = susun_peringkat(SCREENER, TV, edge_jendela_pct=0.42, n_jendela=120)
    assert p.mode == "terukur"
    assert p.edge_rata_pct == 0.42
    assert p.n_sampel == 120
    assert p.terverifikasi_di_warroom is True
    assert "terukur" in p.catatan_kejujuran


def test_kosong_bukan_rusak() -> None:
    """Kosong harus dijelaskan sebagai hasil filter, bukan error."""
    p = susun_peringkat(None, None)
    assert p.ada is False
    assert p.kandidat == []
    assert p.edge_rata_pct is None
    assert "tidak ada kandidat" in p.catatan_kejujuran.lower()
    assert "wajar" in p.catatan_kejujuran.lower()


def test_strong_diurutkan_lebih_dulu_dari_ara() -> None:
    """Urutan sama dengan sumbernya: STRONG dulu, baru rel-vol terbesar."""
    p = susun_peringkat(SCREENER, TV)
    tier = [k.tier for k in p.kandidat]
    assert tier == sorted(tier, key=lambda t: t != "STRONG")
    assert p.kandidat[0].tier == "STRONG"


def test_diterima_dari_tradingview_saja_tanpa_screener() -> None:
    """Screener kosong bukan halangan: TradingView sudah membawa harga + SMA10."""
    p = susun_peringkat([], TV)
    assert {k.ticker for k in p.kandidat} == {"SAPX", "DSSA"}
    assert p.dipindai == 2


def test_ticker_ber_sufiks_jk_dinormalkan() -> None:
    """Kandidat dari universe Tencent datang sebagai 'SAPX.JK'.

    Sebelum normalisasi: `riwayat.get('SAPX.JK')` tidak menemukan kunci 'SAPX' dari
    ambil_riwayat → SMA10 hilang → kandidat ditolak tanpa sebab yang terlihat.
    Tes ini mengunci: 'SAPX.JK' harus diperlakukan sama seperti 'SAPX'.
    """
    screener = [{"stock_code": "SAPX.JK", "bucket": "AKUMULASI"}]
    tv = [{"ticker": "SAPX.JK", "close": 1200.0, "chg": 8.0, "volume": 5_000_000,
           "sma10": 1000.0, "vavg10": 2_000_000}]
    riwayat = {"SAPX": {"sma10": 1000.0, "vavg10": 2_000_000, "sumber": "arsip"}}

    p = susun_peringkat(screener, tv, riwayat=riwayat)
    tickers = [k.ticker for k in p.kandidat]
    assert "SAPX" in tickers, f"ticker bersih harus lolos, dapat: {tickers}"
    assert all(".JK" not in t for t in tickers), "tidak boleh ada .JK di keluaran"

    # Dan kunci riwayat ber-.JK juga harus menemukan nilai yang sama.
    p2 = susun_peringkat(screener, tv, riwayat={"SAPX.JK": {"sma10": 1000.0, "vavg10": 2_000_000}})
    assert [k.ticker for k in p2.kandidat] == tickers
