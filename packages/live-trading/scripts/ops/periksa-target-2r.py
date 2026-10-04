"""Periksa sebaran hasil skenario target 2R — memastikan angka -0,635R bukan artefak."""

import collections
import json
import statistics as st
from pathlib import Path

rows = [
    json.loads(ln)
    for ln in Path("state/backtest-300d.jsonl").read_text().splitlines()
    if ln.strip()
]
print(f"  baris: {len(rows)} · punya r_tp2: {sum(1 for r in rows if r.get('r_tp2') is not None)}")

c = collections.Counter(r.get("hasil_tp2") for r in rows)
print(f"  sebaran hasil_tp2: {dict(c)}")

for nama in ("tp2", "sl", "kedaluwarsa", "terbuka", "tidak_terisi", "tidak_valid"):
    sel = [r for r in rows if r.get("hasil_tp2") == nama and r.get("r_tp2") is not None]
    if not sel:
        continue
    v = [r["r_tp2"] for r in sel]
    print(
        f"    {nama:<14} n={len(sel):<6} rata-rata {st.fmean(v):+.3f}R · "
        f"min {min(v):+.2f} · max {max(v):+.2f}"
    )

sel1 = [r for r in rows if r.get("r") is not None]
print(f"  pembanding 1R: n={len(sel1)} rata-rata {st.fmean([r['r'] for r in sel1]):+.3f}R")
