"""Tes sumber memecoin (empat venue @awsnumsignal). Tanpa jaringan.

Prinsip yang diuji:
  - venue dipetakan dari data nyata (chain + dexId), bukan ditebak dari nama;
  - Jup dinyatakan sebagai agregator, bukan venue palsu;
  - Stonkfun dinyatakan TIDAK tersedia, bukan dipalsukan;
  - urutan pakai volume (bukan likuiditas) — pelajaran penyaring LP;
  - setiap keluaran membawa label jujur kanal sumbernya;
  - cache menghormati kuota/kesegaran.
"""

from __future__ import annotations

from pathlib import Path

from live_trading.collectors.memecoin import (
    LABEL_JUJUR,
    TIDAK_TERSEDIA,
    VENUE,
    klasifikasi_venue,
    select_venue,
    skrining,
)


def _p(chain: str, dex: str, liq: float, v24: float, alamat: str = "A", base: str = "TOK") -> dict:
    return {
        "chainId": chain, "dexId": dex, "pairAddress": alamat,
        "baseToken": {"symbol": base}, "quoteToken": {"symbol": "SOL"},
        "liquidity": {"usd": liq}, "volume": {"h24": v24},
        "priceChange": {"h24": 5.0}, "pairCreatedAt": 1_700_000_000_000,
    }


def test_klasifikasi_venue_dari_data_nyata() -> None:
    assert klasifikasi_venue("solana", "pumpfun") == "pumpfun"
    assert klasifikasi_venue("solana", "pumpswap") == "pumpfun"
    assert klasifikasi_venue("robinhood", "uniswap") == "robinhood"
    assert klasifikasi_venue("robinhood", "flapsh") == "robinhood"
    assert klasifikasi_venue("solana", "meteora") == "jup"
    assert klasifikasi_venue("solana", "raydium") == "jup"


def test_venue_lain_tidak_dipaksa_masuk() -> None:
    assert klasifikasi_venue("ethereum", "uniswap") is None  # uniswap ETH bukan Robinhood
    assert klasifikasi_venue("bsc", "pancakeswap") is None
    assert klasifikasi_venue(None, None) is None


def test_venuemap_konsisten_dengan_klasifikasi() -> None:
    for nama, (chain, dexs) in VENUE.items():
        for d in dexs:
            assert klasifikasi_venue(chain, d) == nama


def test_himpunan_dexid_antar_venue_saling_lepas() -> None:
    """Invarian penting: satu dexId tidak boleh masuk dua venue.

    Kalau bocor, hasil klasifikasi bergantung urutan kamus — bug yang pernah lolos.
    """
    semua: list[str] = []
    for _, (_, dexs) in VENUE.items():
        semua.extend(dexs)
    assert len(semua) == len(set(semua)), f"dexId duplikat antar-venue: {semua}"


def test_pumpswap_milik_pumpfun_bukan_jup() -> None:
    assert klasifikasi_venue("solana", "pumpswap") == "pumpfun"


def test_pilih_venue_urut_volume_bukan_likuiditas() -> None:
    """Pool likuiditas raksasa tapi volume hampir nol TIDAK boleh menang.

    Pool itu tetap ikut (volumenya 0,5 > 0) supaya kelihatan, tapi selalu di bawah.
    Hanya volume nol mutlak yang dibuang.
    """
    pairs = [
        _p("solana", "pumpfun", liq=50_000_000, v24=0.5, alamat="MATI"),
        _p("solana", "pumpfun", liq=30_000, v24=900_000, alamat="HIDUP"),
    ]
    hasil = select_venue(pairs, "pumpfun")
    assert hasil[0]["pairAddress"] == "HIDUP"
    assert [x["pairAddress"] for x in hasil] == ["HIDUP", "MATI"]


def test_pilih_venue_membuang_volume_nol() -> None:
    pairs = [_p("solana", "pumpfun", liq=1_000_000, v24=0, alamat="BENAR-BENAR-MATI")]
    assert select_venue(pairs, "pumpfun") == []


def test_pilih_venue_membuang_yang_bukan_venue_itu() -> None:
    pairs = [_p("solana", "raydium", 1000, 5000), _p("solana", "pumpfun", 1000, 5000)]
    assert [x["dexId"] for x in select_venue(pairs, "pumpfun")] == ["pumpfun"]


