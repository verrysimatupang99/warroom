"""Backtest engine untuk strategy berbasis config.

Menjalankan SATU strategy config atas data candle historis dan menghasilkan
statistik: jumlah trade, winrate, profit factor, expectansi (R), max drawdown.

Kenapa ini inti: strategy yang bisa dikonfigurasi tapi tak bisa di-backtest
hanyalah memindahkan tebakan dari kode ke config. Backtest membuat "easy to
configure" jadi bermakna — kamu bisa MELIHAT apakah formula itu dulu berhasil
sebelum dipakai live/paper.

Model eksekusi (sederhana & konservatif):
- Entry di close bar sinyal.
- Stop loss = entry -/+ sl_atr * ATR(saat entry).
- Take profit = entry +/- tp_rrr * risiko (risiko = |entry - SL|).
- Tiap bar berikutnya: jika low/high menyentuh SL -> rugi; menyentuh TP -> profit.
- Jika SL dan TP tersentuh di bar yang sama -> diasumsikan SL kena dulu
  (pesimis, agar backtest tidak menipu).
- Satu posisi pada satu waktu (tidak menumpuk).
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import StrategyConfig
from .formula import evaluasi


@dataclass
class Trade:
    arah: str            # "long" | "short"
    entry_idx: int
    entry: float
    sl: float
    tp: float
    exit_idx: int = -1
    exit: float = 0.0
    hasil_r: float = 0.0
    alasan_exit: str = ""


@dataclass
class BacktestResult:
    simbol: str
    total_candle: int
    total_trade: int
    menang: int
    rugi: int
    winrate_pct: float
    profit_factor: float
    total_r: float
    expectansi_r: float
    max_drawdown_r: float
    rata_r_menang: float
    rata_r_rugi: float
    trades: list[Trade] = field(default_factory=list)


def baca_candles(csv_path: Path) -> list[dict[str, float]]:
    """Baca CSV candle (kolom: timestamp,open,high,low,close,volume,...)."""
    candles: list[dict[str, float]] = []
    if not Path(csv_path).exists():
        return candles
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                candles.append({
                    "time": float(row["timestamp"]),
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row.get("volume") or 0.0),
                })
            except (ValueError, TypeError, KeyError):
                continue
    return candles


def _precompute_variabel(cfg: StrategyConfig, candles: list[dict]) -> dict[str, list[Any]]:
    """Hitung tiap variabel bernama sekali atas seluruh candle (efisien, O(n))."""
    ctx_induk = {"__candles__": candles}
    hasil: dict[str, list[Any]] = {}
    for nama, ekspresi in cfg.variabel.items():
        hasil[nama] = evaluasi(ekspresi, ctx_induk)  # -> array sepanjang candle
    return hasil


def _konteks_bar(cfg: StrategyConfig, candles: list[dict], variabel: dict[str, list], i: int) -> dict:
    c = candles[i]
    ctx: dict[str, Any] = {
        "close": c["close"], "open": c["open"], "high": c["high"],
        "low": c["low"], "volume": c["volume"], "__candles__": candles,
    }
    for nama, arr in variabel.items():
        ctx[nama] = arr[i]
    return ctx


def _semua_terpenuhi(kondisi: list[str], ctx: dict) -> bool:
    for eks in kondisi:
        try:
            if not evaluasi(eks, ctx):
                return False
        except Exception:  # noqa: BLE001 — variabel None (warmup) -> skip bar
            return False
    return True


def jalankan_backtest(cfg: StrategyConfig, simbol: str, candles: list[dict]) -> BacktestResult:
    """Jalankan backtest satu simbol. Return statistik + daftar trade."""
    variabel = _precompute_variabel(cfg, candles)
    trades: list[Trade] = []
    posisi: Trade | None = None

    for i in range(len(candles)):
        c = candles[i]
        baru_tutup = False

        # --- kelola posisi terbuka dulu (cek SL/TP intrabar) ---
        if posisi is not None:
            keluar = False
            if posisi.arah == "long":
                kena_sl = c["low"] <= posisi.sl
                kena_tp = c["high"] >= posisi.tp
                if kena_sl:            # pesimis: SL diprioritaskan
                    _tutup(posisi, i, posisi.sl, "sl")
                    keluar = True
                elif kena_tp:
                    _tutup(posisi, i, posisi.tp, "tp")
                    keluar = True
            else:  # short
                kena_sl = c["high"] >= posisi.sl
                kena_tp = c["low"] <= posisi.tp
                if kena_sl:
                    _tutup(posisi, i, posisi.sl, "sl")
                    keluar = True
                elif kena_tp:
                    _tutup(posisi, i, posisi.tp, "tp")
                    keluar = True
            if keluar:
                trades.append(posisi)
                posisi = None
                baru_tutup = True   # jangan re-entry di bar yang sama (ambigu)

        # --- cari entry baru hanya jika flat dan tidak baru tutup di bar ini ---
        if posisi is None and not baru_tutup:
            ctx = _konteks_bar(cfg, candles, variabel, i)
            if not _semua_terpenuhi(cfg.filter, ctx):
                continue
            atr_val = ctx.get("atr")
            if not isinstance(atr_val, (int, float)) or atr_val <= 0:
                continue  # butuh ATR valid untuk SL/TP
            entry = c["close"]
            if cfg.entry_long and _semua_terpenuhi(cfg.entry_long, ctx):
                sl = entry - cfg.sl_atr * atr_val
                risiko = entry - sl                      # positif
                posisi = Trade("long", i, entry, sl, entry + cfg.tp_rrr * risiko)
            elif cfg.entry_short and _semua_terpenuhi(cfg.entry_short, ctx):
                sl = entry + cfg.sl_atr * atr_val
                risiko = sl - entry                      # positif (sl di atas entry)
                posisi = Trade("short", i, entry, sl, entry - cfg.tp_rrr * risiko)

    # tutup posisi menggantung di candle terakhir (mark-to-market)
    if posisi is not None:
        _tutup(posisi, len(candles) - 1, candles[-1]["close"], "akhir")
        trades.append(posisi)

    return _hitung_statistik(cfg, simbol, candles, trades)


def _tutup(t: Trade, idx: int, harga: float, alasan: str) -> None:
    t.exit_idx = idx
    t.exit = harga
    t.alasan_exit = alasan
    risiko = abs(t.entry - t.sl)
    if risiko <= 0:
        t.hasil_r = 0.0
        return
    pnl = (t.exit - t.entry) if t.arah == "long" else (t.entry - t.exit)
    t.hasil_r = pnl / risiko


def _hitung_statistik(cfg: StrategyConfig, simbol: str, candles: list[dict],
                      trades: list[Trade]) -> BacktestResult:
    menang = [t for t in trades if t.hasil_r > 0]
    rugi = [t for t in trades if t.hasil_r <= 0]
    total_r = sum(t.hasil_r for t in trades)
    gross_profit = sum(t.hasil_r for t in menang)
    gross_loss = abs(sum(t.hasil_r for t in rugi))
    pf = (gross_profit / gross_loss) if gross_loss > 0 else (float("inf") if gross_profit > 0 else 0.0)

    # max drawdown dalam satuan R (equity melengkung dari akumulasi R)
    equity = 0.0
    puncak = 0.0
    max_dd = 0.0
    for t in trades:
        equity += t.hasil_r
        puncak = max(puncak, equity)
        max_dd = max(max_dd, puncak - equity)

    wr = (len(menang) / len(trades) * 100) if trades else 0.0
    return BacktestResult(
        simbol=simbol,
        total_candle=len(candles),
        total_trade=len(trades),
        menang=len(menang),
        rugi=len(rugi),
        winrate_pct=round(wr, 1),
        profit_factor=round(pf, 2) if pf != float("inf") else float("inf"),
        total_r=round(total_r, 2),
        expectansi_r=round(total_r / len(trades), 3) if trades else 0.0,
        max_drawdown_r=round(max_dd, 2),
        rata_r_menang=round(gross_profit / len(menang), 2) if menang else 0.0,
        rata_r_rugi=round(-gross_loss / len(rugi), 2) if rugi else 0.0,
        trades=trades,
    )
