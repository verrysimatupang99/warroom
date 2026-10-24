"""Laporan kesiapan forex War Room — satu perintah, tanpa mengubah apa pun.

Menjawab pertanyaan yang berulang setelah kejadian 21-24 Okt:
  1. EA hidup? sudah berapa lama?
  2. Indikator diambil dari BROKER atau Yahoo (futures)?
  3. Gerbang Laya memblokir atau meloloskan, dan kenapa?
  4. Sebaran confidence Laya seperti apa -> dasar memilih ambang.

Pemakaian:
    .venv/bin/python ops/laporan-forex.py
    .venv/bin/python ops/laporan-forex.py --token <token>
"""

from __future__ import annotations

import argparse
import csv
import os
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

import httpx

API = os.environ.get("WARROOM_API", "http://127.0.0.1:8800")
CSV_LOG = Path(os.environ.get("WARROOM_LAYA_VERDICT_LOG", "/var/lib/warroom/laya_verdict_log.csv"))
AMBANG_KINI = 0.60


def ambil(path: str, token: str | None) -> dict[str, Any] | None:
    headers = {"X-Warroom-Token": token} if token else {}
    try:
        with httpx.Client(timeout=25.0) as c:
            r = c.get(f"{API}{path}", headers=headers)
        if r.status_code != 200:
            print(f"  ! {path} -> HTTP {r.status_code}")
            return None
        return r.json()
    except Exception as exc:  # noqa: BLE001
        print(f"  ! {path} -> {type(exc).__name__}: {exc}")
        return None


def bagian_ea() -> dict[str, Any] | None:
    st = ambil("/api/v1/tencent/mt5/status", None)
    print("== EA / MT5 ==")
    if not st:
        print("  TIDAK BISA DIBACA")
        return None
    hb = st.get("seconds_ago")
    print(f"  terhubung : {st.get('connected')} (heartbeat {hb} detik)")
    print(f"  akun      : {st.get('account')} / {st.get('broker')}")
    print(f"  ekuitas   : {st.get('equity')} | posisi terbuka: {len(st.get('positions') or [])}")
    print(f"  bid/ask   : {st.get('bid')} / {st.get('ask')} | spread {st.get('spread_pts')} pts")
    print(f"  atr_m5    : {st.get('atr_m5')} | ema9 {st.get('ema9_m5')} | ema21 {st.get('ema21_m5')}")
    print(f"  hari ini  : {st.get('total_trades_today')} trade, "
          f"{st.get('wins_today')} menang, net {st.get('net_pnl_today_usd')}")
    if st.get("atr_m5") is None:
        print("  ! snapshot broker belum terisi -> engine akan memakai Yahoo (futures)")
    return st


def bagian_sinyal() -> dict[str, Any] | None:
    token = os.environ.get("WARROOM_SERVICE_TOKEN") or _token_dari_env_file()
    h = ambil("/api/v1/tencent/forex/levels?symbol=XAUUSD", token)
    print("\n== SINYAL /forex/levels ==")
    if not h:
        print("  TIDAK BISA DIBACA")
        return None
    print(f"  status          : {h.get('status')}")
    print(f"  sumber indikator: {h.get('indicator_source')}")
    if h.get("status") == "OK":
        print(f"  arah            : {h.get('side')} | risk {h.get('risk')} reward {h.get('reward')}")
        print(f"  mode level      : {h.get('levels_mode')} | generated_at {h.get('generated_at')}")
    else:
        print(f"  alasan blokir   : {h.get('blocked_reason')}")
    return h


def _token_dari_env_file() -> str | None:
    for p in (Path("/etc/warroom/service_token.env"),):
        try:
            for line in p.read_text().splitlines():
                if line.startswith("WARROOM_SERVICE_TOKEN="):
                    return line.split("=", 1)[1].strip()
        except OSError:
            continue
    return None


def bagian_sebaran() -> None:
    print("\n== SEBARAN VERDICT LAYA ==")
    if not CSV_LOG.exists():
        print(f"  belum ada riwayat ({CSV_LOG})")
        return

    per_side: dict[str, list[float]] = defaultdict(list)
    jumlah = 0
    with CSV_LOG.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            try:
                p = float(row["confidence"])
            except (TypeError, ValueError, KeyError):
                continue
            per_side[row.get("side", "?")].append(p)
            jumlah += 1

    if not jumlah:
        print("  riwayat kosong")
        return

    print(f"  total sampel: {jumlah} (dari {CSV_LOG.name})")
    for side, vals in sorted(per_side.items()):
        vals_s = sorted(vals)
        di_atas = sum(1 for v in vals if v >= AMBANG_KINI)
        print(f"  {side:5}: n={len(vals):4} min {vals_s[0]:.3f} "
              f"median {statistics.median(vals):.3f} max {vals_s[-1]:.3f} "
              f"| >= {AMBANG_KINI:.2f}: {di_atas}/{len(vals)}")

    semua = [v for vs in per_side.values() for v in vs]
    print("\n  simulasi ambang (berapa persen sinyal akan lolos):")
    for amb in (0.50, 0.55, 0.60, 0.65, 0.70):
        lolos = sum(1 for v in semua if v >= amb)
        print(f"    ambang {amb:.2f} -> {lolos / len(semua) * 100:5.1f}% ({lolos}/{len(semua)})")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--token", default=None, help="token service War Room (opsional)")
    args = ap.parse_args()
    if args.token:
        os.environ["WARROOM_SERVICE_TOKEN"] = args.token

    print("LAPORAN KESIAPAN FOREX WAR ROOM")
    print("=" * 60)
    bagian_ea()
    bagian_sinyal()
    bagian_sebaran()
    print("\nCatatan: skrip ini hanya membaca, tidak mengubah apa pun.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
