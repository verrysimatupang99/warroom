"""Tes pembaca laporan MT5 dan hitung sensitivitas biaya."""

import importlib.util
import pathlib

_src = pathlib.Path(__file__).resolve().parents[1] / "sensitivitas_biaya.py"
spec = importlib.util.spec_from_file_location("sensitivitas_biaya", _src)
sb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sb)

# Laporan mini dengan bentuk yang sama seperti keluaran MT5:
# UTF-16LE, baris header 13 kolom, deal 'in' profit 0, deal 'out' merealisasi.
LAPORAN = """<html><body><table>
<tr><td>Strategy Tester Report</td></tr>
<tr>
  <td>Time</td><td>Deal</td><td>Symbol</td><td>Type</td><td>Direction</td>
  <td>Volume</td><td>Price</td><td>Order</td><td>Commission</td><td>Swap</td>
  <td>Profit</td><td>Balance</td><td>Comment</td>
</tr>
<tr>
  <td>2024.01.02 10:00:00</td><td>1</td><td></td><td>balance</td><td></td>
  <td></td><td></td><td></td><td>0.00</td><td>0.00</td>
  <td>10 000.00</td><td>10 000.00</td><td></td>
</tr>
<tr>
  <td>2024.01.02 11:00:00</td><td>2</td><td>XAUUSDm</td><td>buy</td><td>in</td>
  <td>0.01</td><td>2000.000</td><td>2</td><td>0.00</td><td>0.00</td>
  <td>0.00</td><td>10 000.00</td><td></td>
</tr>
<tr>
  <td>2024.01.02 12:00:00</td><td>3</td><td>XAUUSDm</td><td>sell</td><td>out</td>
  <td>0.01</td><td>2005.000</td><td>3</td><td>0.00</td><td>0.00</td>
  <td>5.00</td><td>10 005.00</td><td></td>
</tr>
<tr>
  <td>2024.01.03 09:00:00</td><td>4</td><td>XAUUSDm</td><td>buy</td><td>in</td>
  <td>0.01</td><td>2010.000</td><td>4</td><td>0.00</td><td>0.00</td>
  <td>0.00</td><td>10 005.00</td><td></td>
</tr>
<tr>
  <td>2024.01.03 10:00:00</td><td>5</td><td>XAUUSDm</td><td>sell</td><td>out</td>
  <td>0.01</td><td>2008.000</td><td>5</td><td>0.00</td><td>0.00</td>
  <td>-2.00</td><td>10 003.00</td><td></td>
</tr>
</table></body></html>
"""


def tulis(tmp_path, teks=LAPORAN):
    p = tmp_path / "laporan.htm"
    p.write_bytes(teks.encode("utf-16"))
    return p


def test_hanya_deal_penutup_yang_dibaca(tmp_path):
    deals = sb.baca(tulis(tmp_path))
    assert len(deals) == 2
    assert [d["profit"] for d in deals] == [5.0, -2.0]


def test_volume_terbaca(tmp_path):
    deals = sb.baca(tulis(tmp_path))
    assert all(d["volume"] == 0.01 for d in deals)


def test_ringkas_menghitung_net_dan_pf(tmp_path):
    r = sb.ringkas(sb.baca(tulis(tmp_path)))
    assert r["trade"] == 2
    assert r["net"] == 3.0
    assert r["pf"] == 2.5


def test_biaya_mengurangi_net(tmp_path):
    deals = sb.baca(tulis(tmp_path))
    tanpa = sb.ringkas(deals)["net"]
    dengan = sb.ringkas(deals, slippage_fill=0.5, komisi_lot=7.0)["net"]
    assert dengan < tanpa


def test_laporan_utf8_juga_terbaca(tmp_path):
    p = tmp_path / "lain.htm"
    p.write_bytes(LAPORAN.encode("utf-8"))
    assert len(sb.baca(p)) == 2


def test_swap_terbaca_dan_rekonsiliasi(tmp_path):
    """Kolom Swap harus terbaca: net MT5 = profit + komisi + swap."""
    laporan = LAPORAN.replace(
        "<td>0.00</td><td>0.00</td>\n  <td>5.00</td>",
        "<td>0.00</td><td>-1.50</td>\n  <td>5.00</td>",
    )
    assert laporan != LAPORAN, "fixture tidak berubah, penanda swap tidak ketemu"
    deals = sb.baca(tulis(tmp_path, laporan))
    assert deals[0]["swap"] == -1.5
    net = sum(d["profit"] for d in deals) + sum(d["komisi"] for d in deals) + sum(d["swap"] for d in deals)
    assert net == 1.5  # 5.00 - 2.00 - 1.50


def test_ke_angka_format_ribuan():
    assert sb.ke_angka("1 234.56") == 1234.56
    assert sb.ke_angka("-16.12") == -16.12
    assert sb.ke_angka("") is None
    assert sb.ke_angka("abc") is None
