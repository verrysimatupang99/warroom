#!/usr/bin/env python3
"""RESET HALTED dompet Strategi A — HANYA OWNER (spec §2.4: reset manual).

Usage: sudo -u admin .venv/bin/python ops/harian-reset.py --pesan "alasan"
"""
import argparse
import datetime as dt
import json
import sys
from pathlib import Path

P = Path("/home/admin/live-trading/state-harian/state/harian_state.json")
ap = argparse.ArgumentParser()
ap.add_argument("--pesan", required=True)
a = ap.parse_args()
st = json.loads(P.read_text()) if P.exists() else {}
if not st.get("halted"):
    print("tidak dalam keadaan HALTED — tidak ada yang direset")
    sys.exit(0)
st["halted"] = False
st["alasan_halted"] = None
st.setdefault("riwayat_reset", []).append(
    {"waktu": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"), "pesan": a.pesan})
P.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")
print("HALTED dilepas oleh owner:", a.pesan)
