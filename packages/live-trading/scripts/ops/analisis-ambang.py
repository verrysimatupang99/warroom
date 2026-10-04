"""Apakah ambang 1% ATR dan aturan SL itu berada di tempat yang berarti?

"Aturan berguna/tidak" hanya jawaban ya-atau-tidak. Yang lebih berguna: bagaimana hasil
berubah terhadap nilai ambangnya. Kalau edge baru muncul di atas ATR 2%, maka ambang 1%
cuma kebetulan lewat — dan itu terlihat di sini, bukan di kesimpulan biner.

Semua angka setelah biaya. Butuh kolom `atr_pct` (baru ada setelah backtest dijalankan ulang).
"""
import json
import statistics as st

FEE_PER_SISI = 0.0005

rows = [json.loads(ln) for ln in open("state/backtest-300d.jsonl") if ln.strip()]
dinilai = [r for r in rows if r.get("hasil") != "menunggu_terisi"]


def bersih(r):
    if r.get("r") is None or not r.get("entry") or not r.get("sl"):
        return None
    risk = abs(float(r["entry"]) - float(r["sl"]))
    if risk <= 0:
        return None
    return r["r"] - (2 * FEE_PER_SISI * float(r["entry"])) / risk


def bucket(nama, kunci, potong, label):
    print(f"\n  {nama}")
    print(f"    {'rentang':<16} {'n':>5} {'terisi':>7} {'TP1':>6} {'SL':>6} {'TP1 rate':>9} {'bersih':>9}")
    for lo, hi, nm in label:
        sel = [r for r in dinilai if lo <= kunci(r) < hi]
        if len(sel) < 5:
            continue
        nilai = [b for b in (bersih(r) for r in sel) if b is not None]
        tp1 = sum(1 for r in sel if r.get("hasil") == "tp1")
        sl_ = sum(1 for r in sel if r.get("hasil") == "sl")
        rate = tp1 / (tp1 + sl_) * 100 if (tp1 + sl_) else 0.0
        eks = st.fmean(nilai) if nilai else 0.0
        print(
            f"    {nm:<16} {len(sel):>5} {len(nilai):>7} {tp1:>6} {sl_:>6} "
            f"{rate:>8.1f}% {eks:>+8.3f}R"
        )
    print(f"    {potong}")


def atr(r):
    a = r.get("atr_pct")
    if a is None:
        return -1.0
    return float(a)


def slpct(r):
    if not r.get("entry") or not r.get("sl"):
        return -1.0
    return abs(float(r["entry"]) - float(r["sl"])) / float(r["entry"]) * 100


lengkap = [r for r in dinilai if r.get("atr_pct")]
if not lengkap:
    raise SystemExit("  berkas belum punya atr_pct — jalankan backtest ulang dulu")

print(f"  kandidat dinilai: {len(dinilai)} · dengan atr_pct: {len(lengkap)}")

bucket(
    "Menurut ATR 1 jam saat keputusan (ambang aturan: 1.0%)",
    atr,
    "Aturan menolak < 1,0%. Kalau baris di atas 1,0% tidak lebih baik, ambangnya tidak bekerja.",
    [
        (0.0, 0.5, "< 0,5%"),
        (0.5, 1.0, "0,5-1,0%"),
        (1.0, 1.5, "1,0-1,5%"),
        (1.5, 2.0, "1,5-2,0%"),
        (2.0, 3.0, "2,0-3,0%"),
        (3.0, 100.0, "> 3,0%"),
    ],
)

bucket(
    "Menurut jarak SL (% harga) — aturan menolak > 5% dan < 0,5%",
    slpct,
    "Kalau kelompok SL lebar tidak lebih buruk, batas 5% itu tidak terbukti.",
    [
        (0.0, 0.5, "< 0,5%"),
        (0.5, 1.0, "0,5-1,0%"),
        (1.0, 2.0, "1,0-2,0%"),
        (2.0, 3.0, "2,0-3,0%"),
        (3.0, 5.0, "3,0-5,0%"),
        (5.0, 100.0, "> 5,0%"),
    ],
)
