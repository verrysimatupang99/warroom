"""Laporan perbandingan 3 panel simulator (A/B/C) — satu perintah.

Menjawab pertanyaan: skema sizing + daily ratchet mana yang bertahan?

Pemakaian:
    .venv/bin/python ops/laporan-panel.py
    .venv/bin/python ops/laporan-panel.py --csv          # ekspor ringkasan
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path

STATE = Path("/var/lib/warroom/panels.json")
LOG = Path("/var/lib/warroom/panels_trades.csv")


def muat_state() -> dict:
    if not STATE.exists():
        return {}
    try:
        return json.loads(STATE.read_text())
    except Exception:
        return {}


def muat_trades() -> dict[str, list[dict]]:
    kel: dict[str, list[dict]] = defaultdict(list)
    if not LOG.exists():
        return kel
    with LOG.open() as f:
        for r in csv.DictReader(f):
            try:
                kel[r["panel"]].append({"pnl": float(r["pnl"]), "R": float(r["R"]),
                                        "ekuitas": float(r["ekuitas"])})
            except Exception:
                continue
    return kel


def statistik(tr: list[dict]) -> dict:
    if not tr:
        return {"n": 0}
    pnl = [t["pnl"] for t in tr]
    rr = [t["R"] for t in tr]
    menang = [x for x in pnl if x > 0]
    kalah = [x for x in pnl if x < 0]
    puncak, dd = 0.0, 0.0
    for t in tr:
        puncak = max(puncak, t["ekuitas"])
        if puncak > 0:
            dd = max(dd, 1 - t["ekuitas"] / puncak)
    pf = (sum(menang) / abs(sum(kalah))) if kalah else float("inf")
    return {"n": len(tr), "win": 100 * len(menang) / len(tr),
            "total": sum(pnl), "avgR": statistics.mean(rr),
            "pf": pf, "dd": 100 * dd}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", action="store_true", help="ekspor ringkasan ke stdout sebagai CSV")
    args = ap.parse_args()

    state = muat_state()
    trades = muat_trades()
    if not state:
        print("Belum ada state. Jalankan: systemctl start warroom-panel-sim.service")
        return

    baris = []
    for nama in sorted(state):
        p = state[nama]
        s = statistik(trades.get(nama, []))
        basis = p["ekuitas"] - p.get("pnl_hari", 0.0)
        hari_pct = 100 * p.get("pnl_hari", 0.0) / basis if basis else 0.0
        baris.append({
            "panel": nama,
            "risk": p["risk_pct"], "target": p["target_pct"], "stop": p["stop_pct"],
            "ekuitas": p["ekuitas"],
            "total_pct": 100 * (p["ekuitas"] / p["modal_awal"] - 1),
            "hari_pct": hari_pct,
            "trades_hari": f"{p['trades_hari']}/{p['max_trades']}",
            "status": ("STOP: " + p["alasan_berhenti"]) if p["berhenti"] else "aktif",
            "posisi": "terbuka" if p.get("posisi") else "-",
            **s,
        })

    if args.csv:
        w = csv.DictWriter(__import__("sys").stdout, fieldnames=list(baris[0]))
        w.writeheader()
        w.writerows(baris)
        return

    print("=" * 78)
    print("PERBANDINGAN 3 PANEL — simulator sizing + daily ratchet")
    print("=" * 78)
    print(f"{'panel':6}{'risk':>6}{'target':>8}{'stop':>6}{'ekuitas':>10}{'total':>8}{'hari':>8}{'trade':>8}")
    for b in baris:
        print(f"{b['panel']:6}{b['risk']:>5.1f}%{b['target']:>7.0f}%{b['stop']:>5.0f}%"
              f"{b['ekuitas']:>10.2f}{b['total_pct']:>7.2f}%{b['hari_pct']:>7.2f}%{b['trades_hari']:>8}")

    print("\n--- status harian ---")
    for b in baris:
        print(f"  {b['panel']}: {b['status']} | posisi {b['posisi']}")

    print("\n--- kinerja terkumpul ---")
    print(f"{'panel':6}{'n':>5}{'win%':>7}{'total$':>10}{'avgR':>8}{'PF':>7}{'maxDD':>8}")
    for b in baris:
        if b.get("n"):
            print(f"{b['panel']:6}{b['n']:>5}{b['win']:>6.1f}%{b['total']:>10.2f}"
                  f"{b['avgR']:>8.3f}{b['pf']:>7.2f}{b['dd']:>7.1f}%")
        else:
            print(f"{b['panel']:6}{0:>5}{'-':>7}{0:>10.2f}{'-':>8}{'-':>7}{'-':>8}")

    total_n = sum(b.get("n", 0) for b in baris)
    print()
    if total_n < 30:
        print(f"! Sampel baru {total_n} trade per panel. Butuh >=30 untuk menyimpulkan.")
        print("  (uji kekuatan statistik: ~28 trade untuk mendeteksi edge 0,37R)")
    else:
        terbaik = max((b for b in baris if b.get("n")), key=lambda x: x["avgR"])
        print(f"Panel terdepan menurut avgR: {terbaik['panel']} ({terbaik['avgR']:+.3f}R)")

    print("\nCatatan: simulasi memakai harga broker dari telemetri, tanpa biaya komisi/swap.")
    print("Angka akan sedikit lebih optimis daripada eksekusi nyata.")


if __name__ == "__main__":
    main()
