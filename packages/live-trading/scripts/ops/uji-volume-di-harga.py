"""Volume TEPAT di harga kita — dari aggTrades, bukan dari candle.

Candle 1 menit memberi volume seluruh menit, bukan volume yang benar-benar terjadi di harga
entry kita. Untuk menjawab "apakah order limit kita terisi?", yang perlu dijumlahkan hanya
transaksi dengan harga <= entry (untuk long) pada menit ketika harga menyentuh level.

Kalau jumlah itu ratusan ribu dolar, order ritel akan terisi. Kalau hanya ribuan dolar,
"sentuh" itu cetakan harga tanpa kedalaman — dan edge dari sana tidak bisa diuangkan.

Pemakaian: python3 scripts/ops/uji-volume-di-harga.py [jumlah_sampel] [ambang_bps]
"""
import datetime as dt
import json
import random
import statistics as st
import sys
from pathlib import Path

import httpx

FAPI = "https://fapi.binance.com"
MS_MENIT = 60_000
FILL_WINDOW_H = 8


def muat(hari: int) -> list[dict]:
    p = Path("state") / f"backtest-{hari}d.jsonl"
    if not p.is_file():
        raise SystemExit(f"  tidak ada {p}")
    return [json.loads(ln) for ln in p.read_text().splitlines() if ln.strip()]


def main() -> int:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    ambang = float(sys.argv[2]) if len(sys.argv) > 2 else 30.0
    rows = [r for r in muat(300) if r.get("jam_ke_isi") and r.get("r") is not None]
    random.seed(7)
    sampel = random.sample(rows, min(n, len(rows)))

    terpilih = []
    with httpx.Client(timeout=30.0, headers={"User-Agent": "curl/8"}) as c:
        # Tahap 1: cari kandidat dengan sentuhan tipis (butuh candle 1 menit)
        for row in sampel:
            ts = int(dt.datetime.fromisoformat(row["ts"]).timestamp() * 1000)
            try:
                kl = c.get(
                    f"{FAPI}/fapi/v1/klines",
                    params={"symbol": row["pair"], "interval": "1m", "startTime": ts,
                            "limit": FILL_WINDOW_H * 60 + 5},
                ).json()
            except Exception:  # noqa: BLE001
                continue
            if not kl:
                continue
            entry = float(row["entry"])
            long = str(row["direction"]).lower() == "long"
            lows = [float(k[3]) for k in kl]
            highs = [float(k[2]) for k in kl]
            if long:
                if min(lows) > entry:
                    continue
                tembus = (entry - min(lows)) / entry * 10000
            else:
                if max(highs) < entry:
                    continue
                tembus = (max(highs) - entry) / entry * 10000
            if tembus <= ambang:
                terpilih.append((row, ts, tembus))
            if len(terpilih) >= 60:
                break

        print(f"  kandidat dengan sentuhan <= {ambang:g} bps: {len(terpilih)}")
        if not terpilih:
            return 1

        # Tahap 2: aggTrades pada menit pertama harga menyentuh level kita
        baris = []
        for i, (row, ts, tembus) in enumerate(terpilih, 1):
            entry = float(row["entry"])
            long = str(row["direction"]).lower() == "long"
            try:
                kl = c.get(
                    f"{FAPI}/fapi/v1/klines",
                    params={"symbol": row["pair"], "interval": "1m", "startTime": ts,
                            "limit": FILL_WINDOW_H * 60 + 5},
                ).json()
                idx = None
                for j, k in enumerate(kl):
                    if long and float(k[3]) <= entry:
                        idx = j
                        break
                    if not long and float(k[2]) >= entry:
                        idx = j
                        break
                if idx is None:
                    continue
                mulai = int(kl[idx][0])
                trades = c.get(
                    f"{FAPI}/fapi/v1/aggTrades",
                    params={"symbol": row["pair"], "startTime": mulai,
                            "endTime": mulai + MS_MENIT - 1, "limit": 1000},
                ).json()
                if not isinstance(trades, list):
                    print(f"  [{i}/{len(terpilih)}] {row['pair']}: aggTrades bukan daftar "
                          f"({str(trades)[:70]})")
                    continue
            except Exception as exc:  # noqa: BLE001
                print(f"  [{i}/{len(terpilih)}] {row['pair']}: gagal ({type(exc).__name__})")
                continue
            # hanya transaksi yang harganya menyentuh harga kita
            if long:
                usd = sum(float(t["p"]) * float(t["q"]) for t in trades if float(t["p"]) <= entry)
                jml = sum(1 for t in trades if float(t["p"]) <= entry)
            else:
                usd = sum(float(t["p"]) * float(t["q"]) for t in trades if float(t["p"]) >= entry)
                jml = sum(1 for t in trades if float(t["p"]) >= entry)
            baris.append({"pair": row["pair"], "tembus_bps": tembus, "usd": usd,
                          "transaksi": jml, "r": row["r"]})
            print(f"  [{i}/{len(terpilih)}] {row['pair']:<14} tembus {tembus:5.1f} bps "
                  f"· di harga kita: ${usd:>12,.0f} dari {jml} transaksi")

    if not baris:
        print("  tidak ada data")
        return 1
    usd = sorted(b["usd"] for b in baris)
    print(f"\n  kandidat terukur: {len(baris)}")
    print(f"  volume TEPAT di harga kita: median ${st.median(usd):,.0f} · "
          f"10% terkecil ${usd[len(usd) // 10]:,.0f} · terkecil ${usd[0]:,.0f}")
    kosong = sum(1 for b in baris if b["usd"] == 0)
    if kosong:
        print(f"  sentuhan tanpa satu pun transaksi di harga kita: {kosong} kandidat")
    print("\n  Acuan: order ritel $1.000-$50.000. Selama angkanya ratusan ribu dolar, terisi.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
