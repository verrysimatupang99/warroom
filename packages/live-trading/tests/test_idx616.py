"""Mirror IDX 616: cache + render kartu (tanpa jaringan)."""

import json

from live_trading.collectors import idx616


def test_snapshot_pakai_cache(tmp_path, monkeypatch) -> None:
    p = tmp_path / "idx616_mirror.json"
    import datetime as _dt

    now = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    p.write_text(json.dumps({"diambil": now, "terbuka": [], "tutup": [],
                             "per_setup": {}, "jurnal": []}), encoding="utf-8")
    monkeypatch.setattr(idx616, "_mirror_file", lambda _s: p)
    d = idx616.snapshot(tmp_path)
    assert d["terbuka"] == []


def test_snapshot_gagal_jaringan(tmp_path, monkeypatch) -> None:
    def boom(_path, timeout=20.0):
        raise ConnectionError("mati")

    monkeypatch.setattr(idx616, "_get", boom)
    d = idx616.fetch()
    assert "error" in d


def test_kartu_mirror_render() -> None:
    from live_trading import dashboard
    snap = {
        "mode": "paper", "dibuat": "x", "risiko": {}, "ledger": {},
        "lp_paper": {}, "poly_paper": {}, "posisi": [], "kandidat": [],
        "bagian": {
            "idx616": {
                "diambil": "2026-09-29 10:00",
                "terbuka": [{"ticker": "REAL.JK", "setup": "ARA_HUNTER",
                             "direction": "LONG", "entry_low": 45.0,
                             "sl": 43.9, "tp1": 45.5}],
                "tutup": [{"ticker": "EKAD.JK", "result": "TP2", "net_r": 2.0}],
                "per_setup": {"ARA_HUNTER": {"n": 3, "r": 4.5}},
                "jurnal": [],
            }
        },
    }
    html_out = dashboard.render(snap)
    assert "IDX 616 mirror" in html_out
    assert "REAL.JK" in html_out
    assert "EKAD.JK" in html_out


def test_snapshot_jatuh_ke_mirror_basi_saat_tencent_mati(tmp_path, monkeypatch) -> None:
    """Standalone: Tencent mati -> mirror terakhir dipakai, ditandai dari_cache + umurnya."""
    import datetime as _dt

    p = tmp_path / "idx616_mirror.json"
    basi = (_dt.datetime.now() - _dt.timedelta(hours=3)).strftime("%Y-%m-%d %H:%M")
    p.write_text(
        json.dumps({"diambil": basi, "terbuka": [{"ticker": "BBRI.JK"}], "tutup": [],
                    "per_setup": {"ARA_HUNTER": {"n": 1, "r": 1.0}}, "jurnal": []}),
        encoding="utf-8",
    )
    monkeypatch.setattr(idx616, "_mirror_file", lambda _s: p)

    def mati(_path, timeout=20.0):
        raise ConnectionError("mati")

    monkeypatch.setattr(idx616, "_get", mati)
    d = idx616.snapshot(tmp_path)

    assert d.get("dari_cache") is True
    assert d.get("peringatan")
    assert d.get("cache_umur_mnt", 0) > 170  # ~3 jam
    assert d["terbuka"] == [{"ticker": "BBRI.JK"}]  # data tetap tampil, bukan hilang


def test_snapshot_tanpa_mirror_error_tetap_error(tmp_path, monkeypatch) -> None:
    """Jangan mengarang: tanpa mirror dan Tencent mati, hasilnya memang error."""
    monkeypatch.setattr(idx616, "_mirror_file", lambda _s: tmp_path / "tidak-ada.json")

    def mati(_path, timeout=20.0):
        raise ConnectionError("mati")

    monkeypatch.setattr(idx616, "_get", mati)
    d = idx616.snapshot(tmp_path)

    assert "error" in d
    assert "dari_cache" not in d


def test_kartu_tampilkan_umur_cache() -> None:
    """Kartu jujur menyebut dari cache berapa menit saat Tencent tak terjangkau."""
    from live_trading import dashboard

    snap = {
        "mode": "paper", "dibuat": "x", "risiko": {}, "ledger": {},
        "lp_paper": {}, "poly_paper": {}, "posisi": [], "kandidat": [],
        "bagian": {
            "idx616": {
                "diambil": "2026-10-04 01:00", "dari_cache": True,
                "cache_umur_mnt": 180.0, "peringatan": "ConnectionError: mati",
                "terbuka": [], "tutup": [], "per_setup": {}, "jurnal": [],
            }
        },
    }
    html_out = dashboard.render(snap)
    assert "dari cache" in html_out
    assert "180.0 menit" in html_out
