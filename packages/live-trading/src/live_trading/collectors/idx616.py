"""Mirror read-only/wm tab IDX 616 Tencent (tanpa order, tanpa tulis ke sana).

Diambil: /api/events (sinyal terstruktur) + /api/journal (hasil).
Disimpan: state/idx616_mirror.json (50 event + 50 jurnal terakhir).
Ditampil: kartu IDX dashboard — dilabeli sumbernya jelas.
"""

from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path
from typing import Any

BASE = "http://43.155.219.37/idx616/api"
TTL_S = 900


def _get(path: str, timeout: float = 20.0) -> Any:
    req = urllib.request.Request(BASE + path, headers={"User-Agent": "war-room/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def _mirror_file(state_dir: Path) -> Path:
    return state_dir / "idx616_mirror.json"


def fetch() -> dict[str, Any]:
    """Ambil + ringkas. Gagal = {'error': ...} (dashboard tampil n/a)."""
    try:
        evs = _get("/events").get("events", [])
        jrn = _get("/journal").get("rows", [])
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}
    terbuka = [e for e in evs if e.get("status") == "CREATED"]
    tutup = [e for e in evs if e.get("status") == "CLOSED" and e.get("net_r") is not None]
    per_setup: dict[str, dict[str, float]] = {}
    for e in tutup:
        s = per_setup.setdefault(str(e.get("setup") or "?"), {"n": 0, "r": 0.0})
        s["n"] += 1
        try:
            s["r"] += float(e.get("net_r") or 0)
        except (ValueError, TypeError):
            pass
    return {
        "diambil": time.strftime("%Y-%m-%d %H:%M"),
        "terbuka": terbuka[-20:],
        "tutup": tutup[-20:],
        "per_setup": per_setup,
        "jurnal": jrn[-20:],
    }


def snapshot(state_dir: Path) -> dict[str, Any]:
    """Cache 15 menit — snapshot dibangun tiap 15 menit jadi 1x fetch.

    Standalone: kalau Tencent tak terjangkau, mirror terakhir tetap dipakai —
    ditandai ``dari_cache`` + umurnya, bukan diganti error. Jangan mengarang:
    tanpa mirror, error memang error.
    """
    p = _mirror_file(state_dir)
    basi: dict[str, Any] | None = None
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        import datetime as _dt

        ts = _dt.datetime.fromisoformat(d.get("diambil", "2000-01-01 00:00"))
        umur_s = (_dt.datetime.now() - ts).total_seconds()
        if umur_s < TTL_S:
            return d
        basi = {**d, "cache_umur_mnt": round(umur_s / 60, 1)}
    except (OSError, json.JSONDecodeError, ValueError):
        pass
    d = fetch()
    if "error" in d:
        if basi is not None:
            return {**basi, "dari_cache": True, "peringatan": d["error"]}
        return d
    try:
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(d), encoding="utf-8")
        tmp.replace(p)
    except OSError:
        pass
    return d
