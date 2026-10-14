"""Pakem bukti — satu standar kematangan sampel untuk SEMUA market.

Disepakati owner 6 Okt 2026, diangkat dari yang sudah terbukti di Tencent
(`signal-performance-validation` + drift IDX) dan pelajaran gate Polymarket:

- `< 10` tuntas  → **INSUFFICIENT**  (belum bisa diklaim apa pun)
- `10–29`        → **DIRECTIONAL**   (arah saja; dilarang klaim profit/tuning)
- `≥ 30`         → **PRELIMINARY**   (evaluasi awal, setelah biaya & cek epoch)
- `≥ 100`        → **TUNING**        (baru boleh tuning, setelah uji ekor & stabilitas)

Aturan yang mengikat:

1. **Win rate tinggi tidak pernah cukup.** Wajib expectancy bersih > 0 DAN
   profit factor > 1 DAN biaya terdokumentasi.
2. **Hitung hari, bukan cuma trade.** Satu hari bisa memuat puluhan trade yang
   saling berkorelasi; CI dan gate dihitung dari **hari independen**
   (pelajaran drift IDX: "efektif N=11 hari, bukan 35 trade").
3. **Bedakan sampel nol dari sampel kurang.** `n=0` → INSUFFICIENT dengan
   `alasan` yang menjelaskan; jangan mengarang nilai.
4. **Ambang ini tidak boleh dilonggarkan otomatis.** Hanya manusia/owner.

Modul ini murni hitung — tidak membaca berkas, tidak menyentuh jaringan.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "AMBANG_DIRECTIONAL",
    "AMBANG_PRELIMINARY",
    "AMBANG_TUNING",
    "MIN_PROFIT_FACTOR",
    "PakemResult",
    "count_independent_days",
    "evaluate_pakem",
    "summarize_r",
    "wilson_interval",
]

AMBANG_DIRECTIONAL = 10
AMBANG_PRELIMINARY = 30
AMBANG_TUNING = 100
MIN_PROFIT_FACTOR = 1.0
Z_WILSON = 1.6448536269514722  # 90% satu sisi (selaras gate Polymarket)


def wilson_interval(menang: int, total: int, z: float = Z_WILSON) -> tuple[float, float]:
    """Interval Wilson untuk proporsi (0..1). total=0 → (0, 0) dengan arti 'n/a'."""
    if total <= 0:
        return (0.0, 0.0)
    p = menang / total
    penyebut = 1 + z * z / total
    pusat = (p + z * z / (2 * total)) / penyebut
    margin = (z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total))) / penyebut
    return (max(0.0, pusat - margin), min(1.0, pusat + margin))


def count_independent_days(tanggal: Iterable[str]) -> int:
    """Jumlah hari unik dari daftar tanggal ISO.

    Dipakai sebagai 'n efektif': trade pada hari yang sama saling berkorelasi
    (regime pasar sama), jadi sampel dihitung per hari, bukan per trade.
    """
    hari = set()
    for t in tanggal:
        if not t:
            continue
        s = str(t).strip()
        hari.add(s[:10])  # YYYY-MM-DD
    return len(hari)


def summarize_r(r_values: Iterable[float]) -> dict[str, Any]:
    """Ringkas seri R: n, rata-rata, total, win/loss, profit factor, max DD."""
    rs = [float(x) for x in r_values if x is not None]
    n = len(rs)
    if n == 0:
        return {
            "n": 0,
            "mean_r": None,
            "total_r": 0.0,
            "wins": 0,
            "losses": 0,
            "winrate_pct": None,
            "profit_factor": None,
            "max_drawdown_r": None,
        }
    menang = [r for r in rs if r > 0]
    kalah = [r for r in rs if r < 0]
    bruto_menang = sum(menang)
    bruto_kalah = abs(sum(kalah))
    # Rata-rata kumulatif untuk drawdown.
    kum = 0.0
    puncak = 0.0
    dd = 0.0
    for r in rs:
        kum += r
        puncak = max(puncak, kum)
        dd = max(dd, puncak - kum)
    return {
        "n": n,
        "mean_r": round(sum(rs) / n, 4),
        "total_r": round(sum(rs), 4),
        "wins": len(menang),
        "losses": len(kalah),
        "winrate_pct": round(len(menang) / n * 100, 2),
        "profit_factor": (
            round(bruto_menang / bruto_kalah, 4)
            if bruto_kalah > 0
            else (None if bruto_menang == 0 else float("inf"))
        ),
        "max_drawdown_r": round(dd, 4),
    }


@dataclass
class PakemResult:
    """Hasil penilaian satu seri hasil (satu market/setup)."""

    tingkat: str  # INSUFFICIENT | DIRECTIONAL | PRELIMINARY | TUNING
    n: int
    n_hari: int
    ringkas: dict[str, Any]
    ci_winrate: tuple[float, float]
    alasan: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "tingkat": self.tingkat,
            "n": self.n,
            "n_hari": self.n_hari,
            "ringkas": self.ringkas,
            "ci_winrate": [round(self.ci_winrate[0], 4), round(self.ci_winrate[1], 4)],
            "alasan": list(self.alasan),
        }


def evaluate_pakem(
    closes: Iterable[dict[str, Any]],
    *,
    kunci_r: str = "r",
    kunci_tanggal: str = "closed_at",
    biaya_tercatat: bool | None = None,
) -> PakemResult:
    """Nilai satu seri hasil tertutup terhadap pakem bukti.

    ``closes``: baris hasil yang HANYA berisi trade tuntas (bukan pending).
    ``biaya_tercatat``: True bila biaya (fee/slippage) terdokumentasi per trade;
    None berarti tidak diketahui → dicatat sebagai catatan, bukan asumsi.

    Ambang memakai **jumlah hari independen** bila tersedia (lebih jujur),
    dan jatuh ke jumlah trade bila tanggal tidak ada.
    """
    rows = [c for c in closes if c is not None]
    rs = [c.get(kunci_r) for c in rows if c.get(kunci_r) is not None]
    tanggal = [str(c.get(kunci_tanggal) or "") for c in rows]
    n_hari = count_independent_days(tanggal)
    n = len(rs)
    ringkas = summarize_r(rs)
    menang = ringkas["wins"]
    ci = wilson_interval(menang, n)
    alasan: list[str] = []

    # Dasar keputusan: n efektif (hari) bila tanggal lengkap, kalau tidak jumlah trade.
    n_efektif = n_hari if n_hari > 0 else n
    if n_hari == 0 and n > 0:
        alasan.append("tanggal tidak tersedia — koreksi klaster hari tidak bisa dihitung")

    if n == 0:
        tingkat = "INSUFFICIENT"
        alasan.append("belum ada trade tuntas (n=0) — jangan tampilkan sebagai 0%")
    elif n_efektif < AMBANG_DIRECTIONAL:
        tingkat = "INSUFFICIENT"
        alasan.append(f"sampel kurang: {n_efektif} < {AMBANG_DIRECTIONAL} (hari/trade efektif)")
    elif n_efektif < AMBANG_PRELIMINARY:
        tingkat = "DIRECTIONAL"
        alasan.append("arah saja — dilarang klaim profit atau tuning di tingkat ini")
    elif n_efektif < AMBANG_TUNING:
        tingkat = "PRELIMINARY"
    else:
        tingkat = "TUNING"
        alasan.append("wajib uji ekor & stabilitas sebelum tuning")

    # Syarat kualitas yang berlaku di semua tingkat ≥ DIRECTIONAL.
    if tingkat != "INSUFFICIENT":
        exp = ringkas["mean_r"]
        pf = ringkas["profit_factor"]
        if exp is None or exp <= 0:
            alasan.append(f"expectancy bersih {exp} ≤ 0 — belum layak")
        if pf is not None and pf != float("inf") and pf <= MIN_PROFIT_FACTOR:
            alasan.append(f"profit factor {pf} ≤ {MIN_PROFIT_FACTOR} — belum layak")
        if biaya_tercatat is False:
            alasan.append("biaya (fee/slippage) belum terdokumentasi — angka belum bersih")
        if biaya_tercatat is None:
            alasan.append("status biaya tidak diketahui — perlakukan sebagai bruto")

    return PakemResult(tingkat=tingkat, n=n, n_hari=n_hari, ringkas=ringkas, ci_winrate=ci, alasan=alasan)
