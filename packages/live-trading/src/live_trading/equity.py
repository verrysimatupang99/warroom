"""Kurva ekuitas — ledger R per trade tertutup + statistik.

Pola diadaptasi dari tracker equity Tencent (ledger append-only
``signal_id, pair, direction, closed_at, status, r, note, source`` —
skema yang sama sudah dipakai paper executor di sini, jadi angka lama
dan baru bisa dibandingkan langsung).

Satu baris ledger = satu trade tertutup. Ledger tidak pernah ditulis
ulang selain append; ``sync`` di sini tidak ada karena paper executor
menulis langsung saat close — tidak ada sumber kedua yang perlu
direkonsiliasi (itu pelajaran dari Tencent: dua sumber kebenaran = drift).
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Any

from .config import Settings


def read_ledger(settings: Settings, venue: str = "crypto") -> list[dict[str, Any]]:
    """Baca semua baris ledger; baris rusak dilewati, bukan menggagalkan."""
    path = settings.venue_ledger_path(venue)
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict) and row.get("signal_id"):
            rows.append(row)
    rows.sort(key=lambda r: (str(r.get("closed_at") or ""), str(r.get("signal_id") or "")))
    return rows


def add_trade(
    settings: Settings,
    *,
    signal_id: str,
    pair: str,
    status: str,
    r: float,
    direction: str = "",
    note: str = "",
    closed_at: str | None = None,
    source: str = "manual",
    venue: str = "crypto",
) -> bool:
    """Catat satu trade manual. False kalau signal_id sudah ada (idempoten)."""
    if not signal_id:
        raise ValueError("signal_id wajib diisi")
    settings.state_dir.mkdir(parents=True, exist_ok=True)
    target_path = settings.venue_ledger_path(venue)
    if target_path.is_file():
        for line in target_path.read_text(encoding="utf-8").splitlines():
            try:
                if json.loads(line).get("signal_id") == signal_id:
                    return False
            except (json.JSONDecodeError, AttributeError):
                continue
    record = {
        "signal_id": signal_id,
        "pair": pair,
        "direction": direction,
        "closed_at": closed_at or _now_wib(),
        "status": status,
        "r": round(float(r), 3),
        "note": note,
        "source": source,
    }
    with target_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return True


def _now_wib() -> str:
    """Waktu sekarang WIB dengan offset +07:00 yang jujur (lihat paper.py).

    Sebelumnya menulis jam WIB berlabel `+00:00`: pembaca yang mengonversi
    zona waktu benar menampilkan +7 jam dari yang seharusnya (temuan QA 15 Okt).
    """
    return dt.datetime.now(dt.timezone(dt.timedelta(hours=7))).isoformat(timespec="seconds")


def curve(settings: Settings, venue: str = "crypto") -> dict[str, Any]:
    """Titik kurva kumulatif (dalam R) + statistik ledger."""
    rows = read_ledger(settings, venue=venue)
    pts: list[dict[str, Any]] = [{"i": 0, "r": 0.0, "cum": 0.0, "label": "start"}]
    cum = 0.0
    peak = 0.0
    max_dd = 0.0
    wins = 0
    losses = 0
    gross_win = 0.0
    gross_loss = 0.0
    for i, t in enumerate(rows, 1):
        try:
            r = float(t.get("r") or 0.0)
        except (TypeError, ValueError):
            r = 0.0
        cum += r
        peak = max(peak, cum)
        max_dd = max(max_dd, peak - cum)
        if r > 0:
            wins += 1
            gross_win += r
        elif r < 0:
            losses += 1
            gross_loss += abs(r)
        pts.append(
            {
                "i": i,
                "r": round(r, 3),
                "cum": round(cum, 3),
                "signal_id": t.get("signal_id"),
                "pair": t.get("pair"),
                "status": t.get("status"),
                "closed_at": t.get("closed_at"),
            }
        )
    n = len(rows)
    stats = {
        "trades": n,
        "total_r": round(cum, 2),
        "winrate_pct": round(100 * wins / n, 1) if n else None,
        "wins": wins,
        "losses": losses,
        "avg_r": round(cum / n, 3) if n else None,
        "max_drawdown_r": round(max_dd, 2),
        "profit_factor": round(gross_win / gross_loss, 2) if gross_loss else None,
        "expectancy_r": round(cum / n, 3) if n else None,
    }
    return {
        "points": pts,
        "trades": rows,
        "stats": stats,
        "since": rows[0].get("closed_at") if rows else None,
    }
