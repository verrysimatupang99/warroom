"""Apakah keunggulan 'freshness' cuma kedok dari jarak SL yang lebih rapat?

Kalau kelompok SL rapat memang lebih baik di SEMUA kandidat, maka freshness bukan
penyebab — ia cuma kebetulan menandai kelompok dengan SL rapat.
"""
import json
import statistics as st

rows = [json.loads(ln) for ln in open("state/backtest-300d.jsonl") if ln.strip()]
terisi = [r for r in rows if r.get("hasil") in ("tp1", "sl") and r.get("entry")]
for r in terisi:
    r["risk_pct"] = abs(r["entry"] - r["sl"]) / r["entry"] * 100

terisi.sort(key=lambda r: r["risk_pct"])
n = len(terisi)
bagian = [terisi[: n // 3], terisi[n // 3 : 2 * n // 3], terisi[2 * n // 3 :]]
nama = ["SL rapat (<1/3)", "SL sedang", "SL lebar (>2/3)"]

print(f"  kandidat terisi dengan TP1/SL kena: {n}\n")
print(f"  {'kelompok':<18} {'n':>5} {'SL%':>7} {'TP1':>6} {'SL':>6} {'TP1 rate':>9} {'eks R':>8}")
for nm, sel in zip(nama, bagian, strict=True):
    tp1 = sum(1 for r in sel if r["hasil"] == "tp1")
    sl = sum(1 for r in sel if r["hasil"] == "sl")
    rate = tp1 / len(sel) * 100
    eks = (tp1 - sl) / len(sel)
    rp = st.fmean(r["risk_pct"] for r in sel)
    print(f"  {nm:<18} {len(sel):>5} {rp:>6.2f}% {tp1:>6} {sl:>6} {rate:>8.1f}% {eks:>+7.3f}R")

print("\n  Bacaannya: kalau kelompok SL rapat memang unggul di semua kandidat,")
print("  maka 'freshness merugikan' sebenarnya soal jarak SL, bukan soal basi.")
