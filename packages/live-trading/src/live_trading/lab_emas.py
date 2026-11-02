"""Lab hipotesis strategi emas — pengujian cepat, banyak ide, satu gerbang.

Kenapa file terpisah dari ``riset_reaper.py``?
``riset_reaper.py`` menguji satu strategi secara mendalam (walk-forward, Monte
Carlo, sensitivitas). File ini untuk tahap sebelumnya: **menyaring banyak ide
dengan cepat** memakai aturan eksekusi yang identik di setiap jalur.

Kaidah yang dipakai semua hipotesis di sini (tanpa pengecualian):

1. Sinyal diputuskan setelah candle penutup, eksekusi di *open* candle berikutnya.
   Tidak ada harga masa depan yang ikut menghitung keputusan.
2. Candle dianggap berisi harga **bid**. Long dieksekusi di ask = bid + spread.
3. Bila stop dan target tersentuh di candle yang sama, dihitung **stop**.
4. Tidak ada trailing stop dan tidak ada partial take-profit.
5. Stop diletakkan di luar struktur harga (di luar high/low candle sinyal),
   bukan di titik yang jaraknya dipilih karena terlihat bagus.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

SPREAD_USD = 0.35
"""Spread Exness Standard Cent untuk emas, USD/oz."""

RISIKO_PER_TRADE = 0.01


# --------------------------------------------------------------------------
# Utilitas data & waktu
# --------------------------------------------------------------------------
def jam_utc(ms: int) -> int:
    return datetime.fromtimestamp(ms / 1000, UTC).hour


def tanggal_utc(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, UTC).date().isoformat()


def atr(high: list[float], low: list[float], close: list[float], periode: int) -> list[float]:
    """ATR Wilder. Nilai sebelum periode penuh adalah None-ish (0.0) dan tidak dipakai."""
    n = len(close)
    out = [0.0] * n
    if n <= periode:
        return out
    trs = [0.0] * n
    for i in range(1, n):
        trs[i] = max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1]))
    awal = sum(trs[1 : periode + 1]) / periode
    out[periode] = awal
    for i in range(periode + 1, n):
        out[i] = (out[i - 1] * (periode - 1) + trs[i]) / periode
    return out


def ema(nilai: list[float], periode: int) -> list[float]:
    n = len(nilai)
    out = [0.0] * n
    if n == 0:
        return out
    alpha = 2 / (periode + 1)
    acc = nilai[0]
    for i in range(n):
        acc = nilai[i] if i == 0 else acc + alpha * (nilai[i] - acc)
        out[i] = acc
    return out


# --------------------------------------------------------------------------
# Simulasi perdagangan (aturan identik dengan riset_reaper)
# --------------------------------------------------------------------------
def simulasikan(
    *,
    arah: str,
    entry: float,
    stop: float,
    target: float,
    high: list[float],
    low: list[float],
    masuk: int,
    batas_stop: int,
    batas_waktu_bars: int,
    spread: float,
) -> dict[str, Any]:
    """Telusuri candle mulai ``masuk`` sampai stop, target, atau waktu habis."""
    asli = abs(entry - stop)
    if asli <= 0:
        return {"hasil": "tidak_valid", "r": 0.0, "keluar_idx": masuk}

    if arah == "long":
        stop = stop - spread
        target = target + spread
    else:
        stop = stop + spread
        target = target - spread

    risiko = abs(entry - stop)
    if risiko <= 0:
        return {"hasil": "tidak_valid", "r": 0.0, "keluar_idx": masuk}

    n = len(high)
    akhir = min(batas_stop, masuk + batas_waktu_bars, n)
    for j in range(masuk, akhir):
        if arah == "long":
            if low[j] <= stop:
                return {"hasil": "sl", "r": -1.0, "keluar_idx": j}
            if high[j] >= target:
                return {"hasil": "tp", "r": (target - entry) / risiko, "keluar_idx": j}
        else:
            if high[j] >= stop:
                return {"hasil": "sl", "r": -1.0, "keluar_idx": j}
            if low[j] <= target:
                return {"hasil": "tp", "r": (entry - target) / risiko, "keluar_idx": j}

    # Batas waktu: hitung hasil di harga penutup candle terakhir jendela.
    j = akhir - 1
    return {"hasil": "waktu", "r": 0.0, "keluar_idx": j, "_butuh_close": True}


def jalankan_sinyal(
    data: dict[str, list[Any]],
    sinyal: Callable[[int], dict[str, Any] | None],
    *,
    mulai: int,
    selesai: int,
    spread: float = SPREAD_USD,
    batas_waktu_bars: int = 96,
) -> list[dict[str, Any]]:
    """Jalankan fungsi sinyal bar demi bar, tanpa posisi tumpang tindih.

    ``sinyal(i)`` harus mengembalikan ``{"arah", "stop", "target"}`` atau ``None``.
    Stop/target berupa **harga**. Eksekusi dilakukan di open candle ``i+1``.
    """
    open_ = data["open"]
    high = data["high"]
    low = data["low"]
    close = data["close"]
    waktu = data["waktu"]
    n = len(close)
    trades: list[dict[str, Any]] = []

    i = max(mulai, 1)
    batas = min(selesai, n - 1)
    while i < batas:
        s = sinyal(i)
        if s is None:
            i += 1
            continue
        masuk = i + 1
        if masuk >= batas:
            break
        entry = float(open_[masuk])
        r = simulasikan(
            arah=s["arah"],
            entry=entry,
            stop=float(s["stop"]),
            target=float(s["target"]),
            high=high,
            low=low,
            masuk=masuk,
            batas_stop=batas,
            batas_waktu_bars=batas_waktu_bars,
            spread=spread,
        )
        if r["hasil"] == "tidak_valid":
            i += 1
            continue

        risiko_asli = abs(entry - float(s["stop"]))
        biaya = spread / risiko_asli if risiko_asli > 0 else math.inf

        if r.get("_butuh_close"):
            j = r["keluar_idx"]
            if s["arah"] == "long":
                r_bersih = (close[j] - entry - spread) / risiko_asli
            else:
                r_bersih = (entry - close[j] - spread) / risiko_asli
            r_kotor = r_bersih + biaya
        else:
            r_bersih = float(r["r"]) - biaya
            r_kotor = float(r["r"])

        trades.append(
            {
                "time": datetime.fromtimestamp(waktu[i] / 1000, UTC).isoformat(),
                "idx": i,
                "jam": jam_utc(waktu[i]),
                "arah": s["arah"],
                "entry": entry,
                "stop": float(s["stop"]),
                "target": float(s["target"]),
                "risiko_usd": round(risiko_asli, 3),
                "hasil": r["hasil"],
                "r_kotor": round(r_kotor, 4),
                "biaya_r": round(biaya, 4),
                "r_bersih": round(r_bersih, 4),
            }
        )
        i = max(r["keluar_idx"] + 1, masuk + 1)
    return trades


# --------------------------------------------------------------------------
# Metrik & gerbang
# --------------------------------------------------------------------------
def metrik(trades: list[dict[str, Any]]) -> dict[str, Any]:
    if not trades:
        return {"n": 0}
    rs = [t["r_bersih"] for t in trades]
    menang = [r for r in rs if r > 0]
    total = sum(rs)
    gross_win = sum(menang)
    gross_loss = abs(sum(r for r in rs if r <= 0))

    ekuitas = puncak = 1.0
    dd = 0.0
    for r in rs:
        ekuitas *= 1 + RISIKO_PER_TRADE * r
        puncak = max(puncak, ekuitas)
        dd = max(dd, (puncak - ekuitas) / puncak)

    sd = statistics.pstdev(rs) if len(rs) > 1 else 0.0
    t_stat = statistics.fmean(rs) / (sd / math.sqrt(len(rs))) if sd > 0 else None

    return {
        "n": len(rs),
        "win_rate": round(len(menang) / len(rs), 4),
        "expectancy_r": round(total / len(rs), 4),
        "profit_factor": round(gross_win / gross_loss, 3) if gross_loss > 0 else None,
        "r_kotor_total": round(sum(t["r_kotor"] for t in trades), 2),
        "r_bersih_total": round(total, 2),
        "max_dd_pct": round(dd * 100, 2),
        "t_stat": round(t_stat, 2) if t_stat is not None else None,
    }


@dataclass(frozen=True)
class Gerbang:
    """Ambang go/no-go. Kandidat harus lolos SEMUA, bukan sebagian.

    Ambang ini ditetapkan sebelum melihat hasil, supaya tidak ada penyesuaian
    lambe setelah angka keluar.
    """

    min_n: int = 100
    min_expectancy: float = 0.05
    min_pf: float = 1.15
    min_t_stat: float = 2.0
    max_dd_pct: float = 10.0

    def periksa(self, m: dict[str, Any]) -> tuple[bool, list[str]]:
        gagal = []
        if m.get("n", 0) < self.min_n:
            gagal.append(f"n {m.get('n')} < {self.min_n}")
        if m.get("expectancy_r", math.inf) < self.min_expectancy:
            gagal.append(f"expectancy {m.get('expectancy_r')} < {self.min_expectancy}")
        pf = m.get("profit_factor")
        if pf is None or pf < self.min_pf:
            gagal.append(f"PF {pf} < {self.min_pf}")
        t = m.get("t_stat")
        if t is None or t < self.min_t_stat:
            gagal.append(f"t {t} < {self.min_t_stat}")
        if m.get("max_dd_pct", math.inf) > self.max_dd_pct:
            gagal.append(f"DD {m.get('max_dd_pct')}% > {self.max_dd_pct}%")
        return (not gagal), gagal


def blok_kronologis(trades: list[dict[str, Any]], k: int = 5) -> list[dict[str, Any]]:
    """Bagi trade per urutan waktu; edge asli muncul di mayoritas blok."""
    if not trades:
        return []
    per = math.ceil(len(trades) / k)
    hasil = []
    for b in range(k):
        potong = trades[b * per : (b + 1) * per]
        if not potong:
            continue
        m = metrik(potong)
        m["blok"] = b + 1
        m["dari"] = potong[0]["time"][:10]
        m["sampai"] = potong[-1]["time"][:10]
        hasil.append(m)
    return hasil


def mc_bootstrap(rs: list[float], iterasi: int = 2000, seed: int = 7) -> dict[str, float]:
    import random

    if not rs:
        return {}
    rnd = random.Random(seed)
    n = len(rs)
    exp = []
    for _ in range(iterasi):
        exp.append(sum(rnd.choice(rs) for _ in range(n)) / n)
    exp.sort()
    return {
        "p_expectancy_positif": round(sum(1 for e in exp if e > 0) / iterasi, 4),
        "p05": round(exp[int(0.05 * iterasi)], 4),
        "p50": round(exp[int(0.50 * iterasi)], 4),
        "p95": round(exp[int(0.95 * iterasi)], 4),
    }
