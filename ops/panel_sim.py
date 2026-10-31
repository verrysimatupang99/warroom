#!/usr/bin/env python3
"""Simulator 3 panel (A/B/C) untuk membandingkan skema sizing + daily ratchet.

Tidak mengirim order. Membaca sinyal War Room + harga broker, lalu menjalankan
tiga portofolio virtual secara paralel dengan aturan berbeda. Tujuannya
memilih skema mana yang bertahan sebelum uang sungguhan dipakai.

Dijalankan oleh systemd timer tiap 30 detik (lihat ops/warroom-panel-sim.*).
"""

from __future__ import annotations

import csv
import json
import os
import urllib.request
from datetime import date, datetime
from pathlib import Path

API = os.environ.get("WARROOM_API", "http://127.0.0.1:8800")
STATE = Path(os.environ.get("PANEL_STATE", "/var/lib/warroom/panels.json"))
LOG = Path(os.environ.get("PANEL_LOG", "/var/lib/warroom/panels_trades.csv"))
MODAL_AWAL = 500.0

# Skema: (nama, risiko per trade % modal, target harian %, stop harian %, maks trade/hari)
SKEMA = [
    ("A", 2.5, 5.0, 5.0, 5),
    ("B", 5.0, 10.0, 10.0, 5),
    ("C", 7.5, 15.0, 10.0, 5),
]
ARM_RASIO = 0.60   # ratchet aktif setelah 60% dari target
LOCK_RASIO = 0.60  # kunci di 60% dari puncak


def ambil(path: str, timeout: float = 20.0) -> dict | None:
    try:
        with urllib.request.urlopen(f"{API}{path}", timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def muat() -> dict:
    if STATE.exists():
        try:
            return json.loads(STATE.read_text())
        except Exception:
            pass
    return {}


def simpan(state: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=1))
    tmp.replace(STATE)


def panel_baru(nama: str, risk: float, target: float, stop: float, maks: int) -> dict:
    return {
        "nama": nama, "risk_pct": risk, "target_pct": target,
        "stop_pct": stop, "max_trades": maks,
        "modal_awal": MODAL_AWAL, "ekuitas": MODAL_AWAL,
        "hari": "", "pnl_hari": 0.0, "puncak_hari": 0.0, "floor": None,
        "berhenti": False, "alasan_berhenti": "",
        "trades_hari": 0, "posisi": None, "riwayat": [],
    }


def reset_harian(p: dict, hari: str) -> None:
    p.update({"hari": hari, "pnl_hari": 0.0, "puncak_hari": 0.0, "floor": None,
              "berhenti": False, "alasan_berhenti": "", "trades_hari": 0})


def persen(p: dict) -> float:
    basis = p["ekuitas"] - p["pnl_hari"]
    return 0.0 if basis <= 0 else 100.0 * p["pnl_hari"] / basis


def perbarui_ratchet(p: dict) -> None:
    if p["berhenti"]:
        return
    x = persen(p)
    p["puncak_hari"] = max(p["puncak_hari"], x)
    if p["puncak_hari"] >= ARM_RASIO * p["target_pct"]:
        kunci = LOCK_RASIO * p["puncak_hari"]
        p["floor"] = kunci if p["floor"] is None else max(p["floor"], kunci)
    if x >= p["target_pct"]:
        p["berhenti"], p["alasan_berhenti"] = True, f"target {x:.2f}% >= {p['target_pct']}%"
    elif p["floor"] is not None and x <= p["floor"]:
        p["berhenti"], p["alasan_berhenti"] = True, f"ratchet {x:.2f}% <= floor {p['floor']:.2f}%"
    elif x <= -p["stop_pct"]:
        p["berhenti"], p["alasan_berhenti"] = True, f"stop {x:.2f}% <= -{p['stop_pct']}%"


