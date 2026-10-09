"""Gate service — satu implementasi aturan kelulusan (ADR-003, P1-T2).

Aturan baku (tidak boleh diubah agen; hanya owner):

1. ``n >= min_n`` (baku 30).
2. Interval kepercayaan Wilson dua sisi pada ``ci`` (baku 0,90 → z = 1,645).
3. **Lolos hanya bila ``ci_low > be``** — bukan titik estimasi.
4. Split data harus dibekukan lebih dulu (``split="frozen:<id>"``). Tanpa itu → ``insufficient``.

``required_n`` dihitung dan dikembalikan supaya UI bisa menampilkan "butuh N lagi" sebagai
angka, bukan opini (GateMeter, 03-backend.md §6).

Fungsi ini sengaja murni: tanpa I/O, tanpa DB, tanpa LLM. UI, learner, dan CI memanggilnya
(dan endpoint ``POST /api/v1/gate/evaluate`` memakai yang sama).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal

__all__ = [
    "DEFAULT_CI",
    "DEFAULT_MIN_N",
    "GateInput",
    "GateResult",
    "PakemTingkat",
    "evaluate",
    "required_n",
    "tingkat_pakem",
    "wilson_interval",
]

DEFAULT_CI = 0.90
DEFAULT_MIN_N = 30

Verdict = Literal["lolos", "gagal", "insufficient"]

# z dua sisi untuk tingkat kepercayaan yang lazim. Nilai di luar tabel dihitung
# lewat aproksimasi normal (lihat _z_for).
_Z_TABLE = {
    0.80: 1.2816,
    0.90: 1.6449,
    0.95: 1.9600,
    0.98: 2.3263,
    0.99: 2.5758,
}


def _z_for(ci: float) -> float:
    """z dua sisi untuk tingkat kepercayaan ``ci`` (mis. 0,90 → 1,6449)."""
    if ci <= 0.0 or ci >= 1.0:
        raise ValueError(f"ci harus di antara 0 dan 1 (diberi {ci!r})")
    key = round(ci, 4)
    if key in _Z_TABLE:
        return _Z_TABLE[key]
    # Aproksimasi normal terbalik (Acklam) — cukup akurat untuk 4 desimal pada rentang wajar.
    p = 1.0 - (1.0 - ci) / 2.0
    a = [-3.969683028665376e01, 2.209460984245205e02, -2.759285104469687e02,
         1.383577518672690e02, -3.066479806614716e01, 2.506628277459239e00]
    b = [-5.447609879822406e01, 1.615858368580409e02, -1.556989798598866e02,
         6.680131188771972e01, -1.328068155288572e01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e00,
         -2.549732539343734e00, 4.374664141464968e00, 2.938163982698783e00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e00,
         3.754408661907416e00]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1
        )
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1
        )
    q = p - 0.5
    r = q * q
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / (
        ((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1
    )


def wilson_interval(win: int, n: int, ci: float = DEFAULT_CI) -> tuple[float, float]:
    """Interval Wilson dua sisi untuk proporsi ``win/n``.

    Dipakai (bukan Wald) karena benar di dekat 0/1 dan pada n kecil — persis rentang
    kerja gate ini.
    """
    if n <= 0:
        return (0.0, 1.0)
    if win < 0 or win > n:
        raise ValueError(f"win harus 0..n (win={win}, n={n})")
    z = _z_for(ci)
    p = win / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - margin), min(1.0, centre + margin))


def _win_at(p: float, n: int) -> int:
    """Jumlah kemenangan pada ``n`` sampel bila win rate ``p`` bertahan (pembulatan biasa).

    Konvensi ini dipakai bersama oleh :func:`required_n` dan tesnya supaya angka
    "butuh n" di UI benar-benar konsisten dengan keputusan gate.
    """
    return int(p * n + 0.5)


def _lolos_at(n: int, p: float, be: float, ci: float, deff: float = 1.0) -> bool:
    """True bila pada ``n`` sampel baku (n efektif ``n/deff``) batas bawah CI melewati ``be``."""
    if deff > 1.0:
        n_eff = max(1, round(n / deff))
        return wilson_interval(_win_at(p, n_eff), n_eff, ci)[0] > be
    return wilson_interval(_win_at(p, n), n, ci)[0] > be


def required_n(
    be: float,
    win_rate: float,
    ci: float = DEFAULT_CI,
    n_max: int = 200_000,
    deff: float = 1.0,
) -> int | None:
    """Jumlah sampel terkecil agar ``ci_low > be`` pada win rate yang diamati.

    Dihitung eksak: cari-n dua arah (dobel → bagi dua) memakai :func:`wilson_interval`
    yang sama dengan yang dipakai gate. Bukan aproksimasi bentuk-tertutup, supaya angka
    "butuh N lagi" di UI benar-benar konsisten dengan keputusan gate.

    ``deff`` = koreksi klaster; jumlah sampel baku yang dibutuhkan ikut terskala
    (``n/deff`` efektif). ``None`` bila ``win_rate <= be`` (menambah sampel tidak akan
    meloloskan — aturan atau asumsinya yang harus diubah manusia, bukan ambangnya) atau
    bila kebutuhan melebihi ``n_max``.
    """
    if deff < 1.0:
        raise ValueError(f"deff harus >= 1 (diberi {deff!r})")
    if win_rate <= be:
        return None
    if n_max < 1:
        raise ValueError("n_max harus >= 1")
    lo, hi = 1, 1024
    while hi < n_max and not _lolos_at(hi, win_rate, be, ci, deff):
        lo, hi = hi, min(hi * 2, n_max)
    if not _lolos_at(hi, win_rate, be, ci, deff):
        return None
    while lo < hi:  # cari batas bawah terkecil
        mid = (lo + hi) // 2
        if _lolos_at(mid, win_rate, be, ci, deff):
            hi = mid
        else:
            lo = mid + 1
    return lo


@dataclass(frozen=True)
class GateInput:
    """Masukan gate. ``split`` harus "frozen:<id>" — split beku sebelum melihat hasil."""

    n: int
    win: int
    be: float
    ci: float = DEFAULT_CI
    min_n: int = DEFAULT_MIN_N
    split: str | None = None
    # Koreksi klaster (design effect). Harus >= 1: nilai di bawah 1 akan mempersempit CI
    # (arah melonggarkan) dan ditolak. Nilai > 1 memperlebar CI — arah konservatif.
    deff: float = 1.0
    # Label sumber hasil. "eksplorasi" tidak boleh dipromosikan lewat gate ini.
    label: Literal["konfirmasi", "eksplorasi"] = "konfirmasi"
    subject: str = ""
    rule: str = ""


@dataclass(frozen=True)
class GateResult:
    verdict: Verdict
    reason: str
    ci_low: float
    ci_high: float
    win_rate: float
    be: float
    n: int
    required_n: int | None
    policy_version: str = "gate/0.2.0"
    notes: list[str] = field(default_factory=list)
    # Kebijakan yang dipakai saat menilai — dikembalikan supaya UI bisa melabelinya.
    ci: float = DEFAULT_CI
    deff: float = 1.0

    @property
    def lolos(self) -> bool:
        return self.verdict == "lolos"

    @property
    def pakem(self) -> str:
        """Tingkat kematangan sampel pada **n efektif** (n ÷ deff) — pakem bukti owner.

        Dipisahkan dari verdict: gate bisa "gagal" pada sampel PRELIMINARY (aturan belum
        terbukti) atau "insufficient" pada sampel TUNING (mis. split belum dibekukan).
        UI wajib menampilkan keduanya — jangan sampai n besar terbaca "hampir lolos"
        padahal yang kurang bukan sampel.
        """
        return tingkat_pakem(self.n_efektif)

    @property
    def n_efektif(self) -> int:
        """n setelah koreksi klaster (n ÷ deff), minimal 1 bila ada sampel."""
        if self.n <= 0:
            return 0
        if self.deff and self.deff > 1.0:
            return max(1, round(self.n / self.deff))
        return self.n


class PakemTingkat:
    """Ambang pakem bukti (satu sumber untuk gate, UI, dan learner)."""

    DIRECTIONAL = 10
    PRELIMINARY = 30
    TUNING = 100


def tingkat_pakem(n_efektif: int) -> str:
    """Kematangan sampel: INSUFFICIENT · DIRECTIONAL · PRELIMINARY · TUNING.

    Ambang disepakati owner 6 Okt 2026 (diangkat dari Tencent
    `signal-performance-validation`): <10 insufficient · 10–29 directional ·
    ≥30 preliminary · ≥100 tuning. Pakai **n efektif** (setelah deff), bukan n mentah.
    """
    if n_efektif < PakemTingkat.DIRECTIONAL:
        return "INSUFFICIENT"
    if n_efektif < PakemTingkat.PRELIMINARY:
        return "DIRECTIONAL"
    if n_efektif < PakemTingkat.TUNING:
        return "PRELIMINARY"
    return "TUNING"


def evaluate(g: GateInput) -> GateResult:
    """Putuskan lolos/gagal/insufficient. ``lolos`` hanya bila ``ci_low > be``.

    ``deff`` = koreksi klaster. Nilai < 1 ditolak (mempersempit CI = arah melonggarkan);
    nilai > 1 menilai CI pada n efektif ``n/deff`` dan menskalakan ``required_n`` — sama
    seperti alat Poly (``qa/favorite-live-verdict.py``).
    """
    notes: list[str] = []
    if g.deff < 1.0:
        raise ValueError(f"deff harus >= 1 (diberi {g.deff!r}); koreksi klaster tidak boleh melonggarkan")
    if g.n <= 0:
        return GateResult("insufficient", "tidak ada sampel (n=0)", 0.0, 1.0, 0.0, g.be, g.n, None,
                          ci=g.ci, deff=g.deff,
                          notes=["butuh data sebelum gate bisa diputuskan"])
    if g.win < 0 or g.win > g.n:
        raise ValueError(f"win harus 0..n (win={g.win}, n={g.n})")

    win_rate = g.win / g.n
    if g.deff > 1.0:
        n_eff = max(1, round(g.n / g.deff))
        ci_low, ci_high = wilson_interval(_win_at(win_rate, n_eff), n_eff, g.ci)
        notes.append(f"koreksi klaster deff={g.deff:.3f}: n efektif {n_eff} (dari {g.n})")
    else:
        ci_low, ci_high = wilson_interval(g.win, g.n, g.ci)
    need = required_n(g.be, win_rate, g.ci, deff=g.deff)

    if g.label == "eksplorasi":
        return GateResult(
            "insufficient",
            "hasil eksplorasi tidak bisa dipromosikan; butuh sampel baru + split beku",
            ci_low, ci_high, win_rate, g.be, g.n, need, ci=g.ci, deff=g.deff,
            notes=[*notes, "label=eksplorasi"],
        )

    if not g.split or not g.split.startswith("frozen:"):
        return GateResult(
            "insufficient",
            "data uji belum dibekukan (split beku wajib: split=frozen:<id>, ADR-003)",
            ci_low, ci_high, win_rate, g.be, g.n, need, ci=g.ci, deff=g.deff,
            notes=[*notes, "split beku wajib (ADR-003)"],
        )

    if g.n < g.min_n:
        return GateResult(
            "insufficient",
            f"n={g.n} < min_n={g.min_n}",
            ci_low, ci_high, win_rate, g.be, g.n, need, ci=g.ci, deff=g.deff,
            notes=[*notes, f"butuh {g.min_n - g.n} sampel lagi untuk memenuhi min_n"],
        )

    if ci_low > g.be:
        return GateResult("lolos", f"ci_low {ci_low:.4f} > be {g.be:.4f}",
                          ci_low, ci_high, win_rate, g.be, g.n, need, ci=g.ci, deff=g.deff,
                          notes=notes)

    reason = f"ci_low {ci_low:.4f} <= be {g.be:.4f}"
    if need is not None:
        notes.append(f"perkiraan butuh n≈{need} pada win rate {win_rate:.3%} (deff={g.deff:.3f})")
    else:
        notes.append("win rate <= BE: menambah sampel tidak akan meloloskan; aturan harus diubah manusia")
    return GateResult("gagal", reason, ci_low, ci_high, win_rate, g.be, g.n, need,
                      ci=g.ci, deff=g.deff, notes=notes)