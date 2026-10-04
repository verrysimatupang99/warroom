"""Uji sinkron backendfragmen + frontend statis + CSS tunggal."""


def test_css_tunggal_sinkron() -> None:
    """_SHELL (SSR) harus memakai isi style.css persis — anti CSS ganda."""
    from live_trading.dashboard import _css, render

    css = _css()
    assert ".bar.nol" in css, "style.css ketinggalan poles bar-nol"
    html_out = render({"mode": "paper", "dibuat": "x", "risiko": {}, "ledger": {}})
    assert css in html_out, "render() tidak menyuntik style.css"


def test_klines_validasi_tanpa_jaringan() -> None:
    import pytest

    from live_trading.dashboard import _klines

    with pytest.raises(ValueError):
        _klines("btc!!", "1h")
    with pytest.raises(ValueError):
        _klines("BTCUSDT", "3m")
