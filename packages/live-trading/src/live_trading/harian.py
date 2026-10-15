"""Strategi A: SMA trend-following harian (BTC/ETH/SOL spot) — 16 Okt 2026.

Sumber spesifikasi: docs/blueprint/spesifikasi/hermes-autotrade-agent2-20261016.md
(§3: daily trend, spot, tanpa short, anti-whipsaw 2 close, rebalance jarang).

Semua fungsi prices/atturan di sini MURNI (sinoid tanpa I/O) supaya backtest dan
paper memakai aturan yang sama — pelajaran 7 Okt tentang "dua jalur berbeda hasil".

Aturan inti (§3.2):
    LONG   = close di atas SMA(N) selama confirm_closes hari berturut-turut
    FLAT   = selain itu
    sizing = equal-weight antar aset yang LONG, cap 40% bucket per aset
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Any

UNIVERSE = ("BTCUSDT", "ETHUSDT", "SOLUSDT")
FEE_BPS_SPOT = 10.0        # Binance spot maker/taker 10 bps (0,1%)
SLIP_BPS_ASUMSI = 5.0      # §3.2: 0,05% slippage asumsi desain
CAP_BUCKET = 0.40
MIN_TRADE_USD = 5.0


def sma(values: list[float], period: int) -> float | None:
    """SMA sederhana; None bila data kurang."""
    if len(values) < period or period <= 0:
        return None
    return mean(values[-period:])


def sinyal_harian(
    closes: list[float], *, sma_n: int, confirm_closes: int,
) -> dict[str, Any]:
    """Sinyal LONG/FLAT dengan konfirmasi N close (murni, tanpa look-ahead).

    Setiap iterasi memakai SMA yang dihitung hanya dari data SEBELUM index itu:
    sinyal di hari i tidak boleh membaca close hari i (candle belum close).
    Return berisi `status` terakhir + jiarian keputusan harian untuk backtest.
    """
    if len(closes) < sma_n + confirm_closes + 1:
        return {"status": "FLAT", "kurang_data": True, "keputusan": []}

    keputusan: list[dict[str, Any]] = []
    status = "FLAT"
    streak_long = 0
    for i in range(1, len(closes)):
        # Semua angka di bawah ini dihitung dari data index < i (candle sudah close).
        window = closes[max(0, i - sma_n):i]
        rata = sma(window, sma_n) if len(window) >= sma_n else None
        atas = rata is not None and closes[i] > rata
        # Konfirmasi: hitung streak close-di-atas-SMA termasuk hari i.
        if atas:
            streak_long += 1
        else:
            streak_long = 0
        target = "LONG" if streak_long >= confirm_closes else "FLAT"
        if target != status:
            keputusan.append({
                "i": i, "dari": status, "ke": target,
                "close": closes[i], "sma": rata,
            })
            status = target
    return {"status": status, "keputusan": keputusan}


def hidup_per_aset(
    closes_per: dict[str, list[float]], sma_n: int, confirm_closes: int,
) -> dict[str, str]:
    """Status terakhir tiap aset (untuk intent harian)."""
    d = {}
    for pair, closes in closes_per.items():
        d[pair] = sinyal_harian(closes, sma_n=sma_n, confirm_closes=confirm_closes)["status"]
    return d


@dataclass
class BakBacktest:
    total_return: float
    max_drawdown: float
    sharpe: float | None
    calmar: float | None
    n_trade: float | int
    oos: bool
    # equity list utk kurva OOS/IS (bukan klaim, data mentah)
    equity: list[float]


def jalankan_backtest(
    closes: list[float], *, sma_n: int, confirm_closes: int,
    equity0: float = 10.0, fee_bps: float = FEE_BPS_SPOT + SLIP_BPS_ASUMSI,
    oos_frac: float = 0.30,
) -> BakBacktest:
    """Backtest harian: masuk/keluar sesuai sinyal, fee dihitung tiap pergantian.

    Tanpa look-ahead: status berubah SETELAH close hari i (dieksekusi di open i+1).
    OOS = 30% data terakhir (spec §3.4).
    """
    tak = sinyal_harian(closes, sma_n=sma_n, confirm_closes=confirm_closes)
    keputusan = {k["i"]: k for k in tak["keputusan"]}
    eq = equity0
    posisi: float = 0.0   # fraksi aset (0..1) yang dipegang
    eq_curve = [eq]
    n_ganti = 0
    hasil_harian: list[float] = []

    for i in range(1, len(closes)):
        ret = closes[i] / closes[i - 1] - 1.0
        pnl = posisi * ret
        eq *= (1.0 + pnl)
        # Eksekusi: keputusan baru ditindaklanjuti PADA OPEN i (pakai close i-1→i).
        k = keputusan.get(i)
        if k is not None and k["ke"] != (posisi > 0 and "LONG" or "FLAT"):
            biaya = (fee_bps / 10_000) * eq
            eq -= biaya
            n_ganti += 1
            posisi = 1.0 if k["ke"] == "LONG" else 0.0
        eq_curve.append(eq)
        hasil_harian.append(pnl)

    dd, peak = 0.0, equity0
    for e in eq_curve:
        peak = max(peak, e)
        dd = max(dd, 1 - e / peak)

    # OOS: jalankan ulang pada 30% data terakhir (split waktu murni).
    batas = int(len(closes) * (1 - oos_frac))
    oos_bak = jalankan_isi(closes[batas - sma_n:], sma_n=sma_n, confirm_closes=confirm_closes,
                           equity0=equity0, fee_bps=fee_bps)

    bak = BakBacktest(
        total_return=eq / equity0 - 1.0,
        max_drawdown=dd,
        sharpe=None if not hasil_harian else _sharpe(hasil_harian),
        calmar=None,
        n_trade=n_ganti,
        oos=False,
        equity=eq_curve,
    )
    bak.total_return_oos = oos_bak.total_return  # type: ignore[attr-defined]
    bak.max_drawdown_oos = oos_bak.max_drawdown  # type: ignore[attr-defined]
    return bak


def jalankan_isi(
    closes: list[float], *, sma_n: int, confirm_closes: int,
    equity0: float, fee_bps: float,
) -> BakBacktest:
    """Backtest pada THUNK data tertentu (dipakai untuk potongan OOS)."""
    tak = sinyal_harian(closes, sma_n=sma_n, confirm_closes=confirm_closes)
    keputusan = {k["i"]: k for k in tak["keputusan"]}
    eq = equity0
    posisi = 0.0
    eq_curve = [eq]
    n_ganti = 0
    harian: list[float] = []
    for i in range(1, len(closes)):
        ret = closes[i] / closes[i - 1] - 1.0
        eq *= (1.0 + posisi * ret)
        k = keputusan.get(i)
        if k is not None and (k["ke"] == "LONG") != (posisi > 0):
            eq -= (fee_bps / 10_000) * eq
            n_ganti += 1
            posisi = 1.0 if k["ke"] == "LONG" else 0.0
        eq_curve.append(eq)
        harian.append(posisi * ret)
    dd, peak = 0.0, equity0
    for e in eq_curve:
        p = max(peak, e)
        dd = max(dd, 1 - e / p)
        peak = max(peak, e)
    return BakBacktest(
        total_return=eq / equity0 - 1.0, max_drawdown=dd,
        sharpe=_sharpe(harian) if harian else None, calmar=None,
        n_trade=n_ganti, oos=True, equity=eq_curve,
    )


def _sharpe(hasil: list[float]) -> float | None:
    if len(hasil) < 2:
        return None
    rata = mean(hasil)
    var = mean([(x - rata) ** 2 for x in hasil])
    sd = var ** 0.5
    if sd == 0:
        return None
    # annualisasi kasar: 365 hari
    return round(rata / sd * (365 ** 0.5), 2)