def tutup(p: dict, harga: float, waktu: str) -> None:
    pos = p["posisi"]
    arah = 1 if pos["side"] == "BUY" else -1
    gerak = (harga - pos["entry"]) * arah
    oz = pos["lot"] * 100.0
    pnl = gerak * oz
    p["ekuitas"] += pnl
    p["pnl_hari"] += pnl
    p["riwayat"].append({"waktu": waktu, "side": pos["side"], "entry": pos["entry"],
                         "exit": harga, "lot": pos["lot"], "pnl": round(pnl, 2),
                         "R": round(pnl / pos["risk_usd"], 3) if pos["risk_usd"] else 0})
    p["riwayat"] = p["riwayat"][-200:]
    LOG.parent.mkdir(parents=True, exist_ok=True)
    baru = not LOG.exists()
    with LOG.open("a", newline="") as f:
        w = csv.writer(f)
        if baru:
            w.writerow(["waktu", "panel", "side", "entry", "exit", "lot", "pnl", "R", "ekuitas"])
        w.writerow([waktu, p["nama"], pos["side"], pos["entry"], harga, pos["lot"],
                    round(pnl, 2), round(pnl / pos["risk_usd"], 3) if pos["risk_usd"] else 0,
                    round(p["ekuitas"], 2)])
    p["posisi"] = None


def main() -> None:
    state = muat()
    for nama, risk, target, stop, maks in SKEMA:
        state.setdefault(nama, panel_baru(nama, risk, target, stop, maks))

    tel = ambil("/api/v1/tencent/mt5/status", 8.0)
    if not tel or not tel.get("connected"):
        print("telemetri tidak tersedia; lewati")
        simpan(state)
        return
    bid, ask = float(tel["bid"]), float(tel["ask"])
    hari = date.today().isoformat()
    waktu = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    sinyal = ambil("/api/v1/tencent/forex/levels?symbol=XAUUSD&mode=scalping", 25.0) or {}
    siap = sinyal.get("status") == "OK" and sinyal.get("side")

    for p in state.values():
        if p["hari"] != hari:
            reset_harian(p, hari)
        # 1. kelola posisi terbuka
        if p["posisi"]:
            pos = p["posisi"]
            kena = (bid <= pos["sl"] if pos["side"] == "BUY" else ask >= pos["sl"]) or \
                   (bid >= pos["tp"] if pos["side"] == "BUY" else ask <= pos["tp"])
            if kena:
                kena_sl = bid <= pos["sl"] if pos["side"] == "BUY" else ask >= pos["sl"]
                harga = pos["sl"] if kena_sl else pos["tp"]
                tutup(p, harga, waktu)
        # 2. ratchet harian
        perbarui_ratchet(p)
        # 3. buka posisi baru
        if siap and not p["posisi"] and not p["berhenti"] and p["trades_hari"] < p["max_trades"]:
            risk = sinyal.get("risk")
            reward = sinyal.get("reward")
            if risk and reward and risk > 0:
                entry = ask if sinyal["side"] == "BUY" else bid
                risiko_usd = p["ekuitas"] * p["risk_pct"] / 100.0
                lot = max(0.01, round(risiko_usd / (risk * 100.0), 2))
                risiko_usd = lot * 100.0 * risk
                arah = 1 if sinyal["side"] == "BUY" else -1
                p["posisi"] = {
                    "side": sinyal["side"], "entry": entry, "lot": lot,
                    "sl": entry - arah * risk, "tp": entry + arah * reward,
                    "risk_usd": risiko_usd, "dibuka": waktu,
                }
                p["trades_hari"] += 1
        # 4. tandai kalau sudah berhenti tapi masih ada posisi
        if p["berhenti"] and p["posisi"]:
            p["posisi"] = None

    simpan(state)
    for p in state.values():
        print(f"panel {p['nama']}: ekuitas ${p['ekuitas']:.2f} | hari {persen(p):+.2f}% | "
              f"trade {p['trades_hari']}/{p['max_trades']} | "
              f"{'STOP: ' + p['alasan_berhenti'] if p['berhenti'] else 'aktif'}")


if __name__ == "__main__":
    main()