def test_pilih_venue_batas_jumlah() -> None:
    pairs = [_p("solana", "pumpfun", 1000, 100 + i * 10, alamat=f"A{i}") for i in range(9)]
    assert len(select_venue(pairs, "pumpfun", limit=3)) == 3
    assert select_venue(pairs, "pumpfun", limit=3)[0]["pairAddress"] == "A8"


def test_pilih_venue_nama_tak_dikenal_kosong() -> None:
    assert select_venue([_p("solana", "pumpfun", 1, 1)], "tidak-ada") == []


def test_skrining_melabeli_tiap_venue(tmp_path: Path) -> None:
    def ambil(kata: str) -> dict:
        if kata == "pumpfun":
            return {"pairs": [_p("solana", "pumpfun", 20_000, 500_000, "P1", "PUMP")]}
        if kata == "robinhood":
            return {"pairs": [_p("robinhood", "uniswap", 40_000, 300_000, "R1", "HOOD")]}
        return {"pairs": [_p("solana", "meteora", 60_000, 200_000, "J1", "MET")]}

    out = skrining(tmp_path, ambil=ambil)
    assert out["total"] == 3
    assert out["venue"]["pumpfun"][0]["pasangan"] == "PUMP/SOL"
    assert out["venue"]["robinhood"][0]["rantai"] == "robinhood"
    assert out["venue"]["jup"][0]["dex"] == "meteora"


def test_setiap_keluaran_membawa_label_jujur(tmp_path: Path) -> None:
    """Cache harus unik per tes — path tetap membuat tes membaca cache basi dari run sebelumnya."""
    out = skrining(tmp_path, ambil=lambda k: {"pairs": []})
    assert LABEL_JUJUR in out["catatan"]
    assert any("stonkfun" in v.lower() for v in TIDAK_TERSEDIA.values())
    assert any("stonkfun" in c.lower() for c in out["catatan"])
    assert any("tidak bisa diverifikasi" in c or "tidak ada track record" in c for c in out["catatan"])


def test_jup_dinyatakan_sebagai_agregator(tmp_path: Path) -> None:
    out = skrining(tmp_path, ambil=lambda k: {"pairs": []})
    assert any("agregator" in c for c in out["catatan"])


def test_skrining_mencatat_venue_yang_gagal(tmp_path: Path) -> None:
    def ambil(kata: str) -> dict:
        if kata == "jup":
            raise RuntimeError("429")
        return {"pairs": [_p("solana", "pumpfun", 1000, 5000, f"X{kata}")]}

    out = skrining(tmp_path, ambil=ambil)
    assert any("jup" in g for g in out["galat"])
    assert out["venue"]["jup"] == []


def test_skrining_memakai_cache(tmp_path: Path) -> None:
    n = {"kali": 0}

    def ambil(kata: str) -> dict:
        n["kali"] += 1
        return {"pairs": []}

    skrining(tmp_path, ambil=ambil)
    pertama = n["kali"]
    skrining(tmp_path, ambil=ambil)
    assert n["kali"] == pertama  # panggilan kedua dari cache


def test_skrining_wajib_fungsi_ambil(tmp_path: Path) -> None:
    import pytest

    with pytest.raises(ValueError):
        skrining(tmp_path)


def test_pumpfun_likuiditas_tidak_tersedia_dinyatakan() -> None:
    """Fakta terverifikasi: DexScreener tidak melaporkan likuiditas pool pumpfun.

    Diuji di endpoint CARI dan DETAIL — keduanya `None`. Karena itu turnover tidak bisa dihitung,
    dan itu harus dinyatakan (`liq_tersedia: False`), bukan diam-diam jadi '—'.
    """
    def ambil(kata: str) -> dict:
        p = _p("solana", "pumpfun", 0, 500_000, "PF1")
        p["liquidity"] = {}  # DexScreener mengembalikan tanpa field usd
        return {"pairs": [p]}

    import tempfile
    from pathlib import Path as _P

    with tempfile.TemporaryDirectory() as td:
        out = skrining(_P(td), ambil=ambil)
    baris = out["venue"]["pumpfun"][0]
    assert baris["liq_tersedia"] is False
    assert baris["turnover_24h"] is None
    assert baris["vol_24h"] == 500_000  # volume tetap ada, jadi urutan tetap bisa
    assert any("pumpfun" in c and "likuiditas" in c for c in out["catatan"])
