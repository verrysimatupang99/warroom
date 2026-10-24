"""Radar rantai — dijalankan **lokal di Webdock** (recreate, bukan lagi SSH ke Azure).

Latar (6 Okt 2026, keputusan owner): server Azure akan dimatikan, jadi radar tidak boleh
bergantung pada SSH ke `20.212.52.5`. Algoritma yang dipakai adalah algoritma yang sama
yang sudah terbukti di VM (`chain_radar.py`, identik byte-per-byte dengan salinan
`~/gmgn-scan/chain_radar.py`), tetapi:

- dipanggil dari domain ini (`lt radar-update`), bukan dari cron VM;
- tulis state **lokal** ke `state/radar_state.json` (sumber kebenaran baru);
- tetap **baca-saja** terhadap pasar: hanya `gmgn-cli market trending`, `gas-price`.

Yang dibaca di sini hanya keluaran `gmgn-cli` (publik, tanpa kunci tulis). Tidak ada
wallet, tidak ada private key, tidak ada order.
"""
from __future__ import annotations

import json
import logging
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

__all__ = ["LAUNCH", "ChainStat", "diff_and_alert", "jalankan_radar", "scan_chain"]

GMGN = "gmgn-cli"

# Tanggal mainnet (UTC). Tidak diketahui -> None, umur dilaporkan "?".
LAUNCH: dict[str, str] = {
    "eth": "2015-07-30",
    "bsc": "2020-09-01",
    "sol": "2020-03-16",
    "arbitrum": "2023-03-23",
    "base": "2023-08-09",
    "hyperevm": "2025-02-18",  # HyperEVM mainnet (chain id 999)
    "stable": "2025-12-08",  # StableChain (Tether-aligned, USDT gas)
    "robinhood": "2026-07-01",  # Arbitrum L2
    "arc": "2026-09-16",  # Circle L1
}

# Heuristik jendela insentif.
YOUTH_HOT = 30  # hari — masih fase insentif tinggi
YOUTH_PRIME = 14  # hari — cukup awal untuk reward berlebih
VL_GOOD = 0.5  # agregat 24 jam vol / likuiditas
VL_DEAD = 0.25

# Chain bawaan: sama dengan yang dipantau di VM (urutan lama: robinhood,arc,hyperevm,stable,base).
CHAINS_BAWAAN = "robinhood,arc,hyperevm,stable,base"


def _run(args: list[str], *, retries: int = 3) -> dict[str, Any] | None:
    for a in range(retries):
        try:
            p = subprocess.run(  # noqa: S603 — perintah tetap, bukan input pengguna
                [GMGN, *args], capture_output=True, text=True, timeout=90
            )
        except (OSError, subprocess.TimeoutExpired):
            if a < retries - 1:
                time.sleep(1.5 * (a + 1))
                continue
            return None
        out = (p.stdout or "").strip()
        if p.returncode == 0 and out:
            try:
                return json.loads(out)
            except json.JSONDecodeError:
                return None
        err = (p.stderr or "") + out
        if "RATE_LIMIT" in err or "429" in err:
            wait = 30
            try:
                wait = max(5, min(300, int(json.loads(out).get("reset_at", 0) - time.time())))
            except Exception:  # noqa: BLE001 — pesan galat bebas; jangan gagalkan karena format
                logging.getLogger(__name__).debug("operasi dilewati", exc_info=True)
            if a < retries - 1:
                print(f"  [rate-limit] {wait}s", file=sys.stderr)
                time.sleep(min(wait, 60))
                continue
        if a < retries - 1:
            time.sleep(1.5 * (a + 1))
            continue
        print(f"  [fail] {' '.join(args)}: {err[:160]}", file=sys.stderr)
        return None
    return None


def _f(v: Any, d: float = 0.0) -> float:
    try:
        if v is None or v == "":
            return d
        return float(v)
    except (TypeError, ValueError):
        return d


def _i(v: Any, d: int = 0) -> int:
    try:
        if v is None or v == "":
            return d
        return int(float(v))
    except (TypeError, ValueError):
        return d


@dataclass
class ChainStat:
    chain: str
    age_days: int | None
    pools: int
    total_liq: float
    total_vol_24h: float
    total_mcap: float
    avg_vl: float
    best_vl: float
    viable: int  # lolos gerbang keamanan + kedalaman
    hp_count: int  # high-potential (vl>=2, liq>=50k, aman)
    native_usd: float
    window: str
    note: str


def _klasifikasi(age: int | None, avg_vl: float) -> tuple[str, str]:
    if age is None:
        return "UNKNOWN", "tanggal listing belum pasti — verifikasi manual"
    if age <= YOUTH_PRIME and avg_vl >= VL_GOOD:
        return "PRIME", f"{age}d old, avg V/L {avg_vl:.2f} — puncak fase insentif"
    if age <= YOUTH_HOT and avg_vl >= VL_GOOD:
        return "OPEN", f"{age}d old, avg V/L {avg_vl:.2f} — masih membayar"
    if age <= 90 and avg_vl >= VL_DEAD:
        return "CLOSING", f"{age}d old, avg V/L {avg_vl:.2f} — menipis"
    if age > 90:
        return "CLOSED", f"{age}d old, avg V/L {avg_vl:.2f} — mature/kompetitif"
    return "DRY", f"{age}d old, avg V/L {avg_vl:.2f} — volume hilang"


