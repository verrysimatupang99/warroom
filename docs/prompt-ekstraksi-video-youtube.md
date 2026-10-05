# Prompt ekstraksi video YouTube → teks terstruktur (untuk Gemini)

**Cara pakai:** tempel **bagian di dalam kotak** ke Gemini (yang punya akses YouTube / bisa baca video).
Kosongkan `[ISI DI SINI]`. Prompt ini **umum** — bisa dipakai untuk video apa pun yang lu rasa
relevan dengan proyek kita, bukan hanya video memecoin kemarin.

---

## PROMPT — salin mulai dari baris di bawah ini

```text
Kamu mengekstrak isi video YouTube menjadi catatan terstruktur untuk satu pengguna yang
menjalankan sistem trading otomatis (multi-pasar: crypto, memecoin, Polymarket, forex, IDX).

VIDEO: [ISI DI SINI — tempel URL video]

ATURAN UTAMA — patuhi ini di atas segalanya:

1. JANGAN MENGARANG. Setiap kalimat di keluaranmu harus bisa ditelusuri ke ucapan di video.
   Kalau sesuatu tidak disebutkan, tulis "tidak disebutkan". Jangan mengisi celah dengan
   pengetahuanmu sendiri, jangan melengkapi angka yang setengah, jangan menebak nama tools.

2. PISAHKAN TIGA HAL INI dengan tegas, jangan dicampur:
   - KLAIM   = apa yang video katakan (angka, hasil, janji)
   - BUKTI   = apa yang video TUNJUKKAN sebagai dasarnya (screenshot, data, backtest, track record)
   - OPINI   = pendapat/prediksi tanpa dasar yang ditunjukkan
   Kalau sebuah klaim tidak disertai bukti apa pun, tulis "tanpa bukti yang ditunjukkan".

3. TANDAI KEPENTINGAN UANG. Sebutkan bila video: menyertakan link afiliasi/referral,
   mempromosikan exchange/broker/tools tertentu, atau punya konflik kepentingan lain.
   Ini fakta yang harus tercatat, bukan untuk dihakimi — cukup dilaporkan apa adanya.

4. TULIS ANGKA APA ADANYA, jangan dibulatkan atau diperbaiki. Kalau video bilang "sekitar 80%",
   tulis "sekitar 80%", bukan "80%". Kalau angka tidak jelas terdengar, tulis "[tidak jelas]".

5. Bahasa keluaran: INDONESIA. Istilah teknis trading boleh tetap Inggris (backtest, slippage,
   liquidity, edge, drawdown, R multiple). Pertahankan istilah asli bila menerjemahkannya
   bisa mengubah makna.

FORMAT KELUARAN — ikuti persis:

## 1. Identitas
- Judul:
- Kanal:
- Perkiraan tanggal upload (kalau terlihat):
- Durasi:
- Bahasa asli:

## 2. Ringkasan 5 kalimat
Apa isi video ini, untuk siapa, dan apa yang penonton dijanjikan. Hanya dari isi video.

## 3. Strategi / metode yang disebutkan
Untuk SETIAP strategi, ulangi blok ini:

### Strategi N: <nama yang video pakai>
- **Inti ide** (1-2 kalimat):
- **Pasar/instrumen** yang dimaksud:
- **Aturan masuk** (kapan beli/masuk) — tulis sedetail yang video sebutkan:
- **Aturan keluar** (kapan jual/keluar, termasuk stop loss & take profit):
- **Manajemen ukuran posisi / risiko**:
- **Timeframe / jadwal** yang dipakai:
- **Syarat pasar** (dipakai di kondisi apa; kapan TIDAK dipakai):
- **Alat/platform** yang disebut (nama persis):
- **Klaim hasil** — angka apa pun yang disebut, APA ADANYA (mis. "+30% dalam 3 bulan"):
- **Bukti yang ditunjukkan** untuk klaim itu (atau "tanpa bukti yang ditunjukkan"):
- **Hal yang bisa diperiksa ulang** — sebutkan apa yang perlu diverifikasi orang lain
  sebelum angka itu bisa dipercaya:
- **Kutipan kunci** (1-3 kutipan langsung yang paling menjelaskan strategi ini):

## 4. Aturan yang bisa dieksekusi
Tulis ulang tiap aturan masuk/keluar menjadi kalimat berbentuk SYARAT yang bisa diuji mesin,
satu baris satu aturan. Contoh bentuk: "MASUK bila harga > SMA10 DAN volume >= 1,5x rata-rata
10 hari". Pakai HANYA syarat yang video sebutkan. Kalau tidak cukup detail untuk jadi aturan,
tulis barisnya sebagai "TIDAK CUKUP DETAIL: <apa yang kurang>".

## 5. Angka penting
Daftar semua angka konkret: persentase, R multiple, win rate, ukuran sampel, periode uji,
biaya, ukuran posisi. Satu baris satu angka, sertakan konteksnya. Kosongkan bila tidak ada.

## 6. Yang TIDAK disebutkan
Hal-hal penting yang justru tidak dibahas dan membuat strategi ini belum bisa dipakai:
biaya transaksi, slippage, likuiditas, ukuran sampel, kondisi pasar saat diuji, drawdown
terburuk, apa yang terjadi saat strategi gagal. Sebutkan yang benar-benar absen.

## 7. Tanda bahaya
Sebutkan bila ada: janji hasil pasti, tekanan waktu ("sekarang atau tidak selamanya"), bukti
yang tidak bisa diperiksa, hasil mustahil, perubahan klaim di tengah video, atau dorongan
mendaftar lewat link tertentu. Kalau tidak ada, tulis "tidak ditemukan".

## 8. Afiliasi & kepentingan
Link apa pun di deskripsi, kode referral, sponsor, atau produk yang dipromosikan. Tulis apa
adanya. Kalau tidak ada, tulis "tidak ada".

## 9. Relevansi untuk sistem otomatis
Pilih SALAH SATU per strategi dan jelaskan dalam 1-2 kalimat:
- **Siap diuji**: aturannya cukup jelas untuk langsung dibuat tesnya
- **Perlu dirinci**: idenya masuk akal tapi detailnya kurang
- **Tidak bisa diotomatiskan**: bergantung pada penilaian manusia/konteks yang tak terukur
- **Sampingkan**: tidak relevan atau dasarnya tidak bisa dipercaya

## 10. Transkrip lengkap
Transkrip utuh apa adanya, dipisah per kalimat atau per paragraf. Jangan diringkas, jangan
diperbaiki, jangan dibersihkan. Kalau bagian tertentu tidak terdengar jelas, tulis
[bagian tidak jelas]. Bila transkrip terlalu panjang, bagi per bagian waktu (menit ke berapa).

---
Kalau kamu tidak bisa mengakses video ini, katakan terus terang di baris pertama dan JANGAN
mengarang isinya. Lebih baik gagal jujur daripada menghasilkan ringkasan palsu.
```

