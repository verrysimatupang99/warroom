"""Uji aturan exit LP (dari threads) + tampilannya di dashboard."""

import importlib.util


def _lp():
    spec = importlib.util.spec_from_file_location(
        "lp_paper", "/home/admin/gmgn-scan/lp_paper.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _pos(**kw):
    d = {
        "symbol": "UBI",
        "entry_price": 100.0,
        "entry_ts": 1_000_000,
        "notional_usd": 30.0,
        "vl_at_entry": 4.0,
    }
    d.update(kw)
    return d


def _row(**kw):
    d = {"price": 100.0, "fee_ratio": 4.0, "price_5m": 0.0}
    d.update(kw)
    return d


def test_keluar_pool_hilang() -> None:
    lp = _lp()
    assert lp.aturan_keluar(_pos(), None, 2_000_000)[0] == "KELUAR"


def test_keluar_target_5persen() -> None:
    lp = _lp()
    # umur 30 hari, vl tinggi -> fee jauh di atas 5% notional
    v, a = lp.aturan_keluar(_pos(), _row(), 1_000_000 + 30 * 86400)
    assert v == "KELUAR" and "target" in a


def test_keluar_vl_layu() -> None:
    lp = _lp()
    v, a = lp.aturan_keluar(_pos(), _row(fee_ratio=1.0), 1_000_000 + 86400)
    assert v == "KELUAR" and "layu" in a


def test_keluar_umur_lewat() -> None:
    lp = _lp()
    v, a = lp.aturan_keluar(_pos(), _row(fee_ratio=0.01), 1_000_000 + 20 * 86400)
    # vl 0.01 tidak layu vs entry? 0.01 < 2.0 -> layu dulu; pakai vl sedang + umur lewat
    assert v == "KELUAR"


def test_keluar_il_dalam() -> None:
    lp = _lp()
    v, a = lp.aturan_keluar(_pos(), _row(price=50.0), 1_000_000 + 86400)
    assert v == "KELUAR" and "IL" in a


def test_keluar_dump_5m() -> None:
    lp = _lp()
    v, _a = lp.aturan_keluar(_pos(), _row(price_5m=-10.0), 1_000_000 + 86400)
    assert v == "KELUAR"


def test_tahan_sehat() -> None:
    lp = _lp()
    v, a = lp.aturan_keluar(_pos(), _row(), 1_000_000 + 86400)
    assert v == "TAHAN"


def test_dashboard_tampilkan_verdict() -> None:
    from live_trading import dashboard

    snap = {
        "mode": "paper",
        "dibuat": "x",
        "risiko": {},
        "ledger": {},
        "lp_paper": {
            "tersedia": True,
            "capital": 30.0,
            "posisi": [
                {
                    "symbol": "UBI",
                    "notional": 30.0,
                    "fee_hari": 1.44,
                    "vl": 4.83,
                    "vl_now": 4.5,
                    "verdict": "KELUAR",
                    "alasan": "target +5% kena",
                }
            ],
        },
    }
    html_out = dashboard.fragments(snap)["lp"]
    assert "KELUAR" in html_out and "target +5% kena" in html_out


def test_konsentrasi_idx() -> None:
    from live_trading import dashboard

    snap = {
        "mode": "paper",
        "dibuat": "x",
        "risiko": {},
        "ledger": {},
        "bagian": {
            "idx616": {
                "per_setup": {"ARA_HUNTER": {"n": 80, "r": 50.0}, "X": {"n": 5, "r": 1.86}},
                "terbuka": [],
                "tutup": [],
            }
        },
    }
    html_out = dashboard.fragments(snap)["idx616"]
    assert "konsentrasi:" in html_out and "ARA_HUNTER" in html_out
