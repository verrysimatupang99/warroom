"""Tes tracker DoD forward test — membaca CSV, tanpa menebak."""

from __future__ import annotations

from datetime import date

from warroom_core.forwardtest import ringkas, tanggal_deal, teks

DEALS_HEADER = (
    "ts,iso,ticket,position,symbol,side,volume,open_time,open_price,close_time,"
    "close_price,profit,swap,commission,net,magic,comment\n"
)
FILLS_HEADER = (
    "ts,iso,ticket,symbol,side,volume,price_requested,price_filled,slippage_pts,"
    "spread_pts,latency_ms,retcode,execution_mode,open_positions,equity,sl,tp\n"
)


def _tulis(path, header: str, baris: list[str]) -> None:
    path.write_text(header + "".join(b + "\n" for b in baris), encoding="utf-8")


def _deal(
    ticket: int,
    *,
    position: int = 0,
    close_time: str = "2026.10.30 08:15:00",
    profit: float = 10.0,
    swap: float = -1.0,
    commission: float = -0.5,
    net: str = "8.50",
) -> str:
    return (
        f"1793000000,{close_time},{ticket},{position or ticket},XAUUSDm,SELL,0.01,"
        f"2026.10.30 08:00:00,4000.0,{close_time},3990.0,{profit},{swap},{commission},{net},0,"
    )


def _fill(ticket: int) -> str:
    return (
        f"1793000000,2026-10-30 08:00:00,{ticket},XAUUSDm,SELL,0.01,4000.0,4000.1,1.0,"
        "20,120,0,0,1,1000.0,4010.0,3980.0"
    )


def test_tanpa_berkas_bukan_angka_karangan(tmp_path) -> None:
    hasil = ringkas(
        deals_path=tmp_path / "deals.csv",
        fills_path=tmp_path / "fills.csv",
        hari_ini=date(2026, 10, 30),
    )
    assert hasil["trade_tertutup"] == 0
    assert hasil["net_usd"] == 0.0
    assert hasil["sumber"]["deals_ada"] is False
    assert hasil["sumber"]["fills_ada"] is False
    assert hasil["status"] == "berjalan"
    assert "belum ada deal tertutup" in teks(hasil)


def test_deal_dan_fill_cocok_lewat_position(tmp_path) -> None:
    _tulis(tmp_path / "deals.csv", DEALS_HEADER, [_deal(9001, position=555)])
    _tulis(tmp_path / "fills.csv", FILLS_HEADER, [_fill(555)])
    hasil = ringkas(
        deals_path=tmp_path / "deals.csv",
        fills_path=tmp_path / "fills.csv",
        hari_ini=date(2026, 10, 30),
    )
    assert hasil["trade_tertutup"] == 1
    assert hasil["net_usd"] == 8.5
    assert (hasil["menang"], hasil["kalah"], hasil["seri"]) == (1, 0, 0)
    assert hasil["deal_hari_ini"] == 1
    assert hasil["fill_belum_deal"] == 0
    assert hasil["deal_tanpa_fill"] == 0


def test_fill_belum_deal_dan_deal_tanpa_fill_dipisah(tmp_path) -> None:
    _tulis(tmp_path / "deals.csv", DEALS_HEADER, [_deal(9002, position=777)])
    _tulis(tmp_path / "fills.csv", FILLS_HEADER, [_fill(555)])
    hasil = ringkas(
        deals_path=tmp_path / "deals.csv",
        fills_path=tmp_path / "fills.csv",
        hari_ini=date(2026, 10, 30),
    )
    assert hasil["fill_belum_deal"] == 1
    assert hasil["fill_belum_deal_tiket"] == ["555"]
    assert hasil["deal_tanpa_fill"] == 1
    assert hasil["deal_tanpa_fill_tiket"] == ["777"]


def test_tiket_ganda_dihitung_sekali(tmp_path) -> None:
    _tulis(
        tmp_path / "deals.csv",
        DEALS_HEADER,
        [_deal(9003), _deal(9003)],
    )
    hasil = ringkas(
        deals_path=tmp_path / "deals.csv",
        fills_path=tmp_path / "fills.csv",
        hari_ini=date(2026, 10, 30),
    )
    assert hasil["trade_tertutup"] == 1


def test_net_dihitung_dari_profit_swap_komisi_bila_kolom_net_kosong(tmp_path) -> None:
    _tulis(tmp_path / "deals.csv", DEALS_HEADER, [_deal(9004, net="")])
    hasil = ringkas(
        deals_path=tmp_path / "deals.csv",
        fills_path=tmp_path / "fills.csv",
        hari_ini=date(2026, 10, 30),
    )
    assert hasil["net_usd"] == 8.5


def test_status_selesai_dan_lewat_batas(tmp_path) -> None:
    baris = [_deal(9100 + i) for i in range(20)]
    _tulis(tmp_path / "deals.csv", DEALS_HEADER, baris)
    selesai = ringkas(
        deals_path=tmp_path / "deals.csv",
        fills_path=tmp_path / "fills.csv",
        hari_ini=date(2026, 10, 30),
    )
    assert selesai["status"] == "selesai"
    assert "target 20 trade tercapai" in selesai["catatan"]

    kosong = tmp_path / "kosong.csv"
    _tulis(kosong, DEALS_HEADER, [])
    lewat = ringkas(
        deals_path=kosong,
        fills_path=tmp_path / "fills.csv",
        hari_ini=date(2026, 12, 5),
    )
    assert lewat["status"] == "lewat-batas"
    assert lewat["hari_berjalan"] == 37


def test_tanggal_deal_dari_close_time_atau_iso() -> None:
    assert tanggal_deal({"close_time": "2026.10.30 08:15:00"}) == date(2026, 10, 30)
    assert tanggal_deal({"close_time": "", "iso": "2026-11-01 09:00:00"}) == date(2026, 11, 1)
    assert tanggal_deal({"close_time": "bukan tanggal"}) is None
