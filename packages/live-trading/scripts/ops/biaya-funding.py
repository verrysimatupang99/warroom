"""Biaya funding: satu-satunya biaya nyata yang belum masuk backtest.

Perp dibayar tiap 8 jam. Kalau arah kandidat kita berkorelasi dengan tanda funding
(contoh: long saat pasar naik biasanya berarti membayar), maka biaya ini bukan acak —
ia sistematis mengurangi edge, dan harus diukur, bukan diasumsikan nol.

Cara: ambil riwayat funding tiap pair SEKALI (1000 per permintaan), lalu jumlahkan funding
yang jatuh di dalam jendela tahan tiap kandidat, ditandai menurut arah posisi.

Pemakaian:
  python3 scripts/ops/biaya-funding.py [hari] [penetrasi_bps]
"""

import datetime as dt
import json
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

import httpx

FAPI = "https://fapi.binance.com"
MS_JAM = 3_600_000
MS_8J = 8 * MS_JAM


def baca_rows(hari: int, penetrasi: float):
    nama = f"backtest-{hari}d-h33-o0-p{penetrasi:g}.jsonl" if penetrasi else f"backtest-{hari}d.jsonl"
    p = Path("state") / nama
    if not p.is_file():
        raise SystemExit(f"  berkas tidak ada: {p}")
    return [json.loads(ln) for ln in p.read_text().splitlines() if ln.strip()]


def ambil_funding(c: httpx.Client, pair: str, mulai_ms: int, akhir_ms: int) -> dict[int, float]:
    out: dict[int, float] = {}
    kursor = mulai_ms
    while kursor < akhir_ms:
        r = c.get(
            f"{FAPI}/fapi/v1/fundingRate",
            params={"symbol": pair, "startTime": kursor, "endTime": akhir_ms, "limit": 1000},
        )
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        for b in batch:
            out[int(b["fundingTime"])] = float(b["fundingRate"])
        kursor = int(batch[-1]["fundingTime"]) + 1
    return out


def main() -> int:
    hari = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    penetrasi = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0
    rows = baca_rows(hari, penetrasi)
    terisi = [r for r in rows if r.get("jam_ke_isi") and r.get("entry") and r.get("sl")]
    if not terisi:
        raise SystemExit("  tidak ada baris terisi")

    per_pair: dict[str, list[dict]] = defaultdict(list)
    for r in terisi:
        per_pair[r["pair"]].append(r)

    total_biaya_r = 0.0
    jumlah = 0
    per_arah: dict[str, list[float]] = defaultdict(list)
    contoh = 0

    with httpx.Client(timeout=30.0, headers={"User-Agent": "curl/8"}) as c:
        for i, (pair, rs) in enumerate(sorted(per_pair.items()), 1):
            awal = min(int(dt.datetime.fromisoformat(r["ts"]).timestamp() * 1000) for r in rs)
            akhir = awal + (hari + 5) * 24 * MS_JAM
            try:
                funding = ambil_funding(c, pair, awal, akhir)
            except Exception as exc:  # noqa: BLE001
                print(f"  [{i}/{len(per_pair)}] {pair}: gagal ambil funding ({type(exc).__name__})")
                continue
            for r in rs:
                ts = int(dt.datetime.fromisoformat(r["ts"]).timestamp() * 1000)
                # jendela tahan nyata: dari terisi sampai hasil (atau 24 jam)
                jam = int(r.get("jam_ke_isi") or 0) + int(r.get("jam_ke_hasil") or 0)
                jam = min(max(jam, 1), 33)
                selesai = ts + jam * MS_JAM
                rate = sum(v for t, v in funding.items() if ts <= t <= selesai)
                risk = abs(float(r["entry"]) - float(r["sl"]))
                if risk <= 0:
                    continue
                # posisi long MEMBAYAR saat rate positif: biaya = +rate
                arah = 1.0 if str(r["direction"]).lower() == "long" else -1.0
                biaya_r = rate * arah * float(r["entry"]) / risk
                total_biaya_r += biaya_r
                jumlah += 1
                per_arah[str(r["direction"]).upper()].append(biaya_r)
                if contoh < 2:
                    contoh += 1
            print(f"  [{i}/{len(per_pair)}] {pair:<14} {len(rs):>4} kandidat · {len(funding)} titik funding")

    if not jumlah:
        print("  tidak ada yang bisa dihitung")
        return 1
    rata = total_biaya_r / jumlah
    print(f"\n  kandidat dihitung: {jumlah}")
    print(f"  biaya funding rata-rata: {rata:+.4f}R per kandidat (positif = kita MEMBAYAR)")
    for arah, v in sorted(per_arah.items()):
        print(f"    {arah:<6} n={len(v):<5} rata-rata {st.fmean(v):+.4f}R")
    print("\n  Bandingkan dengan edge kotor ~+0,04 s/d +0,05R dan fee maker MEXC ~0-1 bps.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
