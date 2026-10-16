"""Regresi per strategi: identitas dan pemisahan dompet tidak boleh berubah diam-diam.

Perbandingan antar-strategi berdiri di atas dua janji:

1. **Satu strategi = satu dompet/ledger.** Kalau dua strategi menulis ke berkas yang
   sama, angkanya tercampur dan tidak ada lagi yang bisa dibandingkan.
2. **Identitas stabil.** Nama strategi menentukan nama ledger (lihat `dompet_strategi`),
   jadi mengganti nama = riwayat lama jadi yatim dan perbandingan mulai dari nol.

Tabel di bawah adalah foto keadaan 14 Okt 2026 — bukan target. Perubahannya tidak
dilarang; yang dilarang adalah berubah tanpa sadar.
"""

from __future__ import annotations

from warroom_core.market_signal import PASAR

from live_trading import strategi_terpilih as st

# market → [(nama strategi, status, berkas ledger)]
HARAPAN: dict[str, list[tuple[str, str, str]]] = {
    "idx": [
        ("BSJP_STRONG", "aktif", "idx__bsjp-strong.jsonl"),
        ("BSJP_ARA", "belum-terbukti", "idx__bsjp-ara.jsonl"),
        ("ARA_HUNTER", "dihentikan", "idx__ara-hunter.jsonl"),
        ("INTRADAY", "dihentikan", "idx__intraday.jsonl"),
    ],
    "crypto": [
        (
            "paper-crypto (SMC multi-TF + golden pullback)",
            "aktif",
            "crypto__paper-crypto--smc-multi-tf---golden-pull.jsonl",
        ),
        ("watchlist-sync", "belum-terbukti", "crypto__watchlist-sync.jsonl"),
    ],
    "forex": [
        ("SMC XAUUSD", "belum-terbukti", "forex__smc-xauusd.jsonl"),
        ("SMC multi-pair (NAS100/EURUSD)", "belum-terbukti", "forex__smc-multi-pair--nas100-eurusd.jsonl"),
    ],
    "gmgn": [
        ("LP Terukur (Meteora DAMM v2)", "belum-terbukti", "gmgn__lp-terukur--meteora-damm-v2.jsonl"),
    ],
    "polymarket": [
        ("Kandidat arm B", "belum-terbukti", "polymarket__kandidat-arm-b.jsonl"),
    ],
}


def test_pilihan_strategi_hanya_untuk_pasar_yang_dikenal() -> None:
    """Pilihan strategi tidak boleh menunjuk pasar yang tidak ada di daftar pasar."""
    pasar = {k for k, _label, _sumber in PASAR}
    assert set(st.PILIHAN) <= pasar, "pasar tidak dikenal → baris papan peringkat tak pernah lahir"


def test_dompet_dan_ledger_terpisah_per_strategi() -> None:
    """Seluruh strategi lintas pasar: dompet_id dan berkas ledger harus unik."""
    dompet = [d for market in st.PILIHAN for d in st.dompet_strategi(market)]
    jumlah_strategi = sum(len(daftar) for daftar in st.PILIHAN.values())

    assert len(dompet) == jumlah_strategi
    ids = [d["dompet_id"] for d in dompet]
    ledger = [d["ledger"] for d in dompet]
    assert len(ids) == len(set(ids)), "dompet_id kembar = dua strategi berbagi satu dompet"
    assert len(ledger) == len(set(ledger)), "dua strategi menulis ke ledger yang sama = angka tercampur"
    assert all(d["ledger"].endswith(".jsonl") for d in dompet)


def test_identitas_dan_status_strategi_tidak_berubah_diam_diam() -> None:
    """Foto nama + status + ledger per strategi.

    Perubahan di sini berarti salah satu dari: rename (riwayat lama yatim), status
    berubah (alokasi dompet ikut berubah), atau ledger pindah berkas. Semuanya perlu
    disengaja — perbarui HARAPAN di tes ini bersama alasannya.
    """
    nyata = {
        market: [
            (s.nama, s.status, d["ledger"])
            for s, d in zip(daftar, st.dompet_strategi(market), strict=True)
        ]
        for market, daftar in st.PILIHAN.items()
    }
    assert nyata == HARAPAN
