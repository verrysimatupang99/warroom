"""Deteksi jam buka pasar dari pergerakan tick broker.

Latar: jam buka/tutup XAUUSD berbeda per broker dan bergeser saat DST. Daripada
mengandalkan asumsi ("Senin 01:00 UTC"), skrip ini mencatat kapan harga BENAR-BENAR
mulai bergerak lagi setelah beku.

Cara kerja:
- setiap kali dijalankan, baca `bid` dari telemetri EA
- bandingkan dengan `bid` terakhir yang tersimpan
- bila berubah dan status sebelumnya "TUTUP", catat peristiwa BUKA (UTC + WIB)
- simpan status ke JSON dan riwayat ke CSV

Dijalankan oleh systemd timer (tiap 5 menit). Hanya membaca, tidak mengubah trading.
"""

from __future__ import annotations

import csv
import json
import os
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

API = os.environ.get("WARROOM_API", "http://127.0.0.1:8800")
STATE = Path(os.environ.get("WARROOM_TICK_STATE", "/var/lib/warroom/tick_state.json"))
LOG = Path(os.environ.get("WARROOM_TICK_LOG", "/var/lib/warroom/pasar_log.csv"))
WIB = timedelta(hours=7)


def baca_state() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def tulis_state(d: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(d), encoding="utf-8")
    os.replace(tmp, STATE)


def catat(baris: list[str]) -> None:
    baru = not LOG.exists()
    with LOG.open("a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if baru:
            w.writerow(["waktu_utc", "waktu_wib", "peristiwa", "bid", "spread_pts", "catatan"])
        w.writerow(baris)


def main() -> int:
    try:
        with httpx.Client(timeout=10.0) as c:
            r = c.get(f"{API}/api/v1/tencent/mt5/status")
        r.raise_for_status()
        st = r.json()
    except Exception as exc:  # noqa: BLE001
        print(f"gagal baca status: {type(exc).__name__}: {exc}")
        return 1

    bid = st.get("bid")
    spread = st.get("spread_pts")
    if bid is None:
        print("bid tidak tersedia (EA mungkin offline)")
        return 1

    now = datetime.now(UTC)
    wib = (now + WIB).strftime("%Y-%m-%d %H:%M")
    lama = baca_state()
    bid_lama = lama.get("bid")
    status_lama = lama.get("status", "TIDAK_DIKETAHUI")

    berubah = bid_lama is not None and float(bid) != float(bid_lama)

    # Status awal tidak diketahui: tetapkan dari pergerakan, bukan dibiarkan
    # menggantung. Tanpa ini, peristiwa BUKA pertama tidak akan pernah tercatat
    # karena syaratnya `status_lama == "TUTUP"` tidak pernah terpenuhi.
    if status_lama == "TIDAK_DIKETAHUI":
        status_baru = "BUKA" if berubah else "TUTUP"
    else:
        status_baru = "BUKA" if berubah else status_lama

    if berubah and status_lama in ("TUTUP", "TIDAK_DIKETAHUI"):
        print(f"PASAR BUKA terdeteksi: bid {bid_lama} -> {bid} pada {now:%Y-%m-%d %H:%M} UTC")
        catat([now.strftime("%Y-%m-%d %H:%M:%S"), wib, "PASAR_BUKA", str(bid), str(spread),
               f"bid sebelumnya {bid_lama}"])
    elif berubah:
        print(f"tick bergerak: {bid_lama} -> {bid}")

    tulis_state({
        "bid": float(bid),
        "spread_pts": spread,
        "status": status_baru,
        "diperbarui": int(time.time()),
        "diperbarui_utc": now.strftime("%Y-%m-%d %H:%M:%S"),
    })
    print(f"status={status_baru} bid={bid} spread={spread} (sebelumnya {bid_lama})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
