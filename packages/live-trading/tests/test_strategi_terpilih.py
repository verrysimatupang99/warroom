"""Tes pemilihan strategi per market + dompet terpisah (poin 3 & 4).

Prinsip yang ditegakkan:
1. Strategi dengan bukti negatif (sum_r < 0, n cukup) -> `dihentikan`, TIDAK dijalankan.
2. Strategi dengan sampel < MIN_SAMPEL_AKTIF -> `belum-terbukti`, bukan dipaksa `aktif`.
3. Satu strategi = satu dompet ID unik (poin 4: wallet berbeda per strategi).
4. Market dengan metrik bukan-R tidak diberi status `dihentikan` (jujur, bukan salah label).
"""

from __future__ import annotations

from live_trading import strategi_terpilih as st


def test_strategi_merugi_dihentikan():
    """ARA_HUNTER (-139R) harus dihentikan, bukan diaktifkan."""
    idx = {s.nama: s for s in st.PILIHAN["idx"]}
    assert idx["ARA_HUNTER"].status == "dihentikan"
    assert "ARA_HUNTER" in [s.nama for s in st.PILIHAN["idx"] if s.status == "dihentikan"]


def test_strategi_terbaik_aktif():
    """BSJP_STRONG (+20,51R, n=26) harus aktif."""
    idx = {s.nama: s for s in st.PILIHAN["idx"]}
    assert idx["BSJP_STRONG"].status == "aktif"


def test_sampel_kecil_bukan_aktif():
    """watchlist-sync n=5 -> belum-terbukti (bukan aktif walau +3,84R)."""
    crypto = {s.nama: s for s in st.PILIHAN["crypto"]}
    assert crypto["watchlist-sync"].status == "belum-terbukti"


def test_dompet_terpisah_per_strategi():
    """IDX punya 4 strategi -> 4 dompet dengan dompet_id unik (poin 4)."""
    dompet = st.dompet_strategi("idx")
    assert len(dompet) == 4
    ids = [d["dompet_id"] for d in dompet]
    assert len(ids) == len(set(ids)), "dompet_id harus unik"
    for d in dompet:
        assert d["saldo_awal_idr"] == st.WALLET_IDR
        assert d["market"] == "idx"


def test_market_bukan_r_tidak_dihentikan():
    """LP (P&L %, bukan R) -> belum-terbukti, bukan dihentikan."""
    gmgn = {s.nama: s for s in st.PILIHAN["gmgn"]}
    lp = gmgn["LP Terukur (Meteora DAMM v2)"]
    assert lp.status == "belum-terbukti"


def test_strategi_aktif_kecualikan_yang_dihentikan():
    """strategi_aktif() tak memuat yang dihentikan."""
    aktif = [s.nama for s in st.strategi_aktif("idx")]
    assert "ARA_HUNTER" not in aktif
    assert "BSJP_STRONG" in aktif


def test_ringkas_konsisten():
    """Ringkasan: total dompet = jumlah seluruh strategi; dihentikan konsisten."""
    r = st.ringkas_pilihan()
    total = sum(len(d) for d in st.PILIHAN.values())
    assert r["total_dompet"] == total
    assert "ARA_HUNTER" in r["pasar"]["idx"]["dihentikan"]
