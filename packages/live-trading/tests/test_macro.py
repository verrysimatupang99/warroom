"""Kalender makro + gerbang stand-down (tanpa jaringan)."""

from __future__ import annotations

import json
import time

from live_trading.collectors import macro

#: Rabu 2026-10-07 18:00 UTC — dipakai sebagai "sekarang" di tes.
NOW = 1791386400.0


def _ev(judul: str, offset_s: float, impact: str = "High", cur: str = "USD") -> dict:
    import datetime as dt

    t = dt.datetime.fromtimestamp(NOW + offset_s, dt.UTC).isoformat()
    return {"title": judul, "country": cur, "date": t, "impact": impact, "forecast": "", "previous": ""}


def test_normalisasi_membuang_tanpa_waktu_dan_mengurutkan() -> None:
    rows = macro.normalisasi(
        [
            {"title": "B", "country": "USD", "date": "2026-10-07T20:00:00+00:00", "impact": "High"},
            {"title": "rusak", "country": "USD", "date": "bukan-tanggal", "impact": "High"},
            {"title": "A", "country": "USD", "date": "2026-10-07T10:00:00+00:00", "impact": "Low"},
            "bukan dict",
        ]
    )
    assert [r["title"] for r in rows] == ["A", "B"]  # urut waktu, yang rusak dibuang


def test_stand_down_hanya_melihat_ke_depan() -> None:
    events = macro.normalisasi(
        [
            _ev("sudah_lewat", -600),
            _ev("dalam_jendela", +1800),  # 30 menit lagi
            _ev("terlalu_jauh", +7200),  # 2 jam lagi
        ]
    )
    blok = macro.stand_down(events, sekarang=NOW, jendela_menit=60)
    assert [b["title"] for b in blok] == ["dalam_jendela"]
    assert blok[0]["menit_lagi"] == 30.0


def test_stand_down_abaikan_impact_rendah_dan_mata_uang_luar_pantauan() -> None:
    events = macro.normalisasi(
        [
            _ev("Medium", +1800, impact="Medium"),
            _ev("Holiday", +1800, impact="Holiday"),
            _ev("IDR", +1800, cur="IDR"),
            _ev("FOMC", +1800, cur="USD"),
        ]
    )
    blok = macro.stand_down(events, sekarang=NOW, jendela_menit=60)
    assert [b["title"] for b in blok] == ["FOMC"]


def test_ringkas_menyertakan_alasan_dan_berikutnya() -> None:
    events = macro.normalisasi([_ev("CPI", +1200), _ev("NFP", +86400)])
    d = macro.ringkas(events, sekarang=NOW, jendela_menit=60)
    assert d["stand_down"] is True
    assert d["alasan"][0]["title"] == "CPI"
    assert [e["title"] for e in d["berikutnya"]] == ["CPI", "NFP"]


def test_snapshot_pakai_cache_segar(tmp_path) -> None:
    p = tmp_path / "cache" / macro.CACHE_NAME
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps({"diambil_epoch": NOW - 60, "events": macro.normalisasi([_ev("CPI", +1800)])}),
        encoding="utf-8",
    )
    d = macro.MacroCollector().snapshot(tmp_path, sekarang=NOW)
    assert d["tersedia"] is True and d["stand_down"] is True
    assert d["dari_cache_mnt"] is None  # segar, bukan basi


def test_snapshot_jatuh_ke_cache_basi_saat_sumber_mati(tmp_path) -> None:
    """Aturan rumah: sumber mati → data terakhir + umurnya, bukan error kosong."""
    p = tmp_path / "cache" / macro.CACHE_NAME
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps({"diambil_epoch": NOW - 8 * 3600, "events": macro.normalisasi([_ev("FOMC", +1800)])}),
        encoding="utf-8",
    )

    class Putus:
        def get(self, *a, **k):
            raise ConnectionError("mati")

    d = macro.MacroCollector(client=Putus()).snapshot(tmp_path, sekarang=NOW)
    assert d["tersedia"] is True
    assert d["stand_down"] is True
    assert d["dari_cache_mnt"] == 480.0
    assert "ConnectionError" in (d["error"] or "")


def test_snapshot_tanpa_cache_error_tetap_error(tmp_path) -> None:
    """Jangan mengarang: tanpa cache dan sumber mati, hasilnya error."""

    class Putus:
        def get(self, *a, **k):
            raise ConnectionError("mati")

    d = macro.MacroCollector(client=Putus()).snapshot(tmp_path, sekarang=NOW)
    assert d["tersedia"] is False
    assert "ConnectionError" in d["error"]


def test_snapshot_segar_dihitung_dari_sekarang_nyata(tmp_path) -> None:
    """Cache dengan umur 1 detik harus dianggap segar apa pun jam dindingnya."""
    p = tmp_path / "cache" / macro.CACHE_NAME
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"diambil_epoch": time.time() - 1, "events": []}), encoding="utf-8")
    d = macro.MacroCollector().snapshot(tmp_path)
    assert d["tersedia"] is True and d["jumlah"] == 0
