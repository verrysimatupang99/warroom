"""Ubah CSV ekspor MT5 menjadi CSV bersih siap lab."""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

KOLOM_MASUK = ("time_utc_epoch", "open", "high", "low", "close",
               "tick_volume", "real_volume", "spread")


def baca_baris(sumber: Path) -> list[list[str]]:
    with sumber.open(newline="") as f:
        pembaca = csv.reader(f)
        judul = next(pembaca, None)
        if judul is None or judul[0] != KOLOM_MASUK[0]:
            raise ValueError(f"header tidak dikenal pada {sumber}: {judul}")
        return [b for b in pembaca if len(b) >= len(KOLOM_MASUK)]


def bersihkan(sumber: Path, keluar: Path) -> dict[str, object]:
    mentah = baca_baris(sumber)
    cacah: Counter[str] = Counter()
    per_hari: Counter[str] = Counter()
    terlihat: dict[int, list[str]] = {}

    for b in mentah:
        cacah["masuk"] += 1
        try:
            detik = int(float(b[0]))
            o, h, l, c = (float(x) for x in b[1:5])
            vol = float(b[5])
            spread = int(float(b[7]))
        except (ValueError, IndexError):
            cacah["baris_rusak"] += 1
            continue
        if min(o, h, l, c) <= 0:
            cacah["harga_nol"] += 1
            continue
        if h < l or not (l <= min(o, c) and max(o, c) <= h):
            cacah["ohlc_tidak_konsisten"] += 1
            continue
        if spread < 0:
            cacah["spread_negatif"] += 1
            continue
        terlihat[detik] = [str(detik * 1000), f"{o}", f"{h}", f"{l}", f"{c}", f"{int(vol)}"]

    cacah["duplikat"] = cacah["masuk"] - cacah["baris_rusak"] - len(terlihat)

    keluar.parent.mkdir(parents=True, exist_ok=True)
    dengan = sorted(terlihat)
    with keluar.open("w", newline="") as f:
        tulis = csv.writer(f)
        tulis.writerow(["timestamp_ms", "open", "high", "low", "close", "volume"])
        for detik in dengan:
            tulis.writerow(terlihat[detik])
            per_hari[datetime.fromtimestamp(detik, UTC).strftime("%Y-%m-%d")] += 1

    hari = sorted(per_hari)
    return {
        "sumber": str(sumber),
        "keluar": str(keluar),
        "baris_masuk": cacah["masuk"],
        "baris_keluar": len(dengan),
        "dibuang": {k: v for k, v in cacah.items() if k != "masuk" and v},
        "hari_perdagangan": len(hari),
        "rentang": (hari[0], hari[-1]) if hari else None,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("sumber", type=Path)
    p.add_argument("keluar", type=Path)
    a = p.parse_args()
    hasil = bersihkan(a.sumber, a.keluar)
    for k, v in hasil.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
