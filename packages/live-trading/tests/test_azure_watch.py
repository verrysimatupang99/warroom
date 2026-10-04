"""Uji watchdog radar Azure: segar vs basi."""

from live_trading.collectors import azure_watch


def test_segar():
    ok, umur = azure_watch.cek_umur(umur_detik=600.0, batas_detik=1800.0)
    assert ok is True and umur == 600.0


def test_basi():
    ok, umur = azure_watch.cek_umur(umur_detik=3600.0, batas_detik=1800.0)
    assert ok is False and umur == 3600.0


def test_umur_file(tmp_path):

    p = tmp_path / "r.json"
    p.write_text("[]")
    ok, umur = azure_watch.cek_umur(azure_watch.umur_file(p), batas_detik=1800.0)
    assert ok is True and umur < 5.0


def test_file_hilang_basi():
    ok, _ = azure_watch.cek_umur(azure_watch.umur_file("/tidak/ada.json"))
    assert ok is False
