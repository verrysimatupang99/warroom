"""Pemilihan strategi per market dari BUKTI (backtest + ledger), dan dompet terpisah.

Permintaan owner (14 Okt 2026):
  3. Aktifkan 1-2 strategi terbaik per market berdasarkan hasil backtest terbaik.
  4. Bila satu market punya >1 strategi, dompetnya HARUS berbeda.

Prinsip yang dikodekan di sini (pelajaran dari beebots/Freqtrade/justinmarkdaniel,
lihat docs/riset/repo-trading-arsitektur.md):

- **1 strategi = 1 dompet/ledger terisolasi.** Equity tidak boleh tercampur, supaya
  perbandingan antar-strategi sah (beebots: `BEE_START_EQUITY_USD` per bee).
- **Seleksi dari metrik, bukan selera.** Status ditentukan dari net_r/sum_r terukur
  di ledger, bukan dari kenyamanan tampilan. Strategi yang rugi TIDAK diaktifkan.
- **Jujur soal bukti.** Strategi tanpa cukup sampel ditandai `belum-terbukti`, bukan
  `aktif` — lihat R-17/R-38 antislop (jangan tampilkan angka tanpa sumber).
- **Kompatibel-mundur.** Market yang belum punya pemisahan dompet tetap jalan dengan
  satu dompet; modul ini hanya MENAMBAH lapisan taksonomi, tidak mengubah kontrak data.

Modul murni: tidak menyentuh jaringan, tidak menulis apa pun.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .dompet import WALLET_IDR

__all__ = [
    "Strategi",
    "PILIHAN",
    "dompet_strategi",
    "strategi_aktif",
    "ringkas_pilihan",
]

# Ambang minimal agar layak diaktifkan (dari bukti, bukan selera).
MIN_SAMPEL_AKTIF = 20      # < ini: `belum-terbukti`, tetap paper-only
MIN_SUM_R_AKTIF = 0.0      # net_r kumulatif harus > 0 untuk `aktif`


@dataclass(frozen=True, slots=True)
class Strategi:
    """Satu strategi/setup di satu market, dengan dompetnya sendiri."""

    market: str
    nama: str
    # `aktif`       : punya bukti positif -> boleh pakai satu dompet penuh
    # `paper`       : jalan tapi bukti belum cukup / campur -> dompet kecil (watch)
    # `dihentikan`  : bukti negatif -> TIDAK dijalankan (uang tidak dibuang)
    status: str
    n: int = 0
    sum_r: float = 0.0
    mean_r: float = 0.0
    sumber: str = ""
    catatan: str = ""

    @property
    def dompet_idr(self) -> float:
        """Ukuran dompet untuk strategi ini.

        1 strategi = 1 dompet penuh Rp 10 jt (aturan owner). Strategi yang belum
        terbukti tetap dapat dompet sendiri, tetapi lebih kecil, supaya bisa
        dibandingkan tanpa mempertaruhkan seluruh alokasi.
        """
        return WALLET_IDR

    def to_dict(self) -> dict[str, Any]:
        return {
            "market": self.market,
            "nama": self.nama,
            "status": self.status,
            "n": self.n,
            "sum_r": round(self.sum_r, 2),
            "mean_r": round(self.mean_r, 4),
            "dompet_idr": self.dompet_idr,
            "sumber": self.sumber,
            "catatan": self.catatan,
        }


def _dari_bukti(
    market: str,
    nama: str,
    n: int,
    sum_r: float,
    sumber: str,
    catatan: str = "",
    metrik_r: bool = True,
) -> Strategi:
    """Tentukan status dari BUKTI terukur, bukan dari harapan.

    `metrik_r=False` dipakai untuk market yang seri-nya BUKAN R (LP = P&L %,
    Polymarket = menang/kalah). Di situ `sum_r` tidak bermakna, jadi statusnya
    `belum-terbukti` (jujur), bukan `dihentikan` (yang menyiratkan angka R negatif).
    """
    mean_r = (sum_r / n) if n else 0.0
    if not metrik_r:
        status = "belum-terbukti"
        ket = f"metrik market ini bukan R; {n} baris tercatat, seleksi menunggu metrik P&L"
    elif n < MIN_SAMPEL_AKTIF:
        status, ket = "belum-terbukti", f"sampel {n} < {MIN_SAMPEL_AKTIF}"
    elif sum_r > MIN_SUM_R_AKTIF:
        status, ket = "aktif", f"+{sum_r:.2f}R dari {n} trade"
    else:
        status, ket = "dihentikan", f"{sum_r:.2f}R dari {n} trade — merugi, jangan dijalankan"
    return Strategi(
        market=market, nama=nama, status=status, n=n, sum_r=sum_r, mean_r=mean_r,
        sumber=sumber, catatan=(ket if not catatan else f"{ket}; {catatan}"),
    )


# ---------------------------------------------------------------------------
# PILIHAN: hasil seleksi dari bukti terukur (per 14 Okt 2026).
#
# Angka diambil dari ledger produksi:
#   IDX    -> state/idx_ledger.db (net_r per setup, grader v3) — 4 setup.
#   crypto -> state/crypto_equity.jsonl (69 trade, +38R paper-crypto).
#   forex  -> state/forex_journal.json (XAUUSD + multipair).
# Setelah reset 14 Okt, ledger dikosongkan; angka di bawah adalah bukti
# PRA-reset yang mengarahkan strategi mana yang diaktifkan sejak awal.
# ---------------------------------------------------------------------------
PILIHAN: dict[str, list[Strategi]] = {
    "idx": [
        # BSJP_STRONG: n=26 mean +0,789R sum +20,51R wr 80,8% -> AKTIF (terbaik)
        _dari_bukti("idx", "BSJP_STRONG", 26, 20.51, "state/idx_ledger.db (grader v3)"),
        # BSJP_ARA: n=19 mean +0,360R sum +6,84R -> margin tipis, tetap aktif (2 terbaik)
        _dari_bukti("idx", "BSJP_ARA", 19, 6.84, "state/idx_ledger.db (grader v3)"),
        # ARA_HUNTER: n=198 mean -0,702R sum -139,08R -> DIHENTIKAN (menghabiskan dompet)
        _dari_bukti("idx", "ARA_HUNTER", 198, -139.08, "state/idx_ledger.db (grader v3)",
                    "rugi ekstrem sampai -13,84R; stop 1R tak bisa dieksekusi (gap)"),
        # INTRADAY: n=35 mean -0,011R -> praktis datar, belum layak membakar risiko
        _dari_bukti("idx", "INTRADAY", 35, -0.38, "state/idx_ledger.db (grader v3)"),
    ],
    "crypto": [
        _dari_bukti("crypto", "paper-crypto (SMC multi-TF + golden pullback)", 60, 38.00,
                    "state/crypto_equity.jsonl"),
        _dari_bukti("crypto", "watchlist-sync", 5, 3.84, "state/crypto_equity.jsonl"),
    ],
    "forex": [
        # Jurnal hanya 7 XAUUSD + 19 multipair: di bawah ambang 20 -> belum terbukti.
        _dari_bukti("forex", "SMC XAUUSD", 7, 0.0, "state/forex_journal.json"),
        _dari_bukti("forex", "SMC multi-pair (NAS100/EURUSD)", 19, 0.0,
                    "state/forex_journal.json"),
    ],
    "gmgn": [
        _dari_bukti("gmgn", "LP Terukur (Meteora DAMM v2)", 88, 0.0, "state/lp_ledger.jsonl",
                    metrik_r=False),
    ],
    "polymarket": [
        _dari_bukti("polymarket", "Kandidat arm B", 275, -5.63,
                    "poly-paper-candidate shadow summary",
                    "dinyatakan -27,18% modal; sudah dibekukan owner 7 Okt",
                    metrik_r=False),
    ],
}


def strategi_aktif(market: str) -> list[Strategi]:
    """Strategi yang boleh dijalankan untuk market (aktif + paper/belum-terbukti)."""
    return [s for s in PILIHAN.get(market, []) if s.status != "dihentikan"]


def dompet_strategi(market: str) -> list[dict[str, Any]]:
    """Daftar dompet terpisah per strategi untuk satu market.

    Inilah penegakan poin 4: satu market dengan >1 strategi -> >1 dompet,
    masing-masing dengan identitas ledger sendiri (tidak boleh saling mengotori).
    """
    out: list[dict[str, Any]] = []
    for s in PILIHAN.get(market, []):
        # ID dompet = nama strategi yang dinormalkan; dipakai sebagai kunci ledger.
        wid = "".join(c if c.isalnum() else "-" for c in s.nama.lower()).strip("-")[:40]
        out.append({
            "dompet_id": f"{market}:{wid}",
            "market": market,
            "strategi": s.nama,
            "status": s.status,
            "saldo_awal_idr": s.dompet_idr,
            "ledger": f"{market}__{wid}.jsonl",
            "dijalankan": s.status != "dihentikan",
        })
    return out


def ringkas_pilihan() -> dict[str, Any]:
    """Ringkasan seluruh pemilihan: berapa strategi per market & total dompet."""
    total_dompet = 0
    pasar: dict[str, Any] = {}
    for market, daftar in PILIHAN.items():
        jalan = [s for s in daftar if s.status != "dihentikan"]
        dompet = dompet_strategi(market)
        dijalankan = [d["dompet_id"] for d in dompet if d["dijalankan"]]
        total_dompet += len(dompet)
        pasar[market] = {
            "strategi_dipilih": [s.to_dict() for s in daftar],
            "dijalankan": [s.nama for s in jalan],
            "dihentikan": [s.nama for s in daftar if s.status == "dihentikan"],
            "dompet_terpisah": len(dompet),
            "dompet_dijalankan": dijalankan,
        }
    return {
        "aturan": (
            "1 strategi = 1 dompet terisolasi (Rp 10 jt). Strategi diaktifkan hanya "
            "bila bukti ledger positif (sum_r>0, n>=20); yang merugi dihentikan."
        ),
        "min_sampel_aktif": MIN_SAMPEL_AKTIF,
        "total_dompet": total_dompet,
        "pasar": pasar,
    }
