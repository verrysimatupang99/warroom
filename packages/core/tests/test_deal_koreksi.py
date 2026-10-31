"""Tes correction log deal: terbaru menang, baris asli tidak diubah."""

from __future__ import annotations

from warroom_core.deal_koreksi import baca_koreksi, terapkan


def _k(ticket: str, field: str, old: str, new: str, ts: str = "2026-10-30T08:00:00+00:00") -> dict:
    return {
        "ts": ts,
        "ticket": ticket,
        "field": field,
        "old": old,
        "new": new,
        "reason": "koreksi uji",
        "source": "uji",
    }


def test_koreksi_terbaru_menang_dan_baris_asli_utuh() -> None:
    asli = [{"ticket": "1", "net": "8.50", "profit": "10.00"}]
    hasil = terapkan(asli, [_k("1", "net", "8.50", "9.00"), _k("1", "net", "9.00", "9.50")])
    assert hasil[0]["net"] == "9.50"
    assert asli[0]["net"] == "8.50", "baris asli tidak boleh berubah"
    assert hasil[0]["_koreksi"][-1]["new"] == "9.50"


def test_koreksi_ticket_lain_diabaikan() -> None:
    hasil = terapkan([{"ticket": "1", "net": "8.50"}], [_k("2", "net", "8.50", "9.00")])
    assert hasil[0]["net"] == "8.50"
    assert "_koreksi" not in hasil[0]


def test_field_tidak_ada_diabaikan() -> None:
    hasil = terapkan([{"ticket": "1", "net": "8.50"}], [_k("1", "tidak_ada", "", "x")])
    assert "_koreksi" not in hasil[0]


def test_baca_koreksi_kosong(tmp_path) -> None:
    assert baca_koreksi(tmp_path / "tidak-ada.csv") == []
