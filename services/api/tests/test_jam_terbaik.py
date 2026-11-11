"""Tes fungsi agregat jam & hari terbaik (murni, tanpa API/DB)."""

from warroom_api.jam_terbaik import MIN_N, agregat_jam_hari


def _t(iso, symbol="XAUUSDc", pnl=None, **lain):
    return {"iso": iso, "symbol": symbol, "pnl_usd": "" if pnl is None else pnl, **lain}


def _contoh():
    return [
        _t("2026-11-09T10:00:00+00:00", pnl="10.00"),   # Senin 10:00 menang
        _t("2026-11-09T10:30:00+00:00", pnl="-2.00"),   # Senin 10:30 rugi
        _t("2026-11-10T14:00:00+00:00", pnl="6.00"),    # Selasa 14:00 menang
        _t("2026-11-10T14:20:00+00:00", pnl="4.00"),    # Selasa 14:20 menang
        _t("2026-11-10T23:00:00+00:00", pnl="-1.00"),   # Selasa 23:00 (n=1)
        _t("2026-11-10 19:17:00", pnl="0"),             # bentuk DB tanpa zona -> UTC, seri
        _t("", pnl="5.00"),                             # tanpa waktu
        _t("2026-11-11T08:00:00+00:00", pnl=""),        # tanpa angka hasil
    ]


def test_per_jam_dan_per_hari_dasar():
    h = agregat_jam_hari(_contoh(), market="forex")

    assert h["market"] == "forex"
    assert h["satuan"] == "pnl_usd"
    assert h["n_total"] == 8
    assert h["n_tanpa_waktu"] == 1
    assert h["n_tanpa_hasil"] == 1
    assert len(h["per_jam"]) == 24
    assert len(h["per_hari"]) == 7
    assert [b["hari"] for b in h["per_hari"]] == [
        "Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu",
    ]


def test_jam_10_dan_14_dihitung_benar():
    h = agregat_jam_hari(_contoh(), market="forex")
    jam = {b["jam"]: b for b in h["per_jam"]}

    assert jam[10]["n"] == 2
    assert jam[10]["menang"] == 1
    assert jam[10]["rugi"] == 1
    assert jam[10]["winrate_pct"] == 50.0
    assert jam[10]["pnl_usd_total"] == 8.0

    assert jam[14]["n"] == 2
    assert jam[14]["winrate_pct"] == 100.0
    assert jam[14]["pnl_usd_total"] == 10.0

    # 19:17 dari bentuk DB (tanpa zona) = UTC, pnl 0 -> seri, bukan menang/rugi.
    assert jam[19]["n"] == 1
    assert jam[19]["seri"] == 1
    assert jam[19]["winrate_pct"] is None
    assert jam[19]["pnl_usd_total"] == 0.0


def test_jam_kosong_tidak_diisi_nol_palsu():
    h = agregat_jam_hari(_contoh(), market="forex")
    kosong = {b["jam"]: b for b in h["per_jam"]}[5]

    assert kosong["n"] == 0
    assert kosong["menang"] == 0
    assert kosong["winrate_pct"] is None
    assert kosong["pnl_usd_total"] is None  # bukan 0.0


def test_jam_dan_hari_terbaik():
    h = agregat_jam_hari(_contoh(), market="forex")

    assert h["jam_terbaik"]["jam"] == 14
    assert h["jam_terbaik"]["pnl_usd_total"] == 10.0
    assert h["hari_terbaik"]["hari"] == "Selasa"
    assert h["hari_terbaik"]["pnl_usd_total"] == 9.0  # 6 + 4 - 1 + 0
    assert h["hari_terbaik"]["n"] == 4

    senin = {b["hari"]: b for b in h["per_hari"]}["Senin"]
    assert senin["n"] == 2
    assert senin["pnl_usd_total"] == 8.0


def test_terbaik_butuh_n_minimal():
    """Satu trade profit bukan pola: jam/hari terbaik harus None bila n < MIN_N."""
    h = agregat_jam_hari([_t("2026-11-10T09:00:00+00:00", pnl="50.00")], market="forex")

    assert MIN_N == 2
    assert h["jam_terbaik"] is None
    assert h["hari_terbaik"] is None
    assert h["per_jam"][9]["pnl_usd_total"] == 50.0


def test_kosong_total_tidak_error():
    h = agregat_jam_hari([], market="forex")

    assert h["n_total"] == 0
    assert h["jam_terbaik"] is None
    assert h["hari_terbaik"] is None
    assert all(b["winrate_pct"] is None for b in h["per_jam"])


def test_crypto_pakai_r():
    trades = [
        {"iso": "2026-11-10T03:00:00+00:00", "symbol": "CRVUSDT", "r": "1.0"},
        {"iso": "2026-11-10T03:30:00+00:00", "symbol": "ENAUSDT", "r": "-1.0"},
        {"iso": "2026-11-10T04:00:00+00:00", "symbol": "ENAUSDT", "r": "+2.5"},
    ]
    h = agregat_jam_hari(trades, market="crypto")

    assert h["satuan"] == "r"
    jam = {b["jam"]: b for b in h["per_jam"]}
    assert jam[3]["n"] == 2
    assert jam[3]["winrate_pct"] == 50.0
    assert jam[3]["pnl_usd_total"] == 0.0


def test_zona_waktu_dikonversi_ke_utc():
    """17:30 WIB = 10:30 UTC — jam mengikuti UTC, sudah dihitung dari waktu tutup."""
    h = agregat_jam_hari(
        [
            {"iso": "2026-11-10T17:30:00+07:00", "symbol": "XAUUSDc", "pnl_usd": "1.0"},
            {"iso": "2026-11-10T10:45:00+00:00", "symbol": "XAUUSDc", "pnl_usd": "-1.0"},
        ],
        market="forex",
    )
    jam = {b["jam"]: b for b in h["per_jam"]}
    assert jam[10]["n"] == 2
    assert jam[17]["n"] == 0
