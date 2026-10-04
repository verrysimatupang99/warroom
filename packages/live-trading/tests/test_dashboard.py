"""Dashboard — bagian baru harus benar-benar muncul, bukan cuma ada di kode."""

from __future__ import annotations

import html
from typing import Any

from live_trading import dashboard


def _snap(**extra: Any) -> dict[str, Any]:
    dasar: dict[str, Any] = {
        "dibuat": "2026-09-28 00:00 WIB",
        "mode": "paper",
        "risiko": {"hari_ini_r": 0.0, "batas_rugi_r": 3.0, "posisi_terbuka": 0, "maks_posisi": 3},
        "bagian": {},
        "posisi": [],
        "ledger": {"trade": 0},
        "gmgn": {"tersedia": False},
        "kandidat": [],
        "pengukuran": {},
    }
    dasar.update(extra)
    return dasar


def test_sembilan_bagian_render_dengan_tag_seimbang() -> None:
    snap = _snap(
        bagian={
            "crypto": [{"pair": "BTCUSDT", "price": 84000.0, "chg24h": 0.5, "funding": 0.001}],
            "idx": {"rows": [], "sumber": "arjum"},
            "forex": {},
            "hyperliquid": {
                "total_perp": 178,
                "top_by_oi": [
                    {"coin": "BTC", "mark": 84403.0, "oi_usd": 3.19e9, "funding_hourly_pct": 0.0013}
                ],
            },
            "idx_tv": {
                "jumlah": 1,
                "ema_naik": 1,
                "ema_turun": 0,
                "rows": [
                    {"ticker": "ASLI", "close": 486, "change_pct": 17.39, "rsi14": 75.2, "ema_state": "naik"}
                ],
            },
        },
        kandidat=[
            {
                "pair": "ENAUSDT",
                "direction": "long",
                "entry": 0.275,
                "sl": 0.2647,
                "allowed": True,
                "tier": "PREMIUM",
            }
        ],
        pengukuran={
            "total_tercatat": 14,
            "dinilai": 6,
            "lolos": {"n": 2, "tp1": 1, "sl": 1, "winrate": 50.0, "expectancy_r": 0.0, "total_r": 0.0},
            "ditolak_bayangan": {
                "n": 4,
                "tp1": 1,
                "sl": 3,
                "winrate": 25.0,
                "expectancy_r": -0.5,
                "total_r": -2.0,
            },
            "per_aturan": {
                "atr_min": {"n": 2, "expectancy_r": -1.0, "tp1": 0, "sl": 2, "putusan": "berguna"}
            },
        },
    )

    html_out = dashboard.render(snap)

    for judul in (
        "Hyperliquid — positioning",
        "IDX — screener TradingView",
        html.escape("Kandidat & pengukuran gate"),
    ):
        assert judul in html_out, f"bagian hilang: {judul}"
    assert html_out.count("<section") == html_out.count("</section>")
    assert "LOLOS" in html_out
    assert "berguna" in html_out
    assert "ASLI" in html_out


def test_terminal_live_ada() -> None:
    """Terminal live: section + canvas + tombol pair + endpoint snapshot."""
    html_out = dashboard.render(_snap())
    assert "terminal-live" in html_out
    assert "<canvas" in html_out
    assert "api/snapshot" in html_out
    assert "data-api.binance.vision" in html_out  # fallback kalau domain utama diblokir


def test_backtest_ubin_nada() -> None:
    """Ubin backtest 3-tuple harus render + garis nada kiri sesuai tanda."""
    html_out = dashboard.render(
        _snap(
            backtest={
                "n": 8441,
                "terisi_pct": 62.8,
                "lolos_bersih": -0.029,
                "lolos_terisi": 788,
                "lolos_keyakinan": "lemah",
                "semua_bersih": -0.003,
                "masuk_pasar_bersih": -0.04,
                "masuk_pasar_terisi": 6693,
                "biaya_bps": 5.0,
                "kotor_semua": 0.038,
                "per_aturan": {},
                "beda_aturan": {},
                "beda_lolos": {},
            }
        )
    )
    assert "lolos bersih" in html_out
    assert "data-tone='fail'" in html_out
    assert "data-tone='warn'" in html_out
    assert "metodologi" in html_out


