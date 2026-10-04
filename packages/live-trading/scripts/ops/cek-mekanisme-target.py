"""Uji mekanisme: kenapa kandidat yang ditolak aturan 'freshness' tampak lebih untung?

Dugaan: bukan karena aturannya salah menilai kualitas setup, tapi karena geometri target.
Kandidat yang TP1-nya baru saja tersentuh hanya butuh HARGA DATANG KEMBALI ke level itu,
bukan mencetak level baru. Kalau dugaan ini benar, jarak target dari harga saat keputusan
(disukur dalam ATR) harus lebih kecil pada kelompok freshness.

Butuh kolom `harga_keputusan` dan `atr_pct` — baru tersedia setelah backtest dijalankan
ulang dengan versi ini.
"""
import json
import statistics as st

rows = [json.loads(ln) for ln in open("state/backtest-300d.jsonl") if ln.strip()]
lengkap = [r for r in rows if r.get("harga_keputusan") and r.get("atr_pct")]
if not lengkap:
    raise SystemExit("  berkas ini belum punya harga_keputusan/atr_pct — jalankan backtest ulang")

f = [r for r in lengkap if r.get("rules_gagal") == ["freshness"]]
o = [r for r in lengkap if "freshness" not in (r.get("rules_gagal") or [])]


def jarak_atr(rs):
    v = []
    for r in rs:
        harga = float(r["harga_keputusan"])
        atr = float(r["atr_pct"]) / 100 * harga
        if atr > 0:
            v.append(abs(float(r["tp1"]) - harga) / atr)
    return v


def ringkas(nama, rs):
    v = jarak_atr(rs)
    if not v:
        print(f"  {nama:<26} n=0")
        return
    tp1 = sum(1 for r in rs if r.get("hasil") == "tp1")
    sl = sum(1 for r in rs if r.get("hasil") == "sl")
    print(
        f"  {nama:<26} n={len(rs):<5} target rata-rata {st.fmean(v):5.2f} ATR "
        f"(median {st.median(v):5.2f}) · TP1 {tp1} · SL {sl}"
    )


print("  Jarak TP1 dari harga saat keputusan, dalam satuan ATR:")
ringkas("ditolak freshness", f)
ringkas("sisanya", o)
ringkas("semua", lengkap)

print("\n  Bacaannya: kalau kelompok freshness punya target yang lebih dekat (angka ATR lebih")
print("  kecil), maka keunggulannya soal geometri target — bukan bukti aturannya salah.")
