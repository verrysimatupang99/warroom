"""Regresi: fundamental.py — laporan keuangan IDX dari Arjum (6 Okt 2026).

Yang dikunci di sini adalah bentuk data NYATA yang ditemukan saat integrasi, bukan bentuk
yang gue harapkan. Dua di antaranya membuat laporan penuh terbaca kosong, dan satu membuat
angka mencurigakan lolos tanpa tanda:

1. Blok bisa berupa **angka langsung** (`"laba_bruto": 5234283000000.0`) ATAU dict
   bersarang (`{"total": ...}`). Versi pertama hanya menangani dict → seluruh blok angka
   terbaca None dan laporan yang penuh terlihat kosong.
2. EPS bersarang **dua lapis** dengan nama kunci panjang, dan harus memilih versi "dasar".
3. Bank tidak punya `laba_bruto`; itu bukan kegagalan, itu jawaban yang benar (None).
4. EPS di sumber bisa **tidak masuk akal** (BBRI 0,0001; TLKM 0,0). Nilainya dibiarkan
   apa adanya TAPI wajib bertanda — kalau tidak, PER jadi tak hingga dan terbaca
   "saham tak bernilai".
"""

from __future__ import annotations

from live_trading.fundamental import (
    JENIS_BANK,
    JENIS_UMUM,
    FundamentalEmiten,
    deteksi_jenis,
    read_fundamental,
)

# Bentuk nyata ANTM Q2 2026 (disederhanakan, nilai asli).
ANTM = {
    "stock_code": "ANTM",
    "report_type": "INCOME_STATEMENT",
    "count": 12,
    "items": [
        {
            "year": "2026",
            "quarter": "2",
            "label": "Q2 2026",
            "data": {
                "penjualan_dan_pendapatan_usaha": 33_390_942_000_000.0,
                "laba_bruto": 5_234_283_000_000.0,
                "laba_rugi": 3_248_746_000_000.0,
                "laba_rugi_per_saham": {
                    "laba_per_saham_dasar_diatribusikan_kepada_pemilik_entitas_induk": {
                        "laba_rugi_per_saham_dasar_dari_operasi_yang_dilanjutkan": 124.08,
                        "total": 124.08,
                    },
                    "laba_rugi_per_saham_dilusian": {"total": 124.08},
                },
            },
        }
    ],
}

# Bentuk nyata BBRI Q2 2026: bank, pendapatan bersarang, EPS mencurigakan.
BBRI = {
    "stock_code": "BBRI",
    "report_type": "INCOME_STATEMENT",
    "count": 12,
    "items": [
        {
            "year": "2026",
            "quarter": "2",
            "label": "Q2 2026",
            "data": {
                "pendapatan_dan_beban_operasional": {"total": 40_160_669_000_000.0},
                "laba_rugi": 15_550_000_000_000.0,
                "laba_rugi_per_saham": {
                    "laba_per_saham_dasar_diatribusikan_kepada_pemilik_entitas_induk": {
                        "total": 0.0001
                    }
                },
            },
        }
    ],
}


def test_blok_angka_langsung_terbaca() -> None:
    """Penjaga utama #1: blok berupa ANGKA tidak boleh terbaca None."""
    f = read_fundamental(ANTM)
    assert f.pendapatan == 33_390_942_000_000.0
    assert f.laba_bruto == 5_234_283_000_000.0
    assert f.laba_bersih == 3_248_746_000_000.0
    assert f.ada is True


def test_blok_dict_bersarang_terbaca() -> None:
    """Penjaga #1 sisi lain: blok dict bersarang juga harus terbaca."""
    f = read_fundamental(BBRI)
    assert f.pendapatan == 40_160_669_000_000.0
    assert f.laba_bersih == 15_550_000_000_000.0


def test_eps_bersarang_dua_lapis() -> None:
    """Penjaga #2: EPS harus diambil dari sub-blok 'dasar', bukan dari dict terluar."""
    assert read_fundamental(ANTM).eps == 124.08


def test_bank_tidak_punya_laba_bruto_dan_itu_benar() -> None:
    """Penjaga #3: None bukan kegagalan — bank memang tidak punya laba bruto."""
    f = read_fundamental(BBRI)
    assert f.jenis == JENIS_BANK
    assert f.laba_bruto is None
    assert any("laba bruto" in c for c in f.catatan)


def test_jenis_dideteksi_dari_blok_yang_ada() -> None:
    """Deteksi dari nama blok nyata, BUKAN daftar sektor yang bisa usang."""
    assert deteksi_jenis({"pendapatan_dan_beban_operasional": {}}) == JENIS_BANK
    assert deteksi_jenis({"penjualan_dan_pendapatan_usaha": 1.0}) == JENIS_UMUM
    assert deteksi_jenis({}) == JENIS_UMUM


def test_eps_mencurigakan_ditandai() -> None:
    """Penjaga #4: EPS 0,0001 dengan laba 15,55 T WAJIB bertanda."""
    f = read_fundamental(BBRI)
    assert f.eps == 0.0001, "nilai sumber dibiarkan apa adanya"
    assert any("mencurigakan" in c for c in f.catatan), "EPS tak wajar wajib ditandai"


def test_eps_nol_ditandai() -> None:
    payload = {
        "stock_code": "X",
        "items": [
            {"label": "Q2", "data": {"laba_rugi": 1e12, "laba_rugi_per_saham": {"total": 0.0}}}
        ],
    }
    f = read_fundamental(payload)
    assert f.eps == 0.0
    assert any("mencurigakan" in c for c in f.catatan)


def test_eps_wajar_tidak_ditandai() -> None:
    f = read_fundamental(ANTM)
    assert f.eps == 124.08
    assert not any("mencurigakan" in c for c in f.catatan)


def test_tanpa_item_mengembalikan_kosong_bukan_angka_nol() -> None:
    """None != 0. Laporan kosong tidak boleh jadi 'laba nol'."""
    f = read_fundamental({"stock_code": "X", "items": []})
    assert f.ada is False
    assert f.laba_bersih is None
    assert any("kosong" in c for c in f.catatan)


def test_payload_none_aman() -> None:
    f = read_fundamental(None)
    assert isinstance(f, FundamentalEmiten)
    assert f.ada is False


def test_bentuk_data_tidak_dikenali() -> None:
    payload = {"stock_code": "X", "items": [{"label": "Q1", "data": "bukan dict"}]}
    f = read_fundamental(payload)
    assert f.ada is False
    assert any("tidak dikenali" in c for c in f.catatan)


def test_jumlah_kuartal_tercatat() -> None:
    assert read_fundamental(ANTM).jumlah_kuartal == 12
    assert read_fundamental(ANTM).label == "Q2 2026"
