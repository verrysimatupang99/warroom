"""Penjaga: paper-scan WAJIB memakai sumber kandidat yang sama dengan dashboard.

Temuan 6 Okt: job ini memindai `engine.scan(DEFAULT_PAIRS)` — 6 pair warisan — sehingga
kandidat yang SUDAH lolos gate dan SUDAH tercatat di `verdicts.jsonl` (192 izin dari 68
pair) tidak pernah dieksekusi. Akurasi crypto mandek di 6 trade karena trade-nya tidak
pernah dibuka. Kelas bug: "dua pemindaian berbeda hasil, satu untuk tampilan satu untuk
eksekusi" — perbedaan yang tidak terlihat siapa pun.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from warroom_worker.jobs import _kandidat_terbaru_dari_ledger


class _Stg:
    def __init__(self, state_dir: Path) -> None:
        self.state_dir = state_dir


def _tulis(state_dir: Path, baris: list[dict]) -> None:
    (state_dir / "verdicts.jsonl").write_text(
        "\n".join(json.dumps(b) for b in baris) + "\n", encoding="utf-8"
    )


def _row(pair: str, allowed: bool, menit_lalu: int, **kw) -> dict:
    ts = datetime.now(UTC) - timedelta(minutes=menit_lalu)
    return {
        "ts": ts.isoformat(),
        "pair": pair,
        "direction": "LONG",
        "allowed": allowed,
        "entry": 1.0,
        "sl": 0.9,
        "tp1": 1.2,
        "tp2": 1.4,
        **kw,
    }


def test_hanya_lolos_yang_diambil(tmp_path: Path):
    _tulis(tmp_path, [_row("AAAUSDT", True, 10), _row("BBBUSDT", False, 10)])
    rows = _kandidat_terbaru_dari_ledger(_Stg(tmp_path), jam_terakhir=6)
    assert [r["pair"] for r in rows] == ["AAAUSDT"]


def test_di_luar_jendela_dilewati(tmp_path: Path):
    _tulis(tmp_path, [_row("AAAUSDT", True, 10), _row("BBBUSDT", True, 600)])
    rows = _kandidat_terbaru_dari_ledger(_Stg(tmp_path), jam_terakhir=6)
    assert [r["pair"] for r in rows] == ["AAAUSDT"]


def test_duplikat_pair_diambil_terbaru(tmp_path: Path):
    _tulis(
        tmp_path,
        [
            _row("AAAUSDT", True, 100, entry=1.0),
            _row("AAAUSDT", True, 5, entry=2.0),
        ],
    )
    rows = _kandidat_terbaru_dari_ledger(_Stg(tmp_path), jam_terakhir=6)
    assert len(rows) == 1
    assert rows[0]["entry"] == 2.0


def test_baris_rusak_dan_ts_kacau_dilewati(tmp_path: Path):
    (tmp_path / "verdicts.jsonl").write_text(
        '{"bukan json lengkap"\n' + json.dumps(_row("AAAUSDT", True, 5)) + "\n"
        + json.dumps({"pair": "BBBBUSDT", "allowed": True, "ts": "bukan-tanggal"}) + "\n",
        encoding="utf-8",
    )
    rows = _kandidat_terbaru_dari_ledger(_Stg(tmp_path), jam_terakhir=6)
    assert [r["pair"] for r in rows] == ["AAAUSDT"]


def test_ledger_tidak_ada_mengembalikan_kosong(tmp_path: Path):
    assert _kandidat_terbaru_dari_ledger(_Stg(tmp_path), jam_terakhir=6) == []
