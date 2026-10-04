"""Uji watchdog gabungan: sehat cukup 1 baris, sakit sebut nama."""

from live_trading.ops import watchdog as w


def test_sehat_satu_baris():
    cek = [("snapshot", 60.0, 1200.0), ("gmgn", 300.0, 4200.0)]
    out = w.jalankan(cek)
    assert out == ["SEHAT 2/2"]


def test_sakit_sebut_nama():
    cek = [("snapshot", 60.0, 1200.0), ("lp_mark", 200000.0, 93600.0)]
    out = w.jalankan(cek)
    assert out[0] == "AWAS 1/2"
    assert any("lp_mark" in b for b in out[1:])


def test_cek_produksi_menyertakan_radar_azure(tmp_path):
    """Radar Azure ikut dipantau lewat cache lokal (azure_watch)."""
    cek = w.cek_produksi(home=tmp_path)
    nama = [n for n, _, _ in cek]
    assert "radar_azure" in nama
    batas = {n: b for n, _, b in cek}
    assert batas["radar_azure"] == 3600.0
