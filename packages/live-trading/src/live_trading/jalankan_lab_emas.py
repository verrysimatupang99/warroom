"""Jalankan ketiga hipotesis di data PAXG 15m, bandingkan, cetak tabel.

Pemakaian::

    PYTHONPATH=packages/core/src:packages/live-trading/src \\
        .venv/bin/python -m live_trading.jalankan_lab_emas
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from live_trading.hipotesis_emas import (
    sinyal_momentum_sesi,
    sinyal_opening_range,
    sinyal_trend_sesi,
)
from live_trading.lab_emas import Gerbang, blok_kronologis, jalankan_sinyal, mc_bootstrap, metrik

DATA = Path("data/hist/PAXGUSDT_15m.csv")
KELUAR = Path("docs/riset-reaper-lab-20261102.json")


def muat(path: Path) -> dict[str, list[Any]]:
    data: dict[str, list[Any]] = {"waktu": [], "open": [], "high": [], "low": [], "close": []}
    with path.open() as f:
        for r in csv.reader(f):
            if not r[0].strip().isdigit():
                continue
            data["waktu"].append(int(r[0]))
            data["open"].append(float(r[1]))
            data["high"].append(float(r[2]))
            data["low"].append(float(r[3]))
            data["close"].append(float(r[4]))
    return data


def ringkas(nama: str, trades: list[dict[str, Any]], g: Gerbang) -> dict[str, Any]:
    m = metrik(trades)
    lolos, gagal = g.periksa(m)
    m["lolos"] = lolos
    m["alasan_gagal"] = gagal
    m["blok"] = blok_kronologis(trades) if trades else []
    m["mc"] = mc_bootstrap([t["r_bersih"] for t in trades]) if trades else {}
    m["nama"] = nama
    return m


def cetak(nama: str, m: dict[str, Any]) -> None:
    print(f"\n{'=' * 70}\n{nama}\n{'=' * 70}")
    if not m.get("n"):
        print("  tidak ada trade")
        return
    print(
        f"  n={m['n']:4d}  win={m['win_rate'] * 100:5.1f}%  "
        f"exp={m['expectancy_r']:+.3f}R  PF={m['profit_factor']}  "
        f"t={m['t_stat']}  DD={m['max_dd_pct']}%"
    )
    print(f"  R kotor={m['r_kotor_total']:+.1f}  R bersih={m['r_bersih_total']:+.1f}")
    if m.get("mc"):
        mc = m["mc"]
        print(
            f"  bootstrap: P(exp>0)={mc['p_expectancy_positif'] * 100:.1f}%  "
            f"[{mc['p05']:+.3f}, {mc['p95']:+.3f}]"
        )
    print("  blok:", " ".join(f"{b['blok']}:{b['expectancy_r']:+.2f}({b['n']})" for b in m["blok"]))
    print("  ", "LOLOS" if m["lolos"] else "GAGAL -> " + "; ".join(m["alasan_gagal"]))


def main() -> None:
    print(f"memuat {DATA} ...")
    data = muat(DATA)
    n = len(data["close"])
    print(f"{n} bar, {data['waktu'][0]} s/d {data['waktu'][-1]}")
    g = Gerbang()

    uji = {
        "A_momentum_sesi": sinyal_momentum_sesi(data),
        "B_opening_range": sinyal_opening_range(data),
        "C_trend_sesi": sinyal_trend_sesi(data),
    }

    hasil = {}
    for nama, fn in uji.items():
        trades = jalankan_sinyal(data, fn, mulai=300, selesai=n)
        m = ringkas(nama, trades, g)
        cetak(nama, m)
        hasil[nama] = m

    KELUAR.write_text(json.dumps(hasil, indent=2, ensure_ascii=False))
    print(f"\nhasil mentah -> {KELUAR}")
    lulus = [k for k, v in hasil.items() if v.get("lolos")]
    print(f"\n{'LOLOS GATE: ' + ', '.join(lulus) if lulus else 'TIDAK ADA YANG LOLOS GATE'}")


if __name__ == "__main__":
    main()
