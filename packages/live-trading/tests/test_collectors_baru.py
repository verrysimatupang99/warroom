"""Kolektor baru (Hyperliquid, screener IDX, bandarmologi Stockbit) — parsing diuji, bukan diasumsikan."""

from __future__ import annotations

import httpx
import pytest

from live_trading.collectors import hyperliquid, idx_stockbit, idx_tv
from live_trading.config import get_settings


# ---------------------------------------------------------------- hyperliquid
def test_hyperliquid_parsing_dan_urut_oi() -> None:
    payload = [
        {
            "universe": [
                {"name": "BTC", "maxLeverage": 40},
                {"name": "DOGE", "maxLeverage": 20},
                {"name": "OLD", "maxLeverage": 5, "isDelisted": True},
            ]
        },
        [
            {"markPx": "84000", "funding": "0.0000125", "openInterest": "38000"},
            {"markPx": "0.5", "funding": "-0.0004", "openInterest": "10000000"},
            {"markPx": "1", "funding": "0", "openInterest": "1"},
        ],
    ]
    client = httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200, json=payload)))

    rows = hyperliquid.perp_contexts(get_settings(), client=client)

    assert [r["coin"] for r in rows] == ["BTC", "DOGE"], "kontrak delisted harus dibuang"
    btc = rows[0]
    assert btc["mark"] == 84000
    assert btc["funding_hourly_pct"] == pytest.approx(0.00125)
    assert btc["oi_usd"] == pytest.approx(84000 * 38000)
    assert rows[1]["funding_hourly_pct"] == pytest.approx(-0.04)


def test_hyperliquid_snapshot_menaruh_funding_ekstrem_di_dua_ujung() -> None:
    payload = [
        {"universe": [{"name": n} for n in ("A", "B", "C")]},
        [
            {"markPx": "10", "funding": "0.0001", "openInterest": "100"},
            {"markPx": "10", "funding": "-0.0005", "openInterest": "50"},
            {"markPx": "10", "funding": "0.0009", "openInterest": "10"},
        ],
    ]
    client = httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200, json=payload)))

    snap = hyperliquid.snapshot(get_settings(), top=2, client=client)

    assert snap["total_perp"] == 3
    assert [r["coin"] for r in snap["top_by_oi"]][:2] == ["A", "B"]
    assert snap["funding_most_negative"][0]["coin"] == "B"
    assert snap["funding_most_positive"][0]["coin"] == "C"


def test_hyperliquid_konteks_satu_koin() -> None:
    payload = [
        {"universe": [{"name": "BTC"}, {"name": "ETH"}]},
        [{"markPx": "84000", "funding": "0.00002", "openInterest": "1000"} for _ in range(2)],
    ]
    client = httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200, json=payload)))

    k = hyperliquid.context_for("BTCUSDT", client=client)

    assert k is not None
    assert k["coin"] == "BTC"
    assert k["funding_annual_pct"] == pytest.approx(0.00002 * 100 * 24 * 365)


def test_hyperliquid_konteks_koin_tidak_dikenal_mengembalikan_none() -> None:
    payload = [{"universe": [{"name": "BTC"}]}, [{"markPx": "1", "funding": "0", "openInterest": "1"}]]
    client = httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200, json=payload)))

    assert hyperliquid.context_for("TIDAKADAUSDT", client=client) is None


# -------------------------------------------------------------------- idx_tv
def test_idx_tv_memetakan_kolom_dan_menandai_keadaan_ema(monkeypatch) -> None:
    cols = idx_tv.BASE_COLUMNS
    baris = [
        ["BBCA", 9000, 1.5, 50_000_000, 1.1e15, 55.0, 9010.0, 8950.0, 100.0, 0.2],
        ["BUMI", 180, -2.0, 60_000_000, 5e13, 40.0, 191.0, 195.0, 9.0, -0.4],
    ]
    monkeypatch.setattr(idx_tv, "_post", lambda body: {"data": [{"s": "IDX:X", "d": r} for r in baris]})
    assert cols[0] == "name"

    rows = idx_tv.screen(uptrend_only=False)

    assert rows[0]["ticker"] == "BBCA"
    assert rows[0]["ema_state"] == "naik"
    assert rows[0]["rsi14"] == 55.0
    assert rows[1]["ema_state"] == "turun"
    assert idx_tv.summary(rows)["ema_naik"] == 1


def test_idx_tv_filter_uptrend_dikirim_ke_server(monkeypatch) -> None:
    ditangkap: dict = {}

    def fake_post(body: dict) -> dict:
        ditangkap.update(body)
        return {"data": []}

    monkeypatch.setattr(idx_tv, "_post", fake_post)
    idx_tv.screen(uptrend_only=True, rsi_below=30, min_volume=1_000_000)

    teks = str(ditangkap["filter"])
    assert "EMA8" in teks and "RSI" in teks
    assert ditangkap["range"] == [0, 20]


def test_idx_tv_ema_tidak_tersedia_tidak_mengarang(monkeypatch) -> None:
    baris = [["X", 100, 0.0, 1, 1, 50.0, None, None, 1.0, 0.0]]
    monkeypatch.setattr(idx_tv, "_post", lambda body: {"data": [{"s": "IDX:X", "d": r} for r in baris]})

    rows = idx_tv.screen()

    assert rows[0]["ema_state"] == "n/a"


