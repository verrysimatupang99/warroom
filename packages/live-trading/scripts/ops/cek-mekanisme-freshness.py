"""Cek mekanisme: apakah 'freshness merugikan' itu temuan atau artefak geometri target."""
import json
import statistics as st
from collections import Counter

rows = [json.loads(ln) for ln in open("state/backtest-300d.jsonl") if ln.strip()]
f = [r for r in rows if r.get("rules_gagal") == ["freshness"]]
o = [r for r in rows if r.get("rules_gagal") != ["freshness"]]


def rdist(rs):
    v = [
        abs(r["tp1"] - r["entry"]) / abs(r["entry"] - r["sl"])
        for r in rs
        if r.get("entry") and r.get("entry") != r.get("sl")
    ]
    return (round(st.fmean(v), 3), round(st.stdev(v), 3)) if v else None


def riskpct(rs):
    v = [abs(r["entry"] - r["sl"]) / r["entry"] * 100 for r in rs if r.get("entry")]
    return round(st.fmean(v), 3)


print(f"  TP1 dalam satuan R - ditolak freshness : {rdist(f)}")
print(f"  TP1 dalam satuan R - sisanya           : {rdist(o)}")
print(f"  jarak SL % harga - freshness : {riskpct(f)}%   sisanya: {riskpct(o)}%")
print(f"  hasil freshness-failed : {dict(Counter(r['hasil'] for r in f))}")
print(f"  hasil sisanya          : {dict(Counter(r['hasil'] for r in o))}")
