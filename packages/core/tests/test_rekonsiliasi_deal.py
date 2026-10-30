"""Tes rekonsiliasi statement MT5 vs deals.csv (US2.1)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from warroom_core.rekonsiliasi_deal import (
    baca_statement,
    bandingkan,
    ke_angka,
    teks,
)

HEADER = (
    "<tr>"
    "<td>Time</td><td>Deal</td><td>Symbol</td><td>Type</td><td>Direction</td>"
    "<td>Volume</td><td>Price</td><td>Order</td><td>Commission</td><td>Swap</td>"
    "<td>Profit</td><td>Balance</td>"
    "</tr>"
)


def _row(
    ticket: int | str,
    *,
    direction: str = "out",
    time: str = "2026.10.30 08:15:00",
    symbol: str = "XAUUSDm",
    type_: str = "sell",
    volume: str = "0.01",
    price: str = "3990.0",
    commission: str = "-0.50",
    swap: str = "-1.00",
    profit: str = "10.00",
) -> str:
    return (
        "<tr>"
        f"<td>{time}</td><td>{ticket}</td><td>{symbol}</td><td>{type_}</td>"
        f"<td>{direction}</td><td>{volume}</td><td>{price}</td><td>1</td>"
        f"<td>{commission}</td><td>{swap}</td><td>{profit}</td><td>1000</td>"
        "</tr>"
    )


def _statement(path: Path, rows: list[str], *, encoding: str = "utf-16") -> Path:
    html = f"<html><body><table>{HEADER}{''.join(rows)}</table></body></html>"
    path.write_bytes(html.encode(encoding))
    return path


def _deal(ticket: int | str, *, net: str = "8.50", iso: str = "2026-10-30 08:15:00") -> dict:
    return {
        "ticket": str(ticket),
        "iso": iso,
        "close_time": iso,
        "symbol": "XAUUSDm",
        "net": net,
        "profit": "10.00",
        "swap": "-1.00",
        "commission": "-0.50",
    }


def test_parser_utf16_hanya_out_dan_net_lengkap(tmp_path) -> None:
    path = _statement(
        tmp_path / "s.htm",
        [
            _row(100, direction="in", profit="0.00", swap="0.00", commission="0.00"),
            _row(101),
        ],
    )
    hasil = baca_statement(path)
    assert len(hasil) == 1, "baris 'in' tidak merealisasi profit dan harus diabaikan"
    assert hasil[0]["ticket"] == "101"
    assert hasil[0]["iso"] == "2026-10-30 08:15:00"
    assert hasil[0]["net"] == 8.5
    assert hasil[0]["sumber"] == "mt5_statement"


def test_parser_utf8_juga_terbaca(tmp_path) -> None:
    path = _statement(tmp_path / "s.htm", [_row(102)], encoding="utf-8")
    assert [d["ticket"] for d in baca_statement(path)] == ["102"]


def test_ke_angka_gaya_indonesia_dan_amerika() -> None:
    assert ke_angka("1 234,56") == 1234.56
    assert ke_angka("1,234.56") == 1234.56
    assert ke_angka("-0,50") == -0.5
    assert ke_angka("bukan angka") is None
    assert ke_angka(None) is None


def test_bandingkan_cocok(tmp_path) -> None:
    st = baca_statement(_statement(tmp_path / "s.htm", [_row(101)]))
    hasil = bandingkan(st, [_deal(101)])
    assert hasil["status"] == "cocok"
    assert hasil["cocok"] == 1
    assert hasil["selisih"] == []
    assert hasil["net_statement_usd"] == 8.5
    assert hasil["net_deals_usd"] == 8.5


def test_selisih_di_atas_toleransi_dilaporkan(tmp_path) -> None:
    st = baca_statement(_statement(tmp_path / "s.htm", [_row(101)]))
    hasil = bandingkan(st, [_deal(101, net="8.52")])
    assert hasil["status"] == "selisih"
    assert hasil["cocok"] == 0
    assert hasil["selisih"] == [
        {
            "ticket": "101",
            "symbol": "XAUUSDm",
            "net_statement": 8.5,
            "net_deals": 8.52,
            "selisih": 0.02,
        }
    ]


def test_selisih_di_bawah_toleransi_dianggap_cocok(tmp_path) -> None:
    st = baca_statement(_statement(tmp_path / "s.htm", [_row(101)]))
    hasil = bandingkan(st, [_deal(101, net="8.51")])
    assert hasil["status"] == "cocok", "selisih 0,01 masih dalam toleransi default"


def test_hanya_di_satu_sisi_dilaporkan(tmp_path) -> None:
    st = baca_statement(_statement(tmp_path / "s.htm", [_row(101), _row(102)]))
    hasil = bandingkan(st, [_deal(101), _deal(999)])
    assert [r["ticket"] for r in hasil["hanya_statement"]] == ["102"]
    assert [r["ticket"] for r in hasil["hanya_deals"]] == ["999"]
    assert hasil["status"] == "selisih"


def test_filter_tanggal_hanya_membandingkan_periode(tmp_path) -> None:
    st = baca_statement(
        _statement(
            tmp_path / "s.htm",
            [_row(101), _row(102, time="2026.11.02 08:15:00")],
        )
    )
    deals = [_deal(101), _deal(102, iso="2026-11-02 08:15:00")]
    hasil = bandingkan(st, deals, sejak=date(2026, 11, 1))
    assert hasil["n_statement"] == 1
    assert hasil["n_deals"] == 1
    assert hasil["status"] == "cocok"


def test_duplikat_tiket_dilaporkan(tmp_path) -> None:
    st = baca_statement(_statement(tmp_path / "s.htm", [_row(101), _row(101)]))
    hasil = bandingkan(st, [_deal(101), _deal(101)])
    assert hasil["duplikat_statement"] == ["101"]
    assert hasil["duplikat_deals"] == ["101"]
    assert hasil["status"] == "selisih"


def test_net_deals_dihitung_dari_komponen_bila_kolom_net_kosong(tmp_path) -> None:
    st = baca_statement(_statement(tmp_path / "s.htm", [_row(101)]))
    deal = _deal(101, net="")
    hasil = bandingkan(st, [deal])
    assert hasil["net_deals_usd"] == 8.5
    assert hasil["status"] == "cocok"


def test_teks_menyebut_selisih_dan_tiket(tmp_path) -> None:
    st = baca_statement(_statement(tmp_path / "s.htm", [_row(101)]))
    hasil = bandingkan(st, [_deal(101, net="8.52")])
    keluaran = teks(hasil)
    assert "SELISIH ticket=101" in keluaran
    assert "Status    : SELISIH" in keluaran
