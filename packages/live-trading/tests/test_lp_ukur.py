"""Ukur peluang LP dengan jujur — tanpa jaringan.

Prinsip yang diuji: apa yang TIDAK bisa dihitung dari data pool harus ditulis "belum diketahui",
bukan ditebak. Klaim LP dari media sosial selalu menyebut % tanpa jendela waktu, fee tier, atau
pembanding hold — di sini itu justru dinyatakan eksplisit.
"""

from __future__ import annotations

import time

from live_trading.collectors.dexscreen import select_pool, ukur_lp

SEKARANG = time.time()


def _pool(
    *,
    liq: float | None = 100_000,
    v24: float | None = 150_000,
    v6: float | None = 30_000,
    chg24: float | None = 5.0,
    chg6: float | None = 2.0,
    umur_jam: float = 24 * 10,
    label: str = "DYN2",
) -> dict:
    p: dict = {
        "labels": [label],
        "dexId": "meteora",
        "priceUsd": "0.0003",
        "liquidity": {"usd": liq} if liq is not None else {},
        "volume": {"h24": v24, "h6": v6} if v24 is not None else {},
        "priceChange": {"h24": chg24, "h6": chg6},
    }
    if umur_jam is not None:
        p["pairCreatedAt"] = int((SEKARANG - umur_jam * 3600) * 1000)
    return p


def test_menghitung_turnover_dan_umur() -> None:
    h = ukur_lp(_pool(liq=100_000, v24=150_000))
    assert h["turnover_24h"] == 1.5
    assert h["label_pool"] == "DYN2"
    assert h["umur_jam"] is not None and h["umur_jam"] > 200


def test_likuiditas_tipis_membuat_tidak_layak() -> None:
    h = ukur_lp(_pool(liq=5_000, v24=9_000))
    assert h["kualitas"] == "tipis"
    assert any("20.000" in c for c in h["catatan"])


def test_turnover_rendah_membuat_tidak_layak() -> None:
    h = ukur_lp(_pool(liq=100_000, v24=20_000))
    assert h["kualitas"] == "tipis"
    assert any("turnover" in c for c in h["catatan"])


def test_pool_baru_ditandai() -> None:
    h = ukur_lp(_pool(liq=100_000, v24=150_000, umur_jam=6))
    assert h["kualitas"] == "terlalu-baru"
    assert any("jam" in c for c in h["catatan"])


def test_pool_sehat_layak_ditinjau() -> None:
    h = ukur_lp(_pool(liq=100_000, v24=150_000, umur_jam=24 * 10, chg24=5.0))
    assert h["kualitas"] == "layak-ditinjau"


def test_harga_bergerak_keras_ditandai_sebagai_tekanan_il() -> None:
    h = ukur_lp(_pool(chg24=58.0))
    assert any("IL besar" in c for c in h["catatan"])


def test_selalu_menyatakan_yang_belum_diketahui() -> None:
    """Ini inti kejujurannya: fee APR & LP-vs-hold TIDAK pernah ditebak."""
    h = ukur_lp(_pool())
    gab = " ".join(h["catatan"])
    assert "fee APR nyata: belum diketahui" in gab
    assert "LP vs hold: belum diketahui" in gab


def test_data_kurang_tidak_menebak_nol() -> None:
    h = ukur_lp({"labels": ["DYN2"]})
    assert h["kualitas"] == "belum-cukup-data"
    assert h["liq_usd"] is None
    assert h["turnover_24h"] is None


def test_likuiditas_nol_tidak_membagi_nol() -> None:
    h = ukur_lp(_pool(liq=0, v24=1000))
    assert h["turnover_24h"] is None
    assert h["kualitas"] == "tipis"


def test_angka_rusak_dianggap_tidak_ada() -> None:
    h = ukur_lp(_pool(liq=None, v24=None))
    assert h["kualitas"] == "belum-cukup-data"