# ---------------------------------------------------------------- idx_check
def test_klasifikasi_bucket_tanpa_bergantung_emoji() -> None:
    from live_trading.collectors import idx_check

    assert idx_check.klasifikasi_bucket("🟢 SINYAL BERSIH") == "akumulasi"
    assert idx_check.klasifikasi_bucket("🥷 AKUMULASI SENYAP") == "akumulasi"
    assert idx_check.klasifikasi_bucket("🩸 RISIKO PANTULAN") == "waspada"
    assert idx_check.klasifikasi_bucket("⚔️ KONFLIK DISTRIBUSI") == "waspada"
    assert idx_check.klasifikasi_bucket("") == "netral"


def test_cross_check_menandai_yang_bertentangan() -> None:
    """Kesepakatan dua sumber lebih berharga daripada keyakinan satu sumber."""
    from live_trading.collectors import idx_check

    arjum = [
        {"stock_code": "PEGE", "bucket": "🟢 SINYAL BERSIH", "wr_event": 74.1, "potential": 11.0},
        {"stock_code": "WBSA", "bucket": "🥷 SINYAL SENYAP", "wr_event": 66.7, "potential": 8.0},
        {"stock_code": "ELTY", "bucket": "🩸 RISIKO PANTULAN", "wr_event": 63.0, "potential": 12.0},
        {"stock_code": "XXXX", "bucket": "🟢 SINYAL BERSIH"},
    ]
    tv = {
        "PEGE": {"close": 141, "change_pct": 2.0, "rsi14": 69.7, "ema_state": "naik"},
        "WBSA": {"close": 625, "change_pct": -1.0, "rsi14": 40.2, "ema_state": "turun"},
        "ELTY": {"close": 30, "change_pct": -3.0, "rsi14": 37.7, "ema_state": "turun"},
    }

    hasil = {r["kode"]: r for r in idx_check.gabungkan(arjum, tv)}

    assert hasil["PEGE"]["putusan"] == "sejalan"
    assert hasil["WBSA"]["putusan"] == "bertentangan"
    assert "di bawah EMA" in hasil["WBSA"]["alasan"]
    assert hasil["ELTY"]["putusan"] == "sejalan"
    assert hasil["XXXX"]["putusan"] == "netral", "tanpa data pembanding jangan mengklaim apa pun"
    assert hasil["PEGE"]["rsi14"] == 69.7


# -------------------------------------------------------------- idx_stockbit
def test_stockbit_tanpa_token_memberi_petunjuk_bukan_error_kosong(tmp_path) -> None:
    s = get_settings(home=tmp_path)

    assert idx_stockbit.load_token(s) is None
    hasil = idx_stockbit.broker_summary("BBRI", token=None)

    assert hasil["error"] == "token_belum_ada"
    assert "reCAPTCHA" in hasil["petunjuk"]


def test_stockbit_token_dibaca_dari_secrets(tmp_path) -> None:
    s = get_settings(home=tmp_path)
    d = idx_stockbit.secrets_dir(s)
    d.mkdir(parents=True, exist_ok=True)
    (d / idx_stockbit.TOKEN_FILENAME).write_text("Bearer abc.def.ghi", encoding="utf-8")

    assert idx_stockbit.load_token(s) == "abc.def.ghi", "prefiks Bearer harus dilepas"


def test_stockbit_parsing_broker_summary(monkeypatch) -> None:
    """Bentuk respons mengikuti hasil RE — field aslinya, bukan tebakan."""
    payload = {
        "status": "OK",
        "body": {
            "data": {
                "from": "2026-09-26",
                "to": "2026-09-27",
                "broker_summary": {
                    "brokers_buy": [
                        {
                            "netbs_broker_code": "DH",
                            "type": "ASING",
                            "blot": 1_000_000,
                            "bval": 119_700_000_000,
                            "freq": 900,
                        },
                    ],
                    "brokers_sell": [
                        {
                            "netbs_broker_code": "SS",
                            "type": "LOKAL",
                            "slot": 300_000,
                            "sval": 34_000_000_000,
                            "freq": 400,
                        },
                    ],
                },
                "bandar_detector": {"broker_accdist": "AKUMULASI", "total_buyer": 120, "total_seller": 80},
            }
        },
    }
    monkeypatch.setattr(idx_stockbit, "_get", lambda path, params, token: payload)

    hasil = idx_stockbit.broker_summary("DSSA", token="x")

    assert hasil["bandar"]["accdist"] == "AKUMULASI"
    assert hasil["pembeli"][0] == {
        "broker": "DH",
        "type": "ASING",
        "net_lot": 1_000_000,
        "net_idr": 119_700_000_000,
        "freq": 900,
    }
    assert hasil["penjual"][0]["broker"] == "SS"
    assert hasil["jendela"] == ["2026-09-26", "2026-09-27"]


def test_stockbit_parsing_distribusi_broker(monkeypatch) -> None:
    payload = {
        "body": {
            "data": {
                "start_date": "2026-09-20",
                "end_date": "2026-09-27",
                "by_value": {
                    "top_broker_buy": [
                        {
                            "detail": {"code": "SS", "type": "LOKAL", "amount": 34_000_000_000},
                            "distribute_to": [
                                {"code": "DH", "amount": 20_000_000_000},
                                {"code": "XL", "amount": 5_000_000_000},
                            ],
                        },
                    ],
                    "top_broker_sell": [],
                },
            }
        }
    }
    monkeypatch.setattr(idx_stockbit, "_get", lambda path, params, token: payload)

    hasil = idx_stockbit.broker_distribution("DSSA", token="x")

    assert hasil["satuan"] == "by_value"
    assert hasil["top_broker_buy"][0]["broker"] == "SS"
    assert hasil["top_broker_buy"][0]["menyalur_ke"][0] == {"broker": "DH", "amount": 20_000_000_000}
