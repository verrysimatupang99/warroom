#!/usr/bin/env python3
"""Perdalam data historis crypto (klines Binance) untuk backtest.

Mengunduh candle OHLCV dari API publik Binance dan menulis ke
data/hist/{SYMBOL}_{interval}.csv dengan format kolom yang sama seperti
file yang sudah ada (12 kolom klines Binance).

Kenapa: backtest butuh cukup sejarah agar statistik (winrate, PF, drawdown)
bermakna. File lama BTC/SOL hanya ~10 hari (1000 candle) — terlalu tipis.

Paginasi: Binance membatasi 1000 candle per permintaan, jadi kita maju
bertahap memakai startTime = close_time candle terakhir + 1 ms.

Pemakaian:
    python ops/perdalam-data-crypto.py                # default: 2 tahun, 15m+1h
    python ops/perdalam-data-crypto.py --tahun 1      # 1 tahun
    python ops/perdalam-data-crypto.py --simbol BTCUSDT --interval 1h
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

API = "https://api.binance.com/api/v3/klines"
HIST_DIR = Path("/home/admin/warroom/data/hist")
KOLOM = [
    "timestamp", "open", "high", "low", "close", "volume", "close_time",
    "quote_asset_volume", "number_of_trades", "taker_buy_base_asset_volume",
    "taker_buy_quote_asset_volume", "ignore",
]
BATCH = 1000  # batas Binance per permintaan


def _ambil_batch(simbol: str, interval: str, start_ms: int, end_ms: int) -> list[list]:
    url = (f"{API}?symbol={simbol}&interval={interval}&limit={BATCH}"
           f"&startTime={start_ms}&endTime={end_ms}")
    req = urllib.request.Request(url, headers={"User-Agent": "warroom-backfill/1.0"})
    for percobaan in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8").strip()
        except (urllib.error.URLError, TimeoutError):
            if percobaan == 2:
                raise
            time.sleep(2 * (percobaan + 1))
    return "[]"


def _parse(data: str) -> list[list]:
    import json
    return json.loads(data) if data else []


def perdalam(simbol: str, interval: str, tahun: int) -> tuple[str, int, str, str]:
    """Unduh candle dari (sekarang - tahun) sampai sekarang. Return (file, baris, awal, akhir)."""
    sekarang_ms = int(datetime.now(UTC).timestamp() * 1000)
    mulai_ms = int((datetime.now(UTC) - timedelta(days=365 * tahun)).timestamp() * 1000)

    HIST_DIR.mkdir(parents=True, exist_ok=True)
    out = HIST_DIR / f"{simbol}_{interval}.csv"

    semua: dict[int, list] = {}  # dedupe by open timestamp
    kursor = mulai_ms
    while kursor < sekarang_ms:
        data = _parse(_ambil_batch(simbol, interval, kursor, sekarang_ms))
        if not data:
            break
        for row in data:
            semua[int(row[0])] = row
        # maju ke setelah candle terakhir
        terakhir_close = int(data[-1][6])
        kursor = terakhir_close + 1
        if len(data) < BATCH:
            break  # sudah sampai ujung
        time.sleep(0.15)  # sopan ke API

    if not semua:
        return (str(out), 0, "-", "-")

    urut = [semua[k] for k in sorted(semua)]
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(KOLOM)
        for row in urut:
            w.writerow(row)

    awal = datetime.fromtimestamp(urut[0][0] / 1000, tz=UTC).strftime("%Y-%m-%d")
    akhir = datetime.fromtimestamp(urut[-1][0] / 1000, tz=UTC).strftime("%Y-%m-%d")
    return (str(out), len(urut), awal, akhir)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--simbol", default="BTCUSDT,ETHUSDT,SOLUSDT")
    ap.add_argument("--interval", default="15m,1h")
    ap.add_argument("--tahun", type=int, default=2)
    args = ap.parse_args()

    simbol = [s.strip() for s in args.simbol.split(",") if s.strip()]
    interval = [i.strip() for i in args.interval.split(",") if i.strip()]

    print(f"Perdalam data: {simbol} interval {interval} sejauh {args.tahun} tahun")
    for s in simbol:
        for i in interval:
            try:
                out, n, awal, akhir = perdalam(s, i, args.tahun)
                print(f"  {s} {i}: {n} candle [{awal} .. {akhir}] -> {out}")
            except Exception as e:  # noqa: BLE001
                print(f"  {s} {i}: GAGAL {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
