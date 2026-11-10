"""Screener: jalankan formula strategy atas data TERKINI, laporkan setup live.

Bedanya dengan backtest: backtest menilai masa lalu; screener menjawab
"setup apa yang match HARI INI / SAAT INI?" untuk tiap simbol.

Cara kerja (stateless):
1. Muat config strategy.
2. Untuk tiap simbol, ambil candle terkini via provider.
3. Hitung variabel, evaluasi filter + entry_long/entry_short di bar TERAKHIR.
4. Laporkan simbol yang lolos (setup long / short / tidak ada).

Dipakai CLI ops/screener-strategy.py atau diimpor.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .config import StrategyConfig
from .formula import evaluasi
from .provider import DataProvider


@dataclass
class SetupScreener:
    simbol: str
    arah: str                 # "long" | "short" | "-"
    alasan: list[str]         # kondisi yang terpenuhi
    close: float
    konteks: dict[str, Any]   # nilai variabel di bar terakhir


def _nilai_variabel(cfg: StrategyConfig, candles: list[dict]) -> dict[str, list[Any]]:
    ctx = {"__candles__": candles}
    return {nama: evaluasi(eks, ctx) for nama, eks in cfg.variabel.items()}


def _kondisi_terpenuhi(kondisi: list[str], ctx: dict) -> tuple[bool, list[str]]:
    """Return (semua_lolos, daftar_kondisi_yang_lolos)."""
    lolos: list[str] = []
    for eks in kondisi:
        try:
            v = evaluasi(eks, ctx)
        except Exception:  # noqa: BLE001 — variabel None (warmup) -> gagal
            return False, lolos
        if v:
            lolos.append(eks)
        else:
            return False, lolos
    return True, lolos


def scan_satu(cfg: StrategyConfig, simbol: str, provider: DataProvider,
              timeframe: str | None = None, limit: int = 300) -> SetupScreener | None:
    """Scan satu simbol. Return SetupScreener bila ada setup, None bila tidak."""
    tf = timeframe or cfg.waktu
    candles = provider.candles(simbol, tf, limit)
    if len(candles) < 2:
        return None
    variabel = _nilai_variabel(cfg, candles)
    i = len(candles) - 1
    ctx: dict[str, Any] = {
        "close": candles[i]["close"], "open": candles[i]["open"],
        "high": candles[i]["high"], "low": candles[i]["low"],
        "volume": candles[i]["volume"], "__candles__": candles,
    }
    for nama, arr in variabel.items():
        ctx[nama] = arr[i]

    # filter wajib lolos dulu
    filter_ok, _ = _kondisi_terpenuhi(cfg.filter, ctx)
    if not filter_ok:
        return SetupScreener(simbol, "-", [], candles[i]["close"], ctx)

    if cfg.entry_long:
        ok, alasan = _kondisi_terpenuhi(cfg.entry_long, ctx)
        if ok:
            return SetupScreener(simbol, "long", alasan, candles[i]["close"], ctx)
    if cfg.entry_short:
        ok, alasan = _kondisi_terpenuhi(cfg.entry_short, ctx)
        if ok:
            return SetupScreener(simbol, "short", alasan, candles[i]["close"], ctx)
    return SetupScreener(simbol, "-", [], candles[i]["close"], ctx)


def scan_semua(cfg: StrategyConfig, provider: DataProvider,
               simbol: list[str] | None = None) -> list[SetupScreener]:
    """Scan semua simbol; kembalikan hanya yang punya setup (long/short)."""
    daftar = simbol or cfg.simbol
    hasil: list[SetupScreener] = []
    for s in daftar:
        try:
            setup = scan_satu(cfg, s, provider)
        except Exception as e:  # noqa: BLE001 — simbol gagal di-skip, bukan crash
            print(f"  [{s}] gagal: {e}")
            continue
        if setup and setup.arah != "-":
            hasil.append(setup)
    return hasil
