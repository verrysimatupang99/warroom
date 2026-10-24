"""Analisa kualitas eksekusi XAUUSD dari log fill + telemetri.

Menjawab: jam mana paling mahal dieksekusi, berapa spread yang mulai merusak
fill, dan apakah kepadatan posisi memperburuk slippage — memakai data broker
sendiri, bukan asumsi.

Pemakaian:
    .venv/bin/python ops/laporan-eksekusi.py
"""

from __future__ import annotations

import csv
import statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path

FILL = Path("/var/lib/warroom/fills.csv")
TELE = Path("/var/lib/warroom/telemetry_log.csv")


def baca(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open() as f:
        return list(csv.DictReader(f))


def f(x) -> float | None:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def jam_dari(iso: str) -> int | None:
    try:
        return datetime.strptime(iso, "%Y-%m-%d %H:%M:%S").hour
    except Exception:
        return None


def ringkas(judul: str, grup: dict, kunci: str) -> None:
    print(f"\n=== {judul} ===")
    print(f"{'nilai':>10}{'n':>5}{'median':>9}{'p90':>9}{'maks':>9}")
    for k in sorted(grup):
        v = sorted(grup[k])
        p90 = v[min(len(v) - 1, int(0.9 * len(v)))]
        print(f"{str(k):>10}{len(v):>5}{statistics.median(v):>9.1f}{p90:>9.1f}{v[-1]:>9.1f}")


def main() -> None:
    fills = baca(FILL)
    tele = baca(TELE)

    print("=" * 62)
    print("KUALITAS EKSEKUSI XAUUSD")
    print("=" * 62)
    print(f"log fill     : {len(fills)} trade")
    print(f"log telemetri: {len(tele)} sampel")

    if tele:
        sp = [v for t in tele if (v := f(t["spread_pts"])) is not None]
        if sp:
            print(f"\nspread (point): median {statistics.median(sp):.0f} | "
                  f"min {min(sp):.0f} | maks {max(sp):.0f}")

    if not fills:
        print("\nBelum ada fill tercatat. Menunggu trade pertama (pasar buka Senin).")
        print("Format yang akan dianalisa: slippage_pts per jam / spread / kepadatan.")
        return

    slip = [(x, f(x["slippage_pts"]), f(x["spread_pts"]), f(x["latency_ms"]),
             f(x["open_positions"]), jam_dari(x["iso"]), x.get("execution_mode"))
            for x in fills]
    slip = [s for s in slip if s[1] is not None]

    semua = [s[1] for s in slip]
    print(f"\nslippage (point): median {statistics.median(semua):.1f} | "
          f"rata-rata {statistics.mean(semua):.2f} | maks {max(semua):.1f}")
    lat = [s[3] for s in slip if s[3] is not None]
    if lat:
        print(f"latensi (ms)   : median {statistics.median(lat):.0f} | maks {max(lat):.0f}")
    mode = {s[6] for s in slip if s[6]}
    if mode:
        print(f"execution_mode : {sorted(mode)} (2 = Market Execution)")

    per_jam: dict[int, list] = defaultdict(list)
    per_spread: dict[str, list] = defaultdict(list)
    per_pos: dict[int, list] = defaultdict(list)
    for _, s, sp, _, pos, jam, _ in slip:
        if jam is not None:
            per_jam[jam].append(s)
        if sp is not None:
            bucket = "0-200" if sp < 200 else "200-300" if sp < 300 else "300-400" if sp < 400 else "400+"
            per_spread[bucket].append(s)
        if pos is not None:
            per_pos[int(pos)].append(s)

    ringkas("SLIPPAGE PER JAM (point, server time)", per_jam, "jam")
    ringkas("SLIPPAGE PER SPREAD SAAT ENTRY", per_spread, "spread")
    ringkas("SLIPPAGE PER JUMLAH POSISI TERBUKA", per_pos, "posisi")

    print("\nCatatan: positif = fill lebih buruk dari harga yang diminta.")
    print("Butuh >=30 fill sebelum angka ini layak dipakai mengambil keputusan.")


if __name__ == "__main__":
    main()
