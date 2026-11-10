"""Paper bot berbasis config strategy — eksekusi kertas stateful.

Bedanya dengan screener (stateless): paper bot MENGINGAT posisi terbuka,
membuka posisi saat sinyal entry, menutup saat SL/TP tersentuh, dan mencatat
setiap trade tertutup ke ledger. Inilah "cara kerja paper bot trading" yang
memakai strategy dari config — bukan hard-code.

State:
- <state_dir>/posisi_<config_id>.json : posisi terbuka (persist antar run).
- <state_dir>/trades_<config_id>.jsonl : ledger trade tertutup (append-only).

Tiap run (dipicu timer/worker):
1. Muat config + posisi terbuka.
2. Untuk tiap simbol, ambil candle terkini via provider.
3. Posisi terbuka: cek SL/TP intrabar -> tutup bila tersentuh, catat ke ledger.
4. Flat & slot tersedia & lolos filter+entry: buka posisi baru (dengan SL/TP).
5. Simpan state.

Sengaja sederhana & mandiri (tidak menyentuh PaperBroker verdicts.jsonl yang
ada) agar mudah diaudit dan tidak berisiko ke sistem live yang kompleks.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config import StrategyConfig
from .formula import evaluasi
from .provider import DataProvider


@dataclass
class Posisi:
    simbol: str
    arah: str
    entry: float
    sl: float
    tp: float
    size_usd: float
    waktu_entry: str

    def ke_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def _muat_posisi(path: Path) -> list[Posisi]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return [Posisi(**p) for p in data.get("posisi", [])]


def _simpan_posisi(path: Path, posisi: list[Posisi]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"posisi": [p.ke_dict() for p in posisi]}, indent=2), encoding="utf-8")
    tmp.replace(path)


def _catat_trade(ledger: Path, baris: dict[str, Any]) -> None:
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with open(ledger, "a", encoding="utf-8") as f:
        f.write(json.dumps(baris) + "\n")


def _variabel(cfg: StrategyConfig, candles: list[dict]) -> dict[str, list[Any]]:
    ctx = {"__candles__": candles}
    return {nama: evaluasi(eks, ctx) for nama, eks in cfg.variabel.items()}


def _kondisi(kondisi: list[str], ctx: dict) -> bool:
    for eks in kondisi:
        try:
            if not evaluasi(eks, ctx):
                return False
        except Exception:  # noqa: BLE001
            return False
    return True


def jalankan_paper_bot(cfg: StrategyConfig, provider: DataProvider, state_dir: Path,
                       modal_per_trade_usd: float = 100.0,
                       maks_posisi: int = 5) -> dict[str, Any]:
    """Jalankan satu siklus paper bot untuk satu config. Return ringkasan."""
    state_dir = Path(state_dir)
    path_posisi = state_dir / f"posisi_{cfg.id}.json"
    ledger = state_dir / f"trades_{cfg.id}.jsonl"

    posisi_aktif = _muat_posisi(path_posisi)
    simbol_terpakai = {p.simbol for p in posisi_aktif}
    ditutup: list[dict] = []
    dibuka: list[str] = []

    simbol_scan = list(dict.fromkeys(cfg.simbol + [p.simbol for p in posisi_aktif]))
    for simbol in simbol_scan:
        try:
            candles = provider.candles(simbol, cfg.waktu, 300)
        except Exception as e:  # noqa: BLE001
            print(f"  [{simbol}] data gagal: {e}")
            continue
        if not candles:
            continue
        c = candles[-1]

        # --- 1. kelola posisi terbuka untuk simbol ini (cukup 1 candle terakhir) ---
        for p in list(posisi_aktif):
            if p.simbol != simbol:
                continue
            hasil = _cek_tutup(p, c)
            if hasil:
                posisi_aktif.remove(p)
                simbol_terpakai.discard(simbol)
                baris = p.ke_dict()
                baris.update(hasil)
                baris["waktu_exit"] = datetime.now(UTC).isoformat()
                baris["config_id"] = cfg.id
                _catat_trade(ledger, baris)
                ditutup.append(baris)

        # --- 2. cari entry baru (butuh sejarah utk indikator; skip jika terlalu tipis) ---
        if len(candles) < 2:
            continue
        if simbol in simbol_terpakai or len(posisi_aktif) >= maks_posisi:
            continue
        variabel = _variabel(cfg, candles)
        ctx: dict[str, Any] = {
            "close": c["close"], "open": c["open"], "high": c["high"],
            "low": c["low"], "volume": c["volume"], "__candles__": candles,
        }
        for nama, arr in variabel.items():
            ctx[nama] = arr[-1]
        if not _kondisi(cfg.filter, ctx):
            continue
        atr_val = ctx.get("atr")
        if not isinstance(atr_val, (int, float)) or atr_val <= 0:
            continue
        posisi_baru = _buka(cfg, simbol, c, ctx, modal_per_trade_usd)
        if posisi_baru:
            posisi_aktif.append(posisi_baru)
            simbol_terpakai.add(simbol)
            dibuka.append(f"{simbol} {posisi_baru.arah} @{posisi_baru.entry:.4g}")

    _simpan_posisi(path_posisi, posisi_aktif)
    return {
        "config": cfg.id,
        "ditutup": ditutup,
        "dibuka": dibuka,
        "posisi_aktif": len(posisi_aktif),
    }


def _cek_tutup(p: Posisi, c: dict) -> dict[str, Any] | None:
    """Cek apakah posisi kena SL/TP di candle `c`. Return info exit atau None."""
    if p.arah == "long":
        if c["low"] <= p.sl:            # pesimis: SL diprioritaskan
            return _hasil(p, p.sl, "sl")
        if c["high"] >= p.tp:
            return _hasil(p, p.tp, "tp")
    else:
        if c["high"] >= p.sl:
            return _hasil(p, p.sl, "sl")
        if c["low"] <= p.tp:
            return _hasil(p, p.tp, "tp")
    return None


def _hasil(p: Posisi, exit_price: float, alasan: str) -> dict[str, Any]:
    risiko = abs(p.entry - p.sl)
    pnl = (exit_price - p.entry) if p.arah == "long" else (p.entry - exit_price)
    r = (pnl / risiko) if risiko > 0 else 0.0
    pnl_usd = (pnl / p.entry) * p.size_usd if p.entry > 0 else 0.0
    return {"exit": exit_price, "alasan_exit": alasan, "hasil_r": round(r, 3),
            "pnl_usd": round(pnl_usd, 2)}


def _buka(cfg: StrategyConfig, simbol: str, c: dict, ctx: dict,
          modal: float) -> Posisi | None:
    """Buka posisi baru memakai konteks lengkap (sudah berisi variabel bernama)."""
    entry = c["close"]
    if cfg.entry_long and _kondisi(cfg.entry_long, ctx):
        sl = entry - cfg.sl_atr * ctx["atr"]
        return Posisi(simbol, "long", entry, sl, entry + cfg.tp_rrr * (entry - sl),
                      modal, datetime.now(UTC).isoformat())
    if cfg.entry_short and _kondisi(cfg.entry_short, ctx):
        sl = entry + cfg.sl_atr * ctx["atr"]
        return Posisi(simbol, "short", entry, sl, entry - cfg.tp_rrr * (sl - entry),
                      modal, datetime.now(UTC).isoformat())
    return None
