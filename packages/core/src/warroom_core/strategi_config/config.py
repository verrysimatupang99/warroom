"""Loader & validator config strategy (YAML) — fail-closed.

Config strategy menjelaskan SATU strategy secara deklaratif: variabel yang
dipakai, filter, kondisi entry/exit, dan manajemen risiko. Strategy = config,
bukan kode. Menambah/mengubah strategy = mengedit YAML, bukan Python.

Skema minimal (contoh):
    id: breakout_crypto
    nama: Breakout Crypto
    market: crypto
    simbol: [BTCUSDT, ETHUSDT]
    waktu: 15m
    variabel:
      rsi: RSI(14)
      ema_cepat: EMA(20)
      ema_lambat: EMA(200)
      atr: ATR(14)
    filter:
      - "atr > 0"
    entry_long:
      - "rsi < 35"
      - "ema_cepat > ema_lambat"
    exit:
      sl_atr: 1.5
      tp_rrr: 2.0
    risiko:
      risiko_per_trade_pct: 1.0

Validator menolak config yang tidak lengkap (fail-closed), bukan menebak.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .formula import FormulaError


class ConfigError(Exception):
    """Config strategy tidak valid / tidak lengkap."""


@dataclass
class StrategyConfig:
    id: str
    nama: str
    market: str
    simbol: list[str]
    waktu: str
    variabel: dict[str, str]                 # nama -> ekspresi indikator
    filter: list[str] = field(default_factory=list)
    entry_long: list[str] = field(default_factory=list)
    entry_short: list[str] = field(default_factory=list)
    sl_atr: float = 1.5
    tp_rrr: float = 2.0
    risiko_per_trade_pct: float = 1.0
    sumber: str = ""


def _wajib(data: dict, kunci: str, tipe) -> Any:
    if kunci not in data:
        raise ConfigError(f"kunci wajib hilang: {kunci}")
    val = data[kunci]
    if tipe is list and not isinstance(val, list):
        raise ConfigError(f"{kunci} harus list")
    if tipe is str and not isinstance(val, str):
        raise ConfigError(f"{kunci} harus string")
    return val


def muat_config(path: Path) -> StrategyConfig:
    """Muat & validasi config strategy dari file YAML."""
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"file config tidak ada: {path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise ConfigError(f"YAML tidak valid: {e}") from e
    if not isinstance(data, dict):
        raise ConfigError("config harus berupa mapping YAML")

    cfg = StrategyConfig(
        id=_wajib(data, "id", str),
        nama=_wajib(data, "nama", str),
        market=_wajib(data, "market", str),
        simbol=_wajib(data, "simbol", list),
        waktu=_wajib(data, "waktu", str),
        variabel=data.get("variabel", {}) or {},
    )
    cfg.filter = data.get("filter", []) or []
    cfg.entry_long = data.get("entry_long", []) or []
    cfg.entry_short = data.get("entry_short", []) or []
    exit_cfg = data.get("exit", {}) or {}
    cfg.sl_atr = float(exit_cfg.get("sl_atr", 1.5))
    cfg.tp_rrr = float(exit_cfg.get("tp_rrr", 2.0))
    risiko = data.get("risiko", {}) or {}
    cfg.risiko_per_trade_pct = float(risiko.get("risiko_per_trade_pct", 1.0))
    cfg.sumber = str(path)

    if not cfg.simbol:
        raise ConfigError("simbol tidak boleh kosong")
    if not cfg.entry_long and not cfg.entry_short:
        raise ConfigError("butuh minimal satu dari entry_long / entry_short")

    # Validasi formula saat load (fail-closed): setiap ekspresi harus parse-able
    # dan hanya memakai variabel yang didefinisikan / bawaan.
    bawaan = {"close", "open", "high", "low", "volume", "__candles__"}
    dikenal = set(cfg.variabel.keys()) | bawaan
    semua_ekspresi = list(cfg.variabel.values()) + cfg.filter + cfg.entry_long + cfg.entry_short
    for eks in semua_ekspresi:
        try:
            # validasi parse + nama variabel (pakai konteks dummy berisi nama dikenal)
            _validasi_nama(eks, dikenal)
        except FormulaError as e:
            raise ConfigError(f"formula tidak valid di config: {eks!r} ({e})") from e
    return cfg


def _validasi_nama(ekspresi: str, dikenal: set[str]) -> None:
    """Pastikan semua Name (referensi variabel) ada di `dikenal` atau indikator.

    Nama yang jadi FUNGSI pemanggilan indikator (mis. RSI dalam RSI(14)) dikecualikan —
    itu bukan variabel. Hanya Name yang dipakai sebagai NILAI yang divalidasi.
    """
    import ast

    from .variabel import INDIKATOR
    tree = ast.parse(ekspresi, mode="eval")
    # kumpulkan nama fungsi indikator yang dipanggil, agar tak dianggap variabel
    nama_fungsi = {
        node.func.id for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id not in nama_fungsi:
            if node.id not in dikenal and node.id not in INDIKATOR:
                raise FormulaError(f"variabel '{node.id}' tidak didefinisikan di config")
