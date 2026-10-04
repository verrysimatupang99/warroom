"""Gate setup — aturan lapangan yang dipindah dari teks prompt menjadi fungsi.

Sumber aturan: prompt 5-agen `crypto-5agent-pipeline-653` (Tencent), dibaca read-only.
**Angkanya tidak diubah** — itu hasil iterasi lapangan (8–27 Sep 2026). Yang berubah
hanya tempatnya: dari kalimat yang dipatuhi secara probabilistik, menjadi fungsi yang
selalu dijalankan dan selalu meninggalkan alasan tertulis.

Tiap aturan mengembalikan :class:`Verdict`. Aturan keras (``hard=True``) yang gagal
membatalkan setup; aturan lunak hanya menurunkan tier atau jadi catatan.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SL_MAX_PCT = 5.0  # jarak SL dari entry maksimum (prompt: "di luar = FAIL")
SL_MIN_PCT = 1.0  # di bawah ini biasanya swing mikro → pakai swing lebih valid
# 29 Sep: cap relatif 2xATR sempat dipasang lalu DI-REVERT hari yang sama —
# validasi 180d penuh menunjukkan pengenceran (+0,114R → +0,076R, total +125,66R → +93,83R).
# Subset offline kecil menipu; angka penuh yang menang. Kasus PUMP (SL 6,82% lolos) rugi
# ditolak — itu harga yang dibayar untuk proteksi.
ATR_MIN_PCT = 1.0  # ATR1H minimum
ATR_IDEAL_PCT = 1.5
EXTENDED_MAX_PCT = 4.0  # harga >4% jauh dari POI → setup basi
MAX_OPEN_POSITIONS = 2
BTC_MOVE_CORRELATION_PCT = 3.0


@dataclass(frozen=True)
class Verdict:
    rule: str
    ok: bool
    reason: str
    hard: bool = True
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Assessment:
    allowed: bool
    tier: str                      # "PREMIUM" | "STANDAR" | "SKIP"
    verdicts: tuple[Verdict, ...]
    duplicate_of: str | None = None  # waktu kandidat lama yang sama (kalau duplikat)

    @property
    def failures(self) -> list[Verdict]:
        return [v for v in self.verdicts if not v.ok]

    def summary(self) -> str:
        bad = ", ".join(f"{v.rule}({v.reason})" for v in self.failures)
        return f"{self.tier} — {'lolos' if self.allowed else 'gagal: ' + bad}"


# ------------------------------------------------------------------ aturan
def mtf_alignment(direction: str, bias_4h: str, bias_1h: str, bias_1d: str) -> Verdict:
    """4H+1H wajib searah. 1D melawan → maks STANDAR. 1D+4H melawan → skip."""
    want = "bullish" if direction.lower() == "long" else "bearish"
    ok_4h, ok_1h, ok_1d = bias_4h == want, bias_1h == want, bias_1d == want

    if not (ok_4h and ok_1h):
        return Verdict(
            "mtf_alignment",
            False,
            f"4H={bias_4h} 1H={bias_1h} tidak searah {direction}",
            detail={"4h": bias_4h, "1h": bias_1h, "1d": bias_1d},
        )
    if not ok_1d:
        return Verdict(
            "mtf_alignment",
            True,
            f"4H+1H searah, 1D {bias_1d} melawan → maks STANDAR",
            hard=False,
            detail={"tier_cap": "STANDAR"},
        )
    return Verdict("mtf_alignment", True, "4H+1H+1D searah", detail={"tier_cap": "PREMIUM"})


def sl_distance(direction: str, entry: float, sl: float, atr_pct: float | None = None) -> Verdict:
    """SL struktural: 1%–5% dari entry, dan di sisi yang benar.

    ``atr_pct`` diterima tapi DIABAIKAN (eksperimen 2xATR 29 Sep di-revert —
    lihat SL_MAX_PCT). Parameter dipertahankan supaya pemanggil tak perlu diubah.
    """
    if entry <= 0:
        return Verdict("sl_distance", False, "entry tidak valid")
    long = direction.lower() == "long"
    if (long and sl >= entry) or (not long and sl <= entry):
        return Verdict("sl_distance", False, f"SL di sisi salah untuk {direction}")

    pct = abs(entry - sl) / entry * 100.0
    if pct > SL_MAX_PCT:
        return Verdict(
            "sl_distance",
            False,
            f"jarak SL {pct:.2f}% > {SL_MAX_PCT}% — tidak worth risk",
            detail={"pct": pct},
        )
    if pct < SL_MIN_PCT:
        return Verdict(
            "sl_distance",
            False,
            f"jarak SL {pct:.2f}% < {SL_MIN_PCT}% — biasanya swing mikro",
            detail={"pct": pct},
        )
    return Verdict("sl_distance", True, f"SL {pct:.2f}% dari entry", detail={"pct": pct})


def atr_min(atr_pct_value: float | None) -> Verdict:
    """ATR1H ≥1% wajib: target intraday mustahil kalau koin tidak bergerak."""
    if atr_pct_value is None:
        return Verdict("atr_min", False, "ATR tidak bisa dihitung (data kurang)")
    if atr_pct_value < ATR_MIN_PCT:
        return Verdict(
            "atr_min", False, f"ATR1H {atr_pct_value:.2f}% < {ATR_MIN_PCT}%", detail={"atr": atr_pct_value}
        )
    note = "ideal" if atr_pct_value >= ATR_IDEAL_PCT else f"di bawah ideal {ATR_IDEAL_PCT}%"
    return Verdict(
        "atr_min", True, f"ATR1H {atr_pct_value:.2f}% ({note})", hard=False, detail={"atr": atr_pct_value}
    )


def freshness(
    direction: str, tp1: float, poi_mid: float, price: float, recent_high: float, recent_low: float
) -> Verdict:
    """Signal harus masih bisa dieksekusi SETELAH dipost.

    Hanya satu yang diperiksa: harga belum terlampau jauh dari POI (setup basi).
    Pemeriksaan lama "(a) TP1 tersentuh 6 jam terakhir → TOLAK" DIHAPUS 29 Sep:
    backtest 300d (n=2627 ditolak sendirian, +0,04R, t=+4,20 kuat) + 180d + offset-300d
    konsisten menunjukkan aturan itu membuang pemenang — TP1 yang tersentuh justru
    konfirmasi momentum, bukan basi. Yang dipertahankan hanya proteksi ngejar harga.
    """
    long = direction.lower() == "long"
    if poi_mid > 0:
        ext = abs(price - poi_mid) / poi_mid * 100.0
        if long and price > poi_mid and ext > EXTENDED_MAX_PCT:
            return Verdict(
                "freshness", False, f"harga {ext:.2f}% di atas POI — tunggu POI baru", detail={"ext": ext}
            )
        if not long and price < poi_mid and ext > EXTENDED_MAX_PCT:
            return Verdict(
                "freshness", False, f"harga {ext:.2f}% di bawah POI — tunggu POI baru", detail={"ext": ext}
            )
    return Verdict("freshness", True, "harga masih dekat POI")


def poi_valid(
    direction: str, entry: float, poi_low: float | None, poi_high: float | None, poi_kind: str | None
) -> Verdict:
    """Entry hanya di POI yang sah — bukan di harga yang kebetulan sedang berjalan."""
    if poi_low is None or poi_high is None:
        return Verdict("poi_valid", False, "tidak ada POI searah yang ditemukan")
    if not (poi_low <= entry <= poi_high):
        return Verdict(
            "poi_valid",
            False,
            f"entry {entry} di luar zona POI {poi_kind or '?'} [{poi_low}-{poi_high}]",
            detail={"poi": poi_kind},
        )
    return Verdict(
        "poi_valid", True, f"entry di dalam POI {poi_kind} [{poi_low}-{poi_high}]", detail={"poi": poi_kind}
    )


def exposure(direction: str, open_positions: list[dict[str, Any]], btc_change_24h: float | None) -> Verdict:
    """Batas eksposur: jumlah posisi + korelasi BTC.

    Aturan dari prompt: maks 2 posisi; kalau |BTC 24j| > 3%, jangan dua posisi searah.
    """
    if len(open_positions) >= MAX_OPEN_POSITIONS:
        return Verdict(
            "exposure", False, f"posisi terbuka {len(open_positions)}/{MAX_OPEN_POSITIONS} — penuh"
        )

    same_dir = [p for p in open_positions if str(p.get("direction", "")).lower() == direction.lower()]
    if same_dir and btc_change_24h is not None and abs(btc_change_24h) > BTC_MOVE_CORRELATION_PCT:
        return Verdict(
            "exposure",
            False,
            f"BTC 24j {btc_change_24h:+.2f}% (>|{BTC_MOVE_CORRELATION_PCT}%|) + "
            f"{len(same_dir)} posisi searah — korelasi terlalu tinggi",
            detail={"btc": btc_change_24h},
        )
    return Verdict("exposure", True, f"{len(open_positions)}/{MAX_OPEN_POSITIONS} posisi, korelasi aman")


# ------------------------------------------------------------------ penilaian
def assess(
    *,
    direction: str,
    entry: float,
    sl: float,
    tp1: float,
    price: float,
    atr_pct_value: float | None,
    bias_4h: str,
    bias_1h: str,
    bias_1d: str,
    recent_high: float,
    recent_low: float,
    poi: dict[str, Any] | None,
    open_positions: list[dict[str, Any]] | None = None,
    btc_change_24h: float | None = None,
) -> Assessment:
    """Jalankan semua gate. Urutan tetap supaya outputnya selalu bisa dibandingkan."""
    poi_mid = float((poi or {}).get("mid") or 0.0)
    verdicts = (
        mtf_alignment(direction, bias_4h, bias_1h, bias_1d),
        poi_valid(direction, entry, (poi or {}).get("low"), (poi or {}).get("high"), (poi or {}).get("kind")),
        freshness(direction, tp1, poi_mid, price, recent_high, recent_low),
        sl_distance(direction, entry, sl, atr_pct_value),
        atr_min(atr_pct_value),
        exposure(direction, open_positions or [], btc_change_24h),
    )

    allowed = all(v.ok for v in verdicts if v.hard)
    tier = "SKIP"
    if allowed:
        cap = next((v.detail.get("tier_cap") for v in verdicts if v.rule == "mtf_alignment"), None)
        tier = cap or "STANDAR"
    return Assessment(allowed=allowed, tier=tier, verdicts=verdicts)
