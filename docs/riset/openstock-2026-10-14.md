# Riset: OpenStock (Open-Dev-Society) — apa yang layak dipinjam

Tanggal: 14 Okt 2026. Sumber: https://github.com/Open-Dev-Society/OpenStock (README, lisensi).
Kesimpulan singkat: **jangan adopsi kodenya; pinjam beberapa pola UX saja.**

## Apa itu OpenStock

Aplikasi **tracker saham global** (harga, watchlist, alert, chart) — bukan sistem
trading, bukan mesin sinyal. 178 commit, ~13.000 pengguna.

- Stack: Next.js (App Router) + shadcn/ui + Tailwind + Better Auth + **MongoDB** +
  Finnhub (data) + TradingView (widget/chart).
- Cakupan: 30+ bursa saham internasional (NSE, LSE, TSX, …).
- Lisensi: **AGPL-3.0**.

## Kenapa TIDAK diadopsi

1. **AGPL-3.0 = penghalang keras.** Memodifikasi/mendistribusikan/menjalankannya
   sebagai layanan web mewajibkan merilis source sendiri di bawah AGPL + kredit.
   War Room adalah repo privat dengan gate live sensitif — menyerap kode AGPL tidak
   dapat diterima.
2. **Stack bertabrakan total.** MongoDB (kita Postgres) · React/Next (kita SvelteKit) ·
   Finnhub (kita OKX/Arjum/TVC/GMGN/Polymarket). Mengadopsi = memelihara dua sistem.
3. **Filosofi berlawanan.** OpenStock = dashboard widget (TradingView) untuk dilihat.
   War Room = "angka hanya dari tabel `facts`, kosong = —, jangan mengarang angka".
   OpenStock tidak punya gate, verifikasi bukti, atau kebijakan paper/live.
4. **Fokus pasar berbeda.** OpenStock saham global; War Room crypto/IDX/forex/meme/
   Polymarket. IDX War Room lewat Arjum (bandarmologi/BSJP), bukan Finnhub.

## Yang layak dipinjam (IDE saja — bangun sendiri dari nol)

1. **Command palette (⌘K).** Pencarian cepat lintas pasar/alat. War Room punya banyak
   area; satu pintu masuk cepat akan menaikkan kecepatan navigasi.
2. **Cross-source sentiment.** OpenStock menggabungkan Reddit/X/news/Polymarket.
   War Room sudah punya Polymarket + GMGN; mengaitkan sentimen sosial ke sinyal
   (dengan label kejujuran "belum terverifikasi") adalah fitur nyata.
3. **Heatmap pasar.** Untuk halaman "ringkas" — menampilkan semua pasar sekaligus
   (warna = seberapa layak/segar) alih-alih tabel panjang.
4. **Onboarding personal (negara, tujuan, toleransi risiko).** Bisa dipakai untuk
   mengatur default tampilan per pengguna — tentu tanpa mengorbankan prinsip
   "UI tidak menghitung sendiri".

## Aturan bila memakai ide ini

- **Tidak menyalin kode** (AGPL). Semua di atas dibangun ulang dari kebutuhan kita.
- Setiap fitur UI tetap patuh: angka dari `facts`, ketiadaan data = `n/a`/`—`, bukan `0`.
- Catat di PR bila fitur menyentuh ambang gate — hanya owner yang boleh mengubah.

## Catatan pembanding

OpenStock lebih **dalam di polish UI/UX stock app**. War Room lebih **dalam di
kebenaran angka & keselamatan eksekusi** (gate Wilson CI + deff, otonomi, dry-run,
audit LLM, paper/live). Jadi: OpenStock = rujukan tampilan, bukan rujukan arsitektur.
