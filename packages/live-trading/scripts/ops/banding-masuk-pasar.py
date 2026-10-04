"""Masuk di harga pasar vs menunggu POI — versi cepat (tanpa biaya).

Dipakai untuk melihat arah hasil sebelum backtest dengan field lengkap selesai.
Angka biaya butuh `harga_keputusan`, jadi versi ini sengaja tanpa biaya.
"""
import json
import statistics as st

rows = [json.loads(ln) for ln in open("state/backtest-300d.jsonl") if ln.strip()]
dinilai = [r for r in rows if r.get("hasil") != "menunggu_terisi"]
punya = [r for r in dinilai if r.get("r_pasar") is not None]


def ringkas(nama, sel, ambil_r, ambil_hasil):
    nilai = [ambil_r(r) for r in sel if ambil_r(r) is not None]
    tp1 = sum(1 for r in sel if ambil_hasil(r) == "tp1")
    sl = sum(1 for r in sel if ambil_hasil(r) == "sl")
    kosong = sum(1 for r in sel if ambil_hasil(r) == "tidak_terisi")
    if not nilai:
        print(f"  {nama:<24} tidak ada data")
        return
    print(
        f"  {nama:<24} n={len(sel):<5} terisi={len(nilai):<5} kosong={kosong:<5} "
        f"TP1={tp1:<5} SL={sl:<5} expectancy={st.fmean(nilai):+.3f}R"
    )


print(f"  kandidat dinilai {len(dinilai)} · punya skenario pasar {len(punya)}\n")
ringkas("TUNGGU POI (apa adanya)", dinilai, lambda r: r.get("r"), lambda r: r.get("hasil"))
ringkas("MASUK HARGA PASAR", punya, lambda r: r.get("r_pasar"), lambda r: r.get("hasil_pasar"))

# Perbandingan berpasangan pada kandidat yang SAMA: ini yang menjawab "kalau kita ganti
# cara masuk, untung atau rugi" — bukan membandingkan dua kelompok yang isinya beda.
pasangan = [
    (float(r["r"]), float(r["r_pasar"]))
    for r in punya
    if r.get("r") is not None and r.get("r_pasar") is not None
]
if pasangan:
    selisih = [a - b for a, b in pasangan]
    menang_poi = sum(1 for s in selisih if s > 0)
    menang_pasar = sum(1 for s in selisih if s < 0)
    print(f"\n  BERPASANGAN pada {len(pasangan)} kandidat yang sama:")
    print(f"    rata-rata selisih (POI - pasar) = {st.fmean(selisih):+.3f}R")
    print(f"    POI lebih baik di {menang_poi} kasus · pasar lebih baik di {menang_pasar} kasus")
    print(f"    median selisih = {st.median(selisih):+.3f}R")

print("\n  Catatan: versi ini belum memasukkan biaya. Biaya masuk-pasar dihitung dari jarak")
print("  SL pada harga pasar (lebih lebar), jadi angka bersihnya akan lebih rendah.")
