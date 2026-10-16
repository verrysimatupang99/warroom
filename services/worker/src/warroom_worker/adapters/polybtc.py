"""Adapter skill «PolyBTC Momentum» (BTC 5m) → fakta War Room.

Skill hidup mandiri di ``/home/admin/polymarket-btc-5m`` (repo pihak ketiga
0xgetz/polymarket-btc-5m). Modul ini HANYA MEMBACA keluaran skill itu dan
menerbitkannya sebagai fakta — tidak mengubah satu baris pun kode skill, dan
tidak menyentuh jalur eksekusi/order apa pun.

Prinsip (selaras aturan kejujuran War Room):
- tidak ada angka karangan; kalau berkas tak ada, laporkan ``tersedia: false`` + alasannya;
- status ``live`` ditampilkan apa adanya dari meta skill (dry-run vs live);
- ini ALTERNATIF untuk pasar Polymarket, bukan pengganti arm D yang sudah ada.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

SKILL_DIR = Path(os.environ.get("POLYBTC_SKILL_DIR", "/home/admin/polymarket-btc-5m"))
RUNTIME = SKILL_DIR / "runtime"


def _baca_json(p: Path) -> dict[str, Any] | None:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _baca_jsonl(p: Path, limit: int = 400) -> list[dict[str, Any]]:
    """Baca sampai `limit` baris terakhir JSONL (tahan baris rusak)."""
    if not p.is_file():
        return []
    out: list[dict[str, Any]] = []
    try:
        with p.open(encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except Exception:
                    continue
    except Exception:
        return []
    return out[-limit:]


def _terbaru(pola: str) -> Path | None:
    kandidat = sorted(RUNTIME.glob(pola), key=lambda p: p.stat().st_mtime, reverse=True)
    return kandidat[0] if kandidat else None


def polybtc_ringkas() -> dict[str, Any]:
    """Ringkas keadaan skill BTC 5m untuk ditampilkan sebagai alternatif pasar.

    Mengembalikan dict siap-jadi nilai fakta. Tidak pernah melempar — kegagalan
    dilaporkan sebagai data, sesuai aturan "jangan menutupi kegagalan".
    """
    hasil: dict[str, Any] = {
        "tersedia": SKILL_DIR.is_dir(),
        "skill_dir": str(SKILL_DIR),
        "sumber": "0xgetz/polymarket-btc-5m",
        "pasar": "polymarket-btc-5m",
        "strategi": "momentum into close (entry ~120s sebelum tutup)",
    }

    if not hasil["tersedia"]:
        hasil["alasan"] = "direktori skill tidak ada"
        return hasil

    # --- keadaan sesi dari meta (dibuat oleh polybtc_ctl.sh) ---
    meta = _baca_json(RUNTIME / "polybtc.meta.json")
    if meta:
        hasil["sesi"] = {
            "profil": meta.get("profile"),
            "live": bool(meta.get("live")),
            "mode": "LIVE" if meta.get("live") else "DRY-RUN",
            "mulai": meta.get("startedAt"),
            "poll_sec": meta.get("pollSec"),
            "batas_menit": meta.get("entryTimeoutMin"),
        }
    else:
        hasil["sesi"] = {"mode": "belum-ada-sesi", "live": False}

    # --- apakah proses masih jalan? ---
    pid_file = RUNTIME / "polybtc.pid"
    jalan = False
    if pid_file.is_file():
        try:
            pid = int(pid_file.read_text().strip())
            os.kill(pid, 0)
            jalan = True
        except Exception:
            jalan = False
    hasil["jalan"] = jalan

    # --- snapshot observe terakhir (bukti jalur pasar hidup) ---
    obs = _baca_jsonl(RUNTIME / "latest_obs.jsonl", limit=120)
    if obs:
        terakhir = obs[-1]
        go = sum(1 for r in obs if r.get("preflight_ok"))
        hasil["observasi"] = {
            "n_snapshot": len(obs),
            "preflight_go": go,
            "terakhir": {
                "slug": terakhir.get("slug"),
                "detik_tersisa": terakhir.get("seconds_left"),
                "btc_move_usd": terakhir.get("btc_move_usd"),
                "up_ask": terakhir.get("up_ask"),
                "dn_ask": terakhir.get("dn_ask"),
                "spread": terakhir.get("spread"),
                "lolos": bool(terakhir.get("preflight_ok")),
                "alasan": (terakhir.get("reasons") or [])[:3],
            },
        }
    else:
        hasil["observasi"] = {"n_snapshot": 0, "alasan": "belum ada snapshot observe"}

    # --- laporan/laporan PnL bila ada (report JSON dari skill) ---
    rep = _terbaru("polybtc_report_*.json")
    if rep:
        d = _baca_json(rep)
        if d:
            kunci_ringkas = ("trades", "wins", "losses", "pnl_usd", "win_rate")
            hasil["laporan"] = {
                "berkas": rep.name,
                "ringkas": {k: d.get(k) for k in kunci_ringkas if k in d},
            }

    # --- catatan jujur ---
    catatan: list[str] = []
    if not jalan and hasil["sesi"].get("mode") != "belum-ada-sesi":
        catatan.append("sesi terakhir tidak berjalan (berhenti/selesai)")
    if not hasil["sesi"].get("live"):
        catatan.append("mode dry-run: tidak ada order nyata")
    catatan.append("alternatif BTC 5m — bukan pengganti arm D favorit")
    hasil["catatan"] = catatan

    return hasil