---

## Catatan untuk saya (bukan bagian prompt)

**Kenapa prompt ini disusun begini** — supaya hasilnya bisa dipakai, bukan cuma enak dibaca:

| Bagian | Masalah yang dicegah |
|---|---|
| Aturan 1 & 5 | Model mengisi celah dengan pengetahuannya sendiri → angka karangan yang terlihat sah |
| Aturan 2 (klaim/bukti/opini) | Video "3 strategi" terdengar meyakinkan walau buktinya nol |
| Aturan 3 & bagian 8 | Link afiliasi harus terlihat, bukan tersembunyi di deskripsi |
| Bagian 4 | Mengubah cerita jadi **aturan yang bisa diuji** — inti supaya bisa dibandingkan dengan BSJP/SMC kita |
| Bagian 5 | "sekitar 80%" jangan jadi "80%" (kesalahan yang sudah dua kali menipu di proyek ini) |
| Bagian 6 | Yang **tidak** disebutkan justru penentu — biaya, slippage, sampel |
| Bagian 9 | Memberi label jujur sebelum sesuatu dianggap layak dikerjakan |
| Bagian 10 | Transkrip mentah = bahan pemeriksaan ulang, bukan ringkasan yang sudah ditafsirkan |

**Cara memakai hasilnya nanti:** setelah lu tempel balik hasilnya, yang gue pakai **bukan**
ringkasannya, melainkan **bagian 4 (aturan yang bisa dieksekusi)**. Aturan itu gue uji dengan cara
yang sama seperti uji BSJP — dan kalau angkanya tidak reproducible, gue bilang tidak
reproducible, seperti `+228R` dulu.

**Kalau videonya panjang:** minta Gemini mengerjakan **per bagian waktu** (0-10 menit, dst.),
lalu gabungkan. Satu kali jalan untuk video 1 jam biasanya memotong bagian akhir diam-diam.
