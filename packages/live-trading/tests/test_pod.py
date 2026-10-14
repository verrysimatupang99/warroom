"""Uji pod Fase 1: analis + lead 4 proyek."""

from live_trading.pods import gmgn, idx, kripto, poly


def _snap() -> dict:
    return {
        "mode": "paper",
        "kandidat": [
            {"pair": "BTCUSDT", "direction": "LONG", "allowed": True},
            {"pair": "BTCUSDT", "direction": "LONG", "allowed": True},
            {"pair": "ETHUSDT", "direction": "SHORT", "allowed": False, "rules": ["r1"]},
        ],
        "ledger": {"total_r": 3.84, "trade": 5, "winrate_pct": 80.0, "expectancy_r": 0.769, "terakhir": []},
        "pengukuran": {"lolos": {"n": 43, "winrate": 46.5, "total_r": -1.59, "expectancy_r": -0.037}},
        "risiko": {"mode": "paper", "sisa_ruang_r": 3.0, "posisi_terbuka": 0},
        "poly_paper": {
            "arms": [
                {"nama": "B", "pnl": 17.34},
                {"nama": "D", "pnl": 12.01},
                {"nama": "A", "pnl": -10.34},
            ]
        },
        "radar": {"chains": [{"chain": "arc", "window": "PRIME", "avg_vl": 0.928}]},
        "lp_paper": {"posisi": [{"symbol": "UBI", "verdict": "TAHAN", "alasan": "ok"}]},
        "bagian": {
            "idx616": {
                "terbuka": [{"ticker": "X", "setup": "S"}, {"ticker": "X", "setup": "S"}],
                "per_setup": {"S": {"n": 2, "r": 1.0}},
            }
        },
    }


def test_kripto_dedupe_dan_bukti_merah() -> None:
    lap = kripto.lead(_snap())
    assert lap.pod == "kripto" and lap.status == "merah"
    assert "1 unik lolos" in lap.ringkas[0] and "duplikat" in lap.ringkas[0]
    assert "-EV" in lap.ringkas[1]


def test_poly_dua_arm_profit() -> None:
    lap = poly.lead(_snap())
    assert lap.status == "hijau" and "2/3 arm profit" in lap.ringkas[0]


def test_gmgn_prime_dan_tahan() -> None:
    lap = gmgn.lead(_snap())
    assert lap.status == "hijau" and "PRIME" in lap.ringkas[0]


def test_gmgn_lp_tunggu_mark() -> None:
    s = _snap()
    s["lp_paper"] = {"posisi": [{"symbol": "UBI", "verdict": None}]}
    lap = gmgn.lead(s)
    assert "cron mark" in lap.ringkas[1]


def test_idx_cap_fase2() -> None:
    lap = idx.lead(_snap())
    assert "Fase 2" in lap.ringkas[0]


def test_dashboard_punya_kartu_pod() -> None:
    from live_trading import dashboard

    frag = dashboard.fragments(_snap())
    for k in ("pod_kripto", "pod_poly", "pod_gmgn", "pod_idx"):
        assert k in frag and f"Pod {k[4:]}" in frag[k], k


def test_nilai_parse_json_berisik() -> None:
    from live_trading.pods import nilai

    asli = nilai.tanya
    nilai.tanya = lambda *a, **k: 'nih bos {"setuju": false, "catatan": "kurang data"} sip'
    try:
        v = nilai.evaluate_pod("x", ["a"])
        assert v == {"setuju": False, "catatan": "kurang data"}
    finally:
        nilai.tanya = asli


def test_nilai_gagal_none() -> None:
    from live_trading.pods import nilai

    asli = nilai.tanya
    nilai.tanya = lambda *a, **k: None
    try:
        assert nilai.evaluate_pod("x", ["a"]) is None
    finally:
        nilai.tanya = asli


def test_kartu_tampilkan_penilaian() -> None:
    from live_trading import dashboard

    snap = _snap()
    snap["pod_llm"] = {"kripto": {"setuju": True, "catatan": "oke"}}
    html_out = dashboard.fragments(snap)["pod_kripto"]
    assert "Penilaian" in html_out and "mimo" in html_out
