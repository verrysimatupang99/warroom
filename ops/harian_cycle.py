#!/usr/bin/env python3
"""Satu siklus Strategi A (SMA harian) — modal paper $10 (50% alokasi majors).

Spec: docs/blueprint/spesifikasi/hermes-autotrade-agent2-20261016.md §3.
Dompet terpisah: LT_HOME=/home/admin/live-trading/state-harian, equity $10.

Urutan siklus (idempoten per hari UTC):
1. Ambil close harian 1D per aset (spot publik Binance, tanpa key).
2. Sinyal LONG/FLAT (SMA100 + konfirmasi 2 close) — tanpa look-ahead.
3. Risk engine dompet: HALTED (kill drawdown / batas mingguan) → tutup semua.
4. Buka/tutup posisi paper (jalur tunggal decide_entry).
5. Terbitkan fakta `harian/status` (angka nyata untuk UI).

Timer: harian-cycle.timer (OnCalendar 00:20 UTC). Owner reset HALTED:
   sudo -u admin LT_HOME=/home/admin/live-trading/state-harian \
     .venv/bin/python -m ops.harian_reset
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
from pathlib import Path

HOME_HARIAN = "/home/admin/live-trading/state-harian"
ENV_H = {
    **os.environ,
    "WARROOM_STATE_DIR": HOME_HARIAN,
    "LT_HOME": HOME_HARIAN,
    "LT_EQUITY_USD": "10",
    "LT_PAPER": "true",
}
UTC = dt.UTC


def _stamp() -> str:
    return dt.datetime.now(UTC).strftime("%H:%M:%S")


def _path_state() -> Path:
    p = Path(HOME_HARIAN) / "state" / "harian_state.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _muat_state() -> dict:
    p = _path_state()
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"equity": 10.0, "peak": 10.0, "halted": False, "alasan_halted": None,
            "minggu": None, "minggu_realized_r": 0.0, "terproses": None}


def _simpan_state(st: dict) -> None:
    _path_state().write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")


def _klines(symbol: str) -> list[list]:
    """Close harian spot Binance (publik, tanpa key) — 3 halaman ≈ 4 tahun."""
    import httpx

    url = "https://api.binance.com/api/v3/klines"
    out: list[list] = []
    end: int | None = None
    for _ in range(3):
        params: dict = {"symbol": symbol, "interval": "1d", "limit": 1000}
        if end:
            params["endTime"] = end
        r = httpx.get(url, params=params, timeout=30.0)
        r.raise_for_status()
        rows = r.json()
        if not rows:
            break
        out = rows + out
        end = rows[0][0] - 1
        if len(rows) < 1000:
            break
    return out


def _publikasi(st: dict, sinyal: dict[str, str], harga: dict[str, float],
               dd_pct: float, minggu_pct: float) -> None:
    os.environ.update(ENV_H)
    from warroom_core.db import session_scope
    from warroom_worker.jobs.base import _tulis_fakta

    value = {
        "mode": "paper",
        "halted": bool(st.get("halted")),
        "alasan_halted": st.get("alasan_halted"),
        "equity_usd": round(st["equity"], 2),
        "peak_usd": round(st["peak"], 2),
        "drawdown_pct": round(dd_pct, 2),
        "minggu_realized_r": round(st.get("minggu_realized_r", 0.0), 2),
        "sinyal": sinyal,
        "harga": harga,
        "updated": dt.datetime.now(UTC).isoformat(timespec="seconds"),
    }
    with session_scope() as s:
        _tulis_fakta(s, kind="harian", key="status", value=value,
                     source="ops/harian_cycle.py", ttl_s=86400)


def main() -> int:
    os.environ.update(ENV_H)
    from live_trading.config import get_settings
    from live_trading.execution.paper import PaperBroker
    from live_trading.harian import hidup_per_aset

    stg = get_settings()
    b = PaperBroker(stg, venue="crypto")
    kini = dt.datetime.now(UTC)
    hari_iso = kini.date().isoformat()

    st = _muat_state()
    if st.get("terproses") == hari_iso and not st.get("halted"):
        print(f"[{_stamp()}] sudah diproses hari {hari_iso} — skip (idempoten)")
        return 0

    # 1-2. Data close + sinyal
    pasangan = [p.strip().upper() for p in stg.harian_universe.split(",") if p.strip()]
    closes_per: dict[str, list[float]] = {}
    harga: dict[str, float] = {}
    for pair in pasangan:
        try:
            rows = _klines(pair)
            closes_per[pair] = [float(k[4]) for k in rows]
            harga[pair] = closes_per[pair][-1]
        except Exception as exc:  # noqa: BLE001 — satu gagal, sisanya jalan
            print(f"[{_stamp()}] {pair}: data gagal ({type(exc).__name__})")
    if not closes_per:
        print(f"[{_stamp()}] semua data gagal — skip siklus")
        return 1

    sinyal = hidup_per_aset(closes_per, sma_n=stg.harian_sma_n,
                            confirm_closes=stg.harian_confirm_closes)
    print(f"[{_stamp()}] sinyal: {sinyal}")

    # 3. Mingguan: reset saat ganti minggu ISO
    minggu_kini = list(kini.isocalendar()[:2])
    if st.get("minggu") != minggu_kini:
        st["minggu"] = minggu_kini
        st["minggu_realized_r"] = 0.0

    # 4. Risk engine dompet: mingguan & kill drawdown
    dd_pct = (1 - st["equity"] / st["peak"]) * 100 if st["peak"] else 0.0
    minggu_loss_pct = -st.get("minggu_realized_r", 0.0) * stg.risk_per_trade_pct
    if minggu_loss_pct >= stg.harian_mingguan_loss_pct and not st.get("halted"):
        st["halted"] = True
        st["alasan_halted"] = f"loss mingguan {minggu_loss_pct:.1f}% >= {stg.harian_mingguan_loss_pct}%"
        print(f"[{_stamp()}] HALTED: {st['alasan_halted']}")
    if dd_pct >= stg.harian_kill_dd_pct and not st.get("halted"):
        st["halted"] = True
        st["alasan_halted"] = f"drawdown {dd_pct:.1f}% >= {stg.harian_kill_dd_pct}%"
        print(f"[{_stamp()}] KILL DRAWDOWN: {st['alasan_halted']} — tutup semua")

    if st.get("halted"):
        for pos in b.positions():
            if pos.pair in harga:
                b.close_position(pos.signal_id, harga[pos.pair], "closed_kill",
                                 note=f"halted pasca-tutup ({st.get('alasan_halted')})")

    # 5. Evaluasi open/close per aset
    buka = {p.pair: p for p in b.positions()}
    n_baru = 0
    for pair, status in sinyal.items():
        if pair not in harga:
            continue
        pos = buka.get(pair)
        if st.get("halted"):
            if pos is not None:
                b.close_position(pos.signal_id, harga[pair], "closed_halted",
                                 note=f"halted tetap tutup ({st.get('alasan_halted')})")
            continue
        if status == "LONG" and pos is None:
            nyala = [p2 for p2, s2 in sinyal.items() if s2 == "LONG" and p2 in harga]
            bobot = min(1.0 / max(1, len(nyala)), stg.harian_maks_bucket)
            size = round(st["equity"] * bobot, 2)
            if size < stg.harian_min_trade_usd:
                print(f"[{_stamp()}] {pair}: size ${size} < min ${stg.harian_min_trade_usd} — dilewati")
                continue
            stp = round(harga[pair] * (1 - stg.harian_capat_stop_pct / 100), 6)
            arah_note = (f"SMA{stg.harian_sma_n} harian, "
                         f"konfirmasi {stg.harian_confirm_closes} close")
            b.open_position(pair=pair, direction="LONG", entry=harga[pair],
                            stop=stp, tp1=None, tp2=None,
                            size_usd=size,
                            note=arah_note)
            n_baru += 1
            print(f"[{_stamp()}] buka {pair} LONG @ {harga[pair]} stop {stp} size ${size}")
        elif status == "FLAT" and pos is not None:
            rec = b.close_position(pos.signal_id, harga[pair], "closed_sma_flat",
                                   note=f"SMA{stg.harian_sma_n} turun — FLAT")
            ke_r = rec.get("r") or 0.0
            st["minggu_realized_r"] += float(ke_r)
            st["equity"] = max(0.5, st["equity"] * (1 + float(ke_r) * stg.risk_per_trade_pct / 100))
            st["peak"] = max(st["peak"], st["equity"])
            print(f"[{_stamp()}] tutup {pair} FLAT R={ke_r:+.2f} equity={st['equity']:.2f}")

    _publikasi(st, sinyal, harga, dd_pct, minggu_loss_pct)
    st["terproses"] = hari_iso
    _simpan_state(st)
    print(f"[{_stamp()}] selesai: equity ${st['equity']:.2f}, dd {dd_pct:.1f}%, {n_baru} entry baru")
    return 0


if __name__ == "__main__":
    sys.exit(main())