def test_contoh_nyata_bagspay_pool() -> None:
    """Angka pool BAGSPAY/SOL (DAMM v2) yang diambil 4 Okt: turnover 1,29x, harga 24j +58%."""
    h = ukur_lp(
        _pool(liq=81_137, v24=104_689, v6=25_839, chg24=58.28, chg6=8.52, umur_jam=24 * 5, label="DYN2")
    )
    assert h["kualitas"] == "layak-ditinjau"
    assert abs(h["turnover_24h"] - 1.29) < 0.01
    assert any("IL besar" in c for c in h["catatan"])  # +58%/24j memang tekanan IL


def test_pool_mati_likuiditas_besar_volume_nol() -> None:
    """Kasus nyata: satu pool BONK/USDC punya $50 juta likuiditas tapi volume $0,31/hari.

    Kalau hanya melihat likuiditas, pool ini tampak paling menarik — padahal LP di sini
    tidak menghasilkan fee apa pun. Karena itu penyaringan harus mengurutkan berdasarkan
    volume, bukan likuiditas.
    """
    h = ukur_lp(_pool(liq=50_394_585, v24=0.31))
    assert h["kualitas"] == "pool-mati"
    assert h["turnover_24h"] is not None and h["turnover_24h"] < 0.02
    assert any("tanpa menghasilkan fee" in c for c in h["catatan"])


def _pool_ringkas(alamat: str, liq: float, v24: float) -> dict:
    return {
        "pairAddress": alamat,
        "liquidity": {"usd": liq},
        "volume": {"h24": v24},
        "chainId": "solana",
    }


def test_urutkan_berdasarkan_volume_bukan_likuiditas() -> None:
    """Pool likuiditas $50 juta tapi volume ~nol TIDAK boleh menang atas pool yang aktif.

    Pool itu tetap ditampilkan (supaya kelihatan dan bisa belajar), tapi selalu di bawah —
    dan `ukur_lp` sudah menandainya `pool-mati`. Yang dibuang total hanya volume nol mutlak.
    """
    dari_cari = [
        _pool_ringkas("DEAD", 50_000_000, 0.31),  # likuiditas raksasa, volume hampir mati
        _pool_ringkas("HIDUP", 81_000, 104_000),  # likuiditas kecil, volume besar
    ]
    hasil = select_pool(dari_cari)
    assert hasil[0]["pairAddress"] == "HIDUP"
    assert [p["pairAddress"] for p in hasil] == ["HIDUP", "DEAD"]
    assert ukur_lp(hasil[1])["kualitas"] == "pool-mati"


def test_pool_tanpa_volume_dibuang() -> None:
    assert select_pool([_pool_ringkas("A", 10_000, 0)]) == []


def test_penyaringan_rantai() -> None:
    """Kata umum seperti "SOL" bisa dijawab pool SOL/USDC yang ada di Base — harus disaring."""
    campur = [
        {**_pool_ringkas("BASE1", 500_000, 900_000), "chainId": "base"},
        {**_pool_ringkas("SOL1", 81_000, 104_000), "chainId": "solana"},
    ]
    assert [p["pairAddress"] for p in select_pool(campur, rantai="solana")] == ["SOL1"]
    assert [p["pairAddress"] for p in select_pool(campur, rantai="base")] == ["BASE1"]
    assert len(select_pool(campur)) == 2  # tanpa penyaring = keduanya


def test_penyaringan_rantai_tidak_peka_huruf_besar_kecil() -> None:
    a = [_pool_ringkas("S1", 10_000, 5_000)]
    a[0]["chainId"] = "Solana"
    assert len(select_pool(a, rantai="solana")) == 1


def test_batas_jumlah_pool() -> None:
    banyak = [_pool_ringkas(f"P{i}", 10_000, 1_000 + i) for i in range(10)]
    hasil = select_pool(banyak, limit=3)
    assert [p["pairAddress"] for p in hasil] == ["P9", "P8", "P7"]
