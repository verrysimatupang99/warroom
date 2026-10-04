"""Multipage: tiap rute merakit blok grupnya; navbar menandai halaman aktif."""

from live_trading import dashboard


def _snap() -> dict:
    return {
        "mode": "paper", "dibuat": "x", "risiko": {}, "ledger": {},
        "lp_paper": {}, "poly_paper": {}, "posisi": [], "kandidat": [],
        "bagian": {},
    }


def test_rute_hanya_bawa_grupnya() -> None:
    snap = _snap()
    penuh = dashboard.render(snap)
    uang = dashboard.render(snap, page="uang")
    assert "href='/uang' aria-current='page'" in uang
    assert "ledger" in uang
    assert "id='terminal-live'" not in uang  # grup lain tidak ikut
    assert "id='gmgn-paper'" not in uang
    assert len(uang) < len(penuh)


def test_semua_rute_punya_nav_lengkap() -> None:
    snap = _snap()
    for route in ("semua", "terminal", "uang", "bukti", "pasar", "proyek"):
        html_out = dashboard.render(snap, page=route)
        for href in ("/", "/terminal", "/uang", "/bukti", "/pasar", "/proyek"):
            assert f"href='{href}'" in html_out, (route, href)


def test_fragmen_cakup_semua_halaman() -> None:
    from live_trading.dashboard import FRAGMEN_HALAMAN, fragments

    frag = fragments(_snap())
    for halaman, daftar in FRAGMEN_HALAMAN.items():
        for nama in daftar:
            assert nama in frag, (halaman, nama)


def test_frontend_statis_sinkron() -> None:
    from pathlib import Path

    from live_trading.dashboard import FRAGMEN_HALAMAN

    fed = Path(__file__).resolve().parent.parent / "frontend"
    assert (fed / "assets" / "style.css").is_file()
    assert (fed / "assets" / "app.js").is_file()
    pg = {"index": "index.html", "terminal": "terminal.html", "uang": "uang.html",
          "bukti": "bukti.html", "pasar": "pasar.html", "proyek": "proyek.html"}
    for halaman, berkas in pg.items():
        html_out = (fed / berkas).read_text(encoding="utf-8")
        for nama in FRAGMEN_HALAMAN[halaman]:
            assert f'data-frag="{nama}"' in html_out, (halaman, nama)