def scan_chain(ch: str, limit: int) -> ChainStat:
    """Satu chain: trending 1h + gas price → statistik + verdict jendela."""
    d = _run(["market", "trending", "--chain", ch, "--interval", "1h", "--limit", str(limit), "--raw"])
    rows = ((d or {}).get("data") or {}).get("rank") or []

    total_liq = total_vol = total_mcap = 0.0
    vls: list[float] = []
    viable = hp = 0
    for r in rows:
        liq = _f(r.get("liquidity"))
        vol = _f(r.get("volume_24h")) or _f(r.get("volume")) * 24.0
        mc = _f(r.get("market_cap"))
        rug = _f(r.get("rug_ratio"))
        bund = _f(r.get("bundler_rate"))
        ins = _f(r.get("rat_trader_amount_rate"))
        top10 = _f(r.get("top_10_holder_rate"))
        hold = _i(r.get("holder_count"))
        total_liq += liq
        total_vol += vol
        total_mcap += mc
        if liq > 0:
            vl = vol / liq
            vls.append(vl)
            safe = rug <= 0.30 and bund <= 0.20 and ins <= 0.10 and top10 <= 0.25
            if safe and liq >= 20_000 and hold >= 150:
                viable += 1
                if vl >= 2.0 and liq >= 50_000:
                    hp += 1

    avg_vl = sum(vls) / len(vls) if vls else 0.0
    best_vl = max(vls) if vls else 0.0

    age: int | None = None
    ld = LAUNCH.get(ch)
    if ld:
        try:
            age = (date.today() - datetime.strptime(ld, "%Y-%m-%d").date()).days
        except ValueError:
            age = None

    g = _run(["gas-price", "--chain", ch, "--raw"])
    native = _f((g or {}).get("native_token_usd_price"), 0.0)

    window, note = _klasifikasi(age, avg_vl)
    return ChainStat(
        chain=ch,
        age_days=age,
        pools=len(rows),
        total_liq=round(total_liq),
        total_vol_24h=round(total_vol),
        total_mcap=round(total_mcap),
        avg_vl=round(avg_vl, 3),
        best_vl=round(best_vl, 2),
        viable=viable,
        hp_count=hp,
        native_usd=round(native, 4),
        window=window,
        note=note,
    )


def _muat_state(path: str | Path) -> dict[str, dict[str, Any]]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return {s["chain"]: s for s in data if isinstance(s, dict) and s.get("chain")}
    except (OSError, json.JSONDecodeError):
        return {}


def diff_and_alert(prev: dict[str, dict[str, Any]], now: list[ChainStat]) -> list[str]:
    """Bandingkan dengan snapshot sebelumnya; kembalikan peringatan yang bisa dibaca."""
    alerts: list[str] = []
    rank = {"PRIME": 0, "OPEN": 1, "UNKNOWN": 2, "CLOSING": 3, "DRY": 4, "CLOSED": 5}
    for s in now:
        p = prev.get(s.chain)
        if not p:
            age = f"{s.age_days}d" if s.age_days is not None else "?"
            alerts.append(
                f"NEW  {s.chain}: first sighting, window={s.window} "
                f"(age {age}, avg V/L {s.avg_vl:.2f})"
            )
            continue
        if rank.get(s.window, 9) < rank.get(p.get("window", "UNKNOWN"), 9):
            alerts.append(
                f"UP   {s.chain}: {p.get('window')} -> {s.window} "
                f"(age {p.get('age_days')}d->{s.age_days}d, avg V/L {p.get('avg_vl'):.2f}->{s.avg_vl:.2f})"
            )
        if rank.get(s.window, 9) > rank.get(p.get("window", "UNKNOWN"), 9):
            alerts.append(
                f"DOWN {s.chain}: {p.get('window')} -> {s.window} "
                f"(avg V/L {p.get('avg_vl'):.2f}->{s.avg_vl:.2f})"
            )
        pv = p.get("avg_vl") or 0
        if pv and s.avg_vl > pv * 1.8 and s.avg_vl >= 1.0:
            naik = (s.avg_vl / pv - 1) * 100
            alerts.append(
                f"SPIKE {s.chain}: avg V/L {pv:.2f} -> {s.avg_vl:.2f} (+{naik:.0f}%) — volume bangun"
            )
        ph = p.get("hp_count") or 0
        if s.hp_count >= 3 and ph < 3:
            alerts.append(f"HP   {s.chain}: high-potential pools {ph} -> {s.hp_count}")
    return alerts


def jalankan_radar(
    *,
    chains: str = CHAINS_BAWAAN,
    limit: int = 60,
    state_path: str | Path,
    tulis_cache: bool = True,
) -> dict[str, Any]:
    """Jalankan radar untuk `chains`, tulis state lokal, kembalikan ringkasan.

    Mengembalikan dict dengan ``hasil`` (daftar stat), ``alerts``, ``state``,
    ``diambil_epoch``. Bila semua chain gagal, ``hasil`` kosong dan state lama
    **tidak** ditimpa (gagal ≠ kosong — cache jangan dihapus karena jaringan putus).
    """
    daftar = [c.strip() for c in chains.split(",") if c.strip()]
    prev = _muat_state(state_path) if tulis_cache else {}
    stats: list[ChainStat] = []
    for ch in daftar:
        print(f"  scanning {ch}...", file=sys.stderr)
        try:
            stats.append(scan_chain(ch, limit))
        except Exception as e:  # noqa: BLE001 — satu chain gagal jangan hentikan sisanya
            print(f"  [skip] {ch}: {e}", file=sys.stderr)
        time.sleep(0.8)

    alerts = diff_and_alert(prev, stats)

    out: dict[str, Any] = {
        "diambil_epoch": time.time(),
        "sumber": "lokal",
        "chains": [asdict(s) for s in stats],
        "alerts": alerts,
    }
    if tulis_cache and stats:
        p = Path(state_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out
