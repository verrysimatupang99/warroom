"""Pilih ukuran target dari sebaran MFE — tanpa menjalankan backtest ulang.

Logikanya sederhana: kalau trade bergerak menguntungkan sebesar MFE, maka target T hanya
tercapai kalau MFE >= T. Jadi peluang kena target adalah proporsi kandidat dengan MFE >= T.
Perkiraan di sini mengabaikan urutan SL-dulu/TP-dulu di dalam jendela; karena itu angka
E(R) di bawah adalah batas atas, bukan janji.

Biaya dihitung dalam satuan R (tetap, tidak tergantung ukuran target) — justru itu intinya:
target lebih jauh memakai biaya yang sama, jadi biaya per R mengecil.
"""
import json
import statistics as st

FEE_PER_SISI = 0.0005

rows = [json.loads(ln) for ln in open("state/backtest-300d.jsonl") if ln.strip()]
terisi = [
    r
    for r in rows
    if r.get("r_mfe") is not None and r.get("entry") and r.get("sl")
]
if not terisi:
    raise SystemExit("  berkas belum punya r_mfe — jalankan backtest ulang dulu")


def biaya_r(r):
    risk = abs(float(r["entry"]) - float(r["sl"]))
    if risk <= 0:
        return 0.0
    return (2 * FEE_PER_SISI * float(r["entry"])) / risk


mfe = [r["r_mfe"] for r in terisi]
print(f"  kandidat terisi: {len(terisi)}")
print("  MFE (seberapa jauh bergerak menguntungkan, dalam R):")
for q, nm in ((0.25, "kuartil bawah"), (0.5, "median"), (0.75, "kuartil atas"), (0.9, "10% terbaik")):
    print(f"    {nm:<14} {st.quantiles(mfe, n=100)[int(q * 100) - 1]:+.2f}R")
print(f"    {'rata-rata':<14} {st.fmean(mfe):+.2f}R")

print("\n  Kalau targetnya sejauh T (stop tetap 1R), perkiraan batas atas:")
print(f"    {'target':>7} {'kena':>7} {'peluang':>9} {'E kotor':>9} {'biaya':>8} {'E bersih':>9}")
for T in (0.5, 1.0, 1.5, 2.0, 3.0, 4.0):
    kena = sum(1 for x in mfe if x >= T)
    p = kena / len(terisi)
    kotor = T * p - 1 * (1 - p)
    biaya = st.fmean(biaya_r(r) for r in terisi)
    print(f"    {T:>6.1f}R {kena:>7} {p * 100:>8.1f}% {kotor:>+8.3f}R {biaya:>7.3f}R {kotor - biaya:>+8.3f}R")

print("\n  Catatan: ini batas atas. Urutan kejadian (SL dulu atau target dulu) tidak terlihat")
print("  dari MFE/MAE, jadi hasil nyata selalu lebih rendah atau sama dengan angka di atas.")
