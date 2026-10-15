# ADR-008 — Beekeeper: usulan revisi aturan saat expectancy turun (tanpa hak terapkan)

Status: **diterima** · Fase: sektor LLM & Agent

## Konteks

Strategi dievaluasi jujur per dompet (`strategi_terpilih`: aktif/paper/dihentikan dari
bukti), tetapi tidak ada mekanisme yang mengangkat sinyal "edge sedang mati" menjadi
tindakan yang bisa diputuskan. Pengalaman lapangan IDX (rolling-20 expectancy negatif,
alert "edge mati?") menunjukkan penurunan expectancy adalah peristiwa nyata yang butuh
respons terstruktur, bukan narasi. Sementara itu ``autonomy.propose`` (P5) boleh
menerapkan sendiri usulan paper & non-gate — hak yang terlalu besar untuk agen pemantau.

## Keputusan

1. **Beekeeper hanya mengusulkan.** Berbasis deteksi deterministik dua jendela
   expectancy per strategi (basis = 20 trade tuntas terlama, baru = 20 terbaru).
   Syarat usulan: expectancy baru negatif, penurunan ≥ 0,5 R/trade, dan bukan derau
   (|t| Welch ≥ 2; jendela tanpa variansi dihitung signifikan bila rata-ratanya berbeda).
2. **Usulan selalu `butuh_manusia`.** Beekeeper menulis baris ``Proposal`` (append-only)
   + event ``beekeeper.usulan`` dan TIDAK punya jalur penerapan. Nilai parameter tidak
   pernah disentuh; menerapkan = ``autonomy.apply_proposal`` oleh manusia.
3. **Gagal-tertutup.** Kill switch AI aktif atau tak terbaca → tidak ada usulan sama
   sekali; target ``gate.*``/rumus BE dan parameter terkunci ditolak tanpa ditulis
   (ADR-006: ambang = hak owner).
4. **Bukti jujur.** Baris tak tuntas (r kosong), tanpa strategi, atau tanpa waktu
   diluarkan — bukan dihitung nol. Sumber tak terbaca tidak memicu usulan.
5. **Kode murni + satu pintu DB.** `deteksi_penurunan` tanpa I/O (baris disuplai
   pemanggil, mis. job worker dari ledger/backtest); `usulkan` satu-satunya jalur tulis.

## Konsekuensi

- Usulan tampil di alur proposal yang sudah ada (tabel `proposals`, event audit), jadi
  UI/analis tidak perlu jalur baru untuk menilainya.
- Angka ambang (20/0,5 R/|t|≥2) adalah tawaran awal penyektor — mengubah nilai ambang
  tetap keputusan owner; Beekeeper mengusulkan perubahan parameter strategi, bukan gate.
- Baris hasil nyata harus dipetakan ke bentuk `{strategi, r, ts}` oleh pekerjaan pemanggil.

## Alternatif yang ditolak

- **Pakai `autonomy.propose(auto=True)`**: menerapkan sendiri usulan paper — melampaui
  mandat "hanya usulan" sektor ini.
- **Minta LLM menilai penurunan**: keputusan turun-naik expectancy itu perhitungan;
  LLM di sini tidak dibutuhkan dan menambah biaya/ketergantungan (ADR-004).
- **Penerapan otomatis kembalikan ambang lama**: melanggar ADR-006 (ambang = owner).
