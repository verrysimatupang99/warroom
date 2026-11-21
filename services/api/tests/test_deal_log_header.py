"""Guard header deals.csv — cegah korupsi saat header berkas lama beda skema.

Bug nyata 20 Nov 2026: deals.csv dibuat dengan header lama (11 kolom) lalu writer
baru menulis 21 kolom. 149 dari 248 baris terbaca bergeser (`account` berisi
timestamp, `strategy_version` berisi harga). Guard sekarang mengarsipkan berkas
dengan header lama dan mulai berkas baru dengan header kanonik.
"""
from __future__ import annotations

from warroom_api.routers import tencent


def _buat_lama(path, header: list[str], baris: str) -> None:
    path.write_text(",".join(header) + "\n" + baris + "\n", encoding="utf-8")


def test_header_lama_diarsipkan_dan_file_baru_dimulai(tmp_path, monkeypatch) -> None:
    p = tmp_path / "deals.csv"
    _buat_lama(p, ["ticket", "symbol"], "1,XAUUSDc")
    monkeypatch.setattr(tencent, "DEAL_LOG", p)

    assert tencent._pastikan_header_deal_log() is True
    assert not p.exists(), "berkas lama harus dipindah, bukan ditimpa"
    arsip = list(tmp_path.glob("deals.csv.lama-*"))
    assert len(arsip) == 1
    assert "1,XAUUSDc" in arsip[0].read_text()


def test_header_cocok_dipertahankan(tmp_path, monkeypatch) -> None:
    p = tmp_path / "deals.csv"
    _buat_lama(p, tencent._DEAL_HEADER, "1795182636,XAUUSDc")
    monkeypatch.setattr(tencent, "DEAL_LOG", p)

    assert tencent._pastikan_header_deal_log() is False
    assert p.exists()


def test_file_kosong_atau_tidak_ada_dianggap_baru(tmp_path, monkeypatch) -> None:
    kosong = tmp_path / "deals.csv"
    kosong.write_text("", encoding="utf-8")
    monkeypatch.setattr(tencent, "DEAL_LOG", kosong)
    assert tencent._pastikan_header_deal_log() is True

    tidak_ada = tmp_path / "deals-lain.csv"
    monkeypatch.setattr(tencent, "DEAL_LOG", tidak_ada)
    assert tencent._pastikan_header_deal_log() is True