def test_ringkas_dan_urutan() -> None:
    """TL;DR ada + urutan tampil: ringkasan > terminal > uang > bukti > pasar > proyek."""
    html_out = dashboard.render(
        _snap(
            ledger={"trade": 5, "total_r": 3.844},
            pengukuran={
                "lolos": {"n": 12, "winrate": 25.0, "expectancy_r": -0.383, "total_r": -4.594},
                "ditolak_bayangan": {"n": 71, "winrate": 31.0, "expectancy_r": -0.244, "total_r": -17.3},
                "per_aturan": {},
            },
            backtest={
                "n": 8441,
                "terisi_pct": 62.8,
                "lolos_bersih": -0.029,
                "lolos_terisi": 788,
                "lolos_keyakinan": "lemah",
                "semua_bersih": -0.003,
                "masuk_pasar_bersih": -0.04,
                "masuk_pasar_terisi": 6693,
                "biaya_bps": 5.0,
                "kotor_semua": 0.038,
                "per_aturan": {},
                "beda_aturan": {},
                "beda_lolos": {},
            },
        )
    )
    assert "Ringkasan 10 detik" in html_out
    assert "Artinya:" in html_out
    urutan = [
        "ringkasan-10-detik",
        "terminal-live",
        "ledger-warisan",
        "posisi-paper",
        "kandidat-pengukuran-gate",
        "backtest-gate-historis",
        "crypto-binance-perp",
        "radar-azure",
    ]
    pos = [html_out.index(f"id='{k}'") for k in urutan]
    assert pos == sorted(pos), "urutan tampil salah"
    assert "Bukti" in html_out and "Pasar" in html_out and "Proyek" in html_out


def test_dashboard_tetap_render_saat_sumber_gagal() -> None:
    """Satu sumber mati tidak boleh membuat seluruh halaman kosong."""
    snap = _snap(
        bagian={
            "crypto": {"error": "HTTP 500"},
            "hyperliquid": {"error": "timeout"},
            "idx_tv": {"error": "403"},
        },
        pengukuran={"error": "jaringan mati"},
    )

    html_out = dashboard.render(snap)

    assert "War Room" in html_out
    assert html_out.count("<section") == html_out.count("</section>")
    assert "timeout" in html_out


def test_radar_lima_tab() -> None:
    """5 tab Radar render dari shadow + lp_top, label tren benar."""
    shadow = [
        {
            "symbol": "AAA",
            "cluster_wallets": 8,
            "cluster_buy_usd": 5000,
            "ret_5m_pct": 3.0,
            "ret_1h_pct": 150.0,
            "shadow_pct": 12.5,
            "max_single_usd": 1500.0,
            "whale": True,
            "copy": True,
        },
        {
            "symbol": "BBB",
            "cluster_wallets": 2,
            "cluster_buy_usd": 300,
            "ret_5m_pct": 25.0,
            "ret_1h_pct": 10.0,
            "shadow_pct": -5.0,
            "max_single_usd": 100.0,
            "whale": False,
            "copy": False,
        },
    ]
    lp_top = [
        {"symbol": "UBI", "chain": "arc", "dex": "uniswissy", "fee": 0.3, "liq": 118000, "vol24": 570000}
    ]
    html_out = dashboard._radar_tabs(shadow, lp_top)
    for tab in ["Smart Money", "Smart Buy", "Whale", "Copy", "LP Edge"]:
        assert tab in html_out, tab
    assert "Tenang" in html_out and "Panas" in html_out
    assert "UBI" in html_out
