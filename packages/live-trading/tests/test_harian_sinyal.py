from __future__ import annotations

from live_trading.harian import sinyal_harian


def test_konfirmasi_dua_close():
    # Sinyal LONG hanya setelah 2 close di atas SMA berturut-turut.
    naik = [100.0 - i for i in range(60)]          # turun 60 hari
    naik += [100.0, 110.0, 120.0, 130.0]           # naik 4 hari
    k = sinyal_harian(naik, sma_n=50, confirm_closes=2)
    # close pertama di atas SMA: streak=1 → belum; streak 2 → LONG.
    keputusan = [d for d in k["keputusan"] if d["ke"] == "LONG"]
    assert keputusan, "harus ada satu keputusan ke LONG"


def test_whipsaw_satu_close_tidak_ubah_status():
    # Satu close di atas SMA lalu satu lagi di bawah → tetap FLAT (konfirmasi=2).
    c = [120.0 if i % 2 == 0 else 100.0 for i in range(60)]  # bolak-balik
    k = sinyal_harian(c, sma_n=20, confirm_closes=2)
    assert k["status"] == "FLAT"


def test_tanpa_lookahead_pada_keputusan_terakhir():
    # SMA pada keputusan terakhir TIDAK BOLEH mencantumkan close hari itu.
    c = [100.0] * 60 + [80.0]  # satu close di bawah di akhir
    k = sinyal_harian(c, sma_n=50, confirm_closes=1)
    assert k["status"] == "FLAT"
    k2 = sinyal_harian([100.0] * 60 + [120.0], sma_n=50, confirm_closes=1)
    assert k2["keputusan"][-1]["i"] == len(c) - 1


def test_data_kurang_aman():
    k = sinyal_harian([100.0, 101.0], sma_n=50, confirm_closes=1)
    assert k.get("kurang_data") and k["status"] == "FLAT"
