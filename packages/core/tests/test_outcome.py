"""Regresi: ekstraksi hasil pasar dari dataset recorder (P1 lanjutan, 5 Okt 2026).

Yang dikunci — semuanya adalah bug nyata yang ditemukan saat menguji modul ini:
1. Gamma mengirim `outcomes`/`outcomePrices` sebagai STRING JSON, bukan array. Parser yang
   mengiterasi string mentah membaca per karakter dan selalu gagal.
2. Pasar yang BELUM selesai (mis. 0.505/0.495) tidak boleh dilabeli — itu mengarang hasil.
3. Keputusan yang sengaja DITOLAK strategi tidak boleh ikut dihitung: pada satu run
   produksi, itu menghasilkan win-rate palsu 62,6% vs 14,8% yang sebenarnya.
4. Resolusi datang SETELAH keputusannya dan berkas dirotasi — pelabelan harus dua lintasan.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

from warroom_core import outcome


def _tulis(path: Path, baris: list[dict]) -> None:
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        for b in baris:
            fh.write(json.dumps(b) + "\n")


def _gamma(slug: str, outcomes: str, harga: str, *, closed: bool, status: str) -> dict:
    """Event http gamma dengan field yang meniru bentuk ASLI (string JSON)."""
    return {
        "kind": "http",
        "url": "https://gamma-api.polymarket.com/events?slug=" + slug,
        "body": [{
            "slug": slug,
            "closed": closed,
            "markets": [{
                "closed": closed,
                "umaResolutionStatus": status,
                "outcomes": outcomes,      # SENGAJA string, seperti aslinya
                "outcomePrices": harga,    # SENGAJA string
            }],
        }],
    }


def _decision(coin: str, wts: int, side: str, reason: str = "quote_eligible") -> dict:
    return {"kind": "decision", "coin": coin, "wts": wts, "side": side, "reason": reason,
            "partition": "holdout", "token": "t"}


def test_parse_string_json_dan_pemenang(tmp_path: Path) -> None:
    """Bug 1: field string JSON. ["0","1"] → Down menang."""
    f = tmp_path / "events-0000.jsonl.gz"
    _tulis(f, [_gamma("btc-updown-5m-100", '["Up", "Down"]', '["0", "1"]', closed=True, status="resolved")])
    h = outcome.read_outcome(f)
    assert ("btc", 100) in h
    assert h[("btc", 100)].menang == "Down"
    assert h[("btc", 100)].teresolusi is True


def test_pasar_belum_selesai_tidak_dilabeli(tmp_path: Path) -> None:
    """Bug 2: pasar masih jalan (0.505/0.495) tidak boleh jadi label."""
    f = tmp_path / "events-0000.jsonl.gz"
    _tulis(f, [
        _gamma("btc-updown-5m-200", '["Up", "Down"]', '["0.505", "0.495"]', closed=False, status=""),
        _gamma("btc-updown-5m-201", '["Up", "Down"]', '["1", "0"]', closed=True, status="resolved"),
    ])
    h = outcome.read_outcome(f)
    assert ("btc", 200) not in h, "pasar yang belum selesai tidak boleh punya label"
    assert ("btc", 201) in h and h[("btc", 201)].menang == "Up"


def test_dua_lintasan_resolusi_di_berkas_lain(tmp_path: Path) -> None:
    """Bug 4: resolusi ada di berkas LAIN dari keputusannya."""
    (tmp_path / "events-0000.jsonl.gz").write_bytes(b"")
    _tulis(tmp_path / "events-0000.jsonl.gz", [_decision("btc", 300, "Up")])
    _tulis(tmp_path / "events-0001.jsonl.gz", [
        _gamma("btc-updown-5m-300", '["Up", "Down"]', '["1", "0"]', closed=True, status="resolved")
    ])
    r = outcome.summarize_dataset(tmp_path)
    assert r["hasil_pasar"] == 1
    assert r["keputusan_berlabel"] == 1
    assert r["menang"] == 1


def test_keputusan_ditolak_tidak_ikut_dihitung(tmp_path: Path) -> None:
    """Bug 3 — penjaga terpenting. Keputusan `outside_window` yang kebetulan menang tidak
    boleh menaikkan win-rate; hanya `quote_eligible` yang dihitung."""
    f = tmp_path / "events-0000.jsonl.gz"
    _tulis(f, [
        _decision("btc", 400, "Up", reason="quote_eligible"),    # pasar 400 → Up menang
        _decision("btc", 401, "Up", reason="quote_eligible"),    # pasar 401 → Down menang (kalah)
        _decision("btc", 402, "Up", reason="outside_window"),   # menang tapi ditolak
        _decision("btc", 403, "Up", reason="empty_book"),       # menang tapi ditolak
    ])
    _tulis(tmp_path / "events-0001.jsonl.gz", [
        _gamma("btc-updown-5m-400", '["Up","Down"]', '["1","0"]', closed=True, status="resolved"),
        _gamma("btc-updown-5m-401", '["Up","Down"]', '["0","1"]', closed=True, status="resolved"),
        _gamma("btc-updown-5m-402", '["Up","Down"]', '["1","0"]', closed=True, status="resolved"),
        _gamma("btc-updown-5m-403", '["Up","Down"]', '["1","0"]', closed=True, status="resolved"),
    ])
    r = outcome.summarize_dataset(tmp_path)
    assert r["keputusan_semua_alasan"] == 4
    assert r["keputusan_berlabel"] == 2, "hanya quote_eligible yang dihitung"
    assert r["menang"] == 1 and r["kalah"] == 1
    assert r["win_rate_layak"] == 0.5
    # angka campuran (semua alasan) = 3/4 menang — itulah yang menyesatkan
    assert r["win_rate_palsu_semua_alasan"] == 0.75


def test_ringkas_dataset_kosong(tmp_path: Path) -> None:
    assert "error" in outcome.summarize_dataset(tmp_path)
