# PROMPT — Bangun "War Room" + "Market Crypto" di Server Lain

Kamu adalah agen Hermes di server lain. Tugasmu: membangun dua proyek trading
crypto yang sudah terbukti berjalan di server lain, lalu memverifikasi benar-
benar hidup. Jangan berhenti di "script sudah ditulis" — buktikan dengan run
nyata, output nyata, dan pesan yang benar-benar terkirim.

Baca seluruh dokumen ini sebelum menyentuh apa pun. Kerjakan berurutan.

═══════════════════════════════════════════════════════════════════
BAGIAN 1 — KONTEKS & PEMBAGIAN TANGGUNG JAWAB
═══════════════════════════════════════════════════════════════════

Dua proyek terpisah, jangan dicampur:

  WAR ROOM
    - Otak analisis. Scan market, nilai koin, hasilkan signal.
    - Menghasilkan JSON signal + teks siap-kirim Telegram.
    - TIDAK mengirim pesan sendiri, TIDAK eksekusi order.

  MARKET CRYPTO
    - Wajah & tangan. Dashboard, pengiriman ke Telegram, eksekusi order.
    - Membaca output War Room, mengeksekusi ke exchange, melaporkan hasil.
    - TIDAK menganalisis market sendiri.

Aturan pembatas: kalau ada logika analisis di Market Crypto, itu bug — pindah
ke War Room. Kalau ada pengiriman pesan atau eksekusi order di War Room, itu
bug — pindah ke Market Crypto.

═══════════════════════════════════════════════════════════════════
BAGIAN 2 — STRATEGI (WAJIB DIIKUTI PERSIS)
═══════════════════════════════════════════════════════════════════

Sumber: spesifikasi pemilik proyek. Ini bukan saran, ini kontrak.

Dua play:

  SCALPING
    Timeframe analisis : 1H / 15M / 5M
    Entry di           : M5
    RR                 : TP1 = 1R, TP2 = 3R   (WAJIB dipatok di kode)

  INTRADAY
    Timeframe analisis : 4H / 1H / 15M
    Entry di           : M15
    RR                 : TP1 = 1R, TP2 = 2R   (WAJIB dipatok di kode)

Universe koin: Big Cap + Mid Cap, data dari MEXC API.

Indikator wajib (hitung sendiri, jangan minta LLM mengarang):
    VWAP · ATR(14) · RSI(14) · MACD(12,26,9) · EMA20 · EMA50 · EMA200
    + market struktur multi-timeframe

Stop Loss:
    - berbasis ATR
    - diletakkan DI BALIK liquidity sweep terdekat (bukan asal di bawah entry)

Take Profit:
    - TP1 = 1R dari entry fill
    - TP2 = sesuai RR play (3R scalping / 2R intraday)

Filter choppy/sideways: WAJIB. Gate berdasarkan ATR per timeframe.
    Referensi yang sudah terbukti:
      scalping  : ATR M5  >= 0.22%
      intraday  : ATR 1H  >= 1.8%
    Di bawah ambang -> jangan ada signal.

Data volume:
    - Ambil dari BINANCE, bukan MEXC (likuiditas Binance lebih representatif).
    - Volume 24 jam
    - Volume M15, cek konsistensi ~20% per candle
    - Nilai kualitas: SANGAT BAIK / BAIK / CUKUP
      (dari likuiditas, volume relatif, dan kemerataan)
    - Kalau Binance rate-limit: fallback ke MEXC, dan TANDAI di output bahwa
      sumbernya fallback. Jangan diam-diam.

═══════════════════════════════════════════════════════════════════
BAGIAN 3 — ARSITEKTUR 3 AGENT (di dalam War Room)
═══════════════════════════════════════════════════════════════════

  AGENT_1 — Market Observer
    Input : OHLCV multi-TF, ticker, volume
    Tugas : hitung indikator, baca struktur multi-TF, jalankan gate choppy
    Output: ringkasan terstruktur per koin + daftar play yang ELIGIBLE
            (SCALPING / INTRADAY / keduanya / tidak ada)

  AGENT_2 — Setup Creator
    Input : output Agent_1
    Tugas : tentukan arah, zona entry, SL (ATR + liquidity sweep), TP1/TP2
            sesuai RR yang dipatok
    Output: kandidat signal lengkap dengan level numerik

  AGENT_3 — Risk Gate
    Input : kandidat signal + kondisi BTC
    Tugas : cek bias BTC, tolak signal yang melawan bias
    Output: APPROVED / REJECTED + alasan

PENTING — tegakkan di KODE, bukan di prompt LLM:
    - RR TP1/TP2 harus dihitung ulang dari level nyata. Kalau LLM memberi
      level yang tidak memenuhi RR, TOLAK signalnya. Jangan "sesuaikan RR
      mengikuti level" — itu membalik kontrak.
    - Gate choppy harus berupa ambang angka, bukan kalimat "hindari sideways".
    - Bias BTC harus gate keras, bukan imbauan.

Referensi bias BTC yang sudah terbukti (boleh dipakai):
    Bias = BTC 1H close vs EMA20 DAN BTC 1D close vs EMA20
      keduanya di atas -> BULLISH (hanya LONG)
      keduanya di bawah -> BEARISH (hanya SHORT)
      selain itu -> NEUTRAL (tidak ada signal)
    Pakai deadband +/-0.5% di sekitar EMA supaya noise dekat garis tidak
    dianggap bias bersih.

═══════════════════════════════════════════════════════════════════
BAGIAN 4 — FORMAT SIGNAL TELEGRAM
═══════════════════════════════════════════════════════════════════

Ikuti persis bentuk ini (emoji & urutan jangan diubah):

🔎 Signal ID: #SIGxxxxxx
📊 XXXUSDT — INTRADAY · SHORT
📉 Short Entry Zone: <low> – <high>
🎯 TP1: <harga>
🎯 TP2: <harga>
🔺 SL: <harga>
📌 R:R 1:1 (TP1) · 1:2 (TP2)
🛡 Risk: <x>% balance
⏱️ Durasi: <rentang jam>
💡 TP1 → Partial 50% + SL ke BE
📦 Order: <limit/market>
🧭 Confluence 3/3 TF searah.
Volume 24j : $<xx>M
Volume 15m : <konsisten/tidak> (20% candle)
Kualitas   : <SANGAT BAIK / BAIK / CUKUP>

Kalau tidak ada signal yang lolos semua gate: cetak HANYA token [SILENT] dan
jangan kirim pesan apa pun. Jangan kirim pesan "tidak ada signal" — itu spam.

═══════════════════════════════════════════════════════════════════
BAGIAN 5 — DASHBOARD MARKET CRYPTO
═══════════════════════════════════════════════════════════════════

11 komponen wajib, semua harus ada:

   1. Balance MEXC (live, bukan mock)
   2. Posisi open
   3. Estimasi R
   4. Winrate
   5. Koin yang discan (dari MEXC API, tampilkan jumlah + nama)
   6. Equity curve berdasarkan RR yang didapat
   7. Thumbnail play aktif (SCALPING / INTRADAY — nyala atau mati)
   8. Mode job — status 3 agent (idle / running / done)
   9. Thumbnail signal & watchlist
  10. Thumbnail entry yang sedang berjalan di MEXC
  11. Thumbnail order yang masih pending

Aturan dashboard:
    - Harus enak dibaca di HP. Ini untuk dipantau sambil kerja.
    - Angka uang WAJIB dari API exchange, bukan hasil hitungan lokal.
    - Kalau data gagal diambil: tampilkan status "DATA GAGAL", jangan
      tampilkan angka 0 yang menyesatkan.
    - Auto-refresh, dan tampilkan jam update terakhir.

═══════════════════════════════════════════════════════════════════
BAGIAN 6 — EKSEKUSI & PROTEKSI (Market Crypto)
═══════════════════════════════════════════════════════════════════

Urutan wajib saat mengeksekusi signal:

  1. Cek batas posisi. Maksimum 5 posisi terbuka (terisi + pending).
     Slot bebas saat TP1 kena -> partial 50% + SL ke BE.
  2. Cek rem harian. Empat LOSS BERTURUT dalam satu hari (tanggal WIB) ->
     TUTUP SEMUA posisi dan batalkan semua pending. Win memutus hitungan.
     0R dianggap netral, tidak memutus.
  3. Entry HANYA limit order. DILARANG stop order untuk entry.
     Alasan: stop-entry terisi di ujung breakout; breakout palsu = langsung
     round-trip ke SL. Entry = sisi zona yang tersentuh lebih dulu.
  4. Pasang SL saat order dibuat, JANGAN tunggu fill.
  5. Kalau pemasangan SL GAGAL: TUTUP posisi SEKARANG. Jangan pernah
     tinggalkan posisi tanpa proteksi.
  6. Verifikasi proteksi: total volume stop-order harus == volume posisi,
     DAN benar-benar ada SL. Bukan sekadar "ada order".

Manajemen TP:
    SCALPING : pasang SL + TP3 saat entry.
               TP1 kena -> tutup 50% manual, SL ke BE
               TP2 kena -> tutup 50% lagi
               TP3 kena -> tutup semua
    INTRADAY : pasang SL + TP2 saja.
               TP1 kena -> tutup 50% manual, SL ke BE
               TP2 kena -> tutup sisa

Harga TP/SL yang dicatat ke jurnal WAJIB dari exchange (history_orders
createTime), bukan dari jam evaluasi lokal.

═══════════════════════════════════════════════════════════════════
BAGIAN 7 — JEBAKAN YANG SUDAH MEMAKAN KORBAN (baca, jangan ulangi)
═══════════════════════════════════════════════════════════════════

1. CANCEL SEMUA STOP ORDER ITU GLOBAL
   Di MEXC, endpoint cancel-all TIDAK peduli parameter symbol. Memanggilnya
   membatalkan proteksi SEMUA posisi sekaligus. Bersihkan zombie order satu
   per satu lewat cancel?orderIds=.

2. ZOMBIE ORDER MEMAKAN KUOTA
   Order dengan isFinished=1 dan error 8913 tetap dihitung. Kalau dibiarkan,
   pemasangan SL baru gagal dengan error 5004. Bersihkan dulu, baru arm.

3. JANGAN STRINGIFY ANGKA HARGA
   Kirim SL/TP sebagai FLOAT. Mengirim sebagai string memicu error 2015.

4. SCALPING SHORT ADALAH PENYUMBANG RUGI TERBESAR
   Di data historis: SHORT+SCALPING saja n=31, winrate 32.3%, -10.37R.
   Tanpa kategori itu, hasil keseluruhan berbalik jadi positif.
   SL di bawah 1.5% punya winrate 32.1%, sedangkan SL 3-5% punya 53.3%.
   Jangan longgarkan aturan ini tanpa data baru.

5. TOKEN TIDAK BOLEH DICETAK
   Jangan pernah tulis API key ke chat, log, commit, atau output dashboard.
   Simpan di .env dengan chmod 600, rujuk lewat nama variabel.

═══════════════════════════════════════════════════════════════════
BAGIAN 8 — LANGKAH KERJA
═══════════════════════════════════════════════════════════════════

1. ORIENTASI
   - Inventaris apa yang sudah ada di server ini: Hermes versi apa, provider
     apa, cron apa saja, service apa yang jalan, port apa yang bebas.
   - JANGAN menimpa konfigurasi yang sudah ada.

2. SUSUN STRUKTUR
   - Buat direktori proyek terpisah untuk War Room dan Market Crypto.
   - Tulis dulu kontrak antar keduanya (bentuk JSON signal, field wajib).
   - Tulis README singkat: apa yang dilakukan tiap komponen.

3. BANGUN WAR ROOM
   - Implementasi indikator. Verifikasi angkanya masuk akal terhadap data
     nyata (bandingkan dengan hitungan manual di beberapa candle).
   - Implementasi 3 agent.
   - Implementasi gate RR di kode (tolak yang tidak memenuhi).
   - Jalankan sekali secara manual. Tunjukkan output nyata.

4. BANGUN MARKET CRYPTO
   - Eksekusi + proteksi sesuai Bagian 6.
   - Dashboard 11 komponen.
   - Uji dengan mode paper dulu, JANGAN langsung uang sungguhan.

5. SAMBUNGKAN KE HERMES
   - Daftarkan cron. Ingat: field script hanya menerima NAMA FILE, bukan path.
   - Script no_agent: stdout = pesan yang dikirim. Kosong atau [SILENT] =
     tidak mengirim apa pun.
   - Pastikan idempoten: cron yang jalan tiap 5 menit tidak boleh dobel.

6. VERIFIKASI (INI YANG MENENTUKAN)
   - Jalankan scanner manual, tunjukkan output.
   - Pastikan pesan benar-benar terkirim ke Telegram, bukan cuma "seharusnya
     terkirim". Cek message_id balik.
   - Buka dashboard, pastikan 11 komponen terisi data nyata.
   - Kalau ada angka 0 padahal harusnya ada data: itu bug, bukan "belum ada
     posisi". Bedakan keduanya.

7. LAPOR
   Laporkan apa adanya:
   - Apa yang sudah jalan (dengan bukti)
   - Apa yang belum jalan dan kenapa
   - Angka nyata dari run pertama
   - Risiko yang kamu lihat
   Jangan mengarang hasil yang terlihat berhasil.

═══════════════════════════════════════════════════════════════════
BAGIAN 9 — LARANGAN
═══════════════════════════════════════════════════════════════════

- Jangan eksekusi uang sungguhan sebelum pemilik proyek menyetujui eksplisit.
  Mulai dari paper mode.
- Jangan ubah model default atau provider chat utama tanpa izin.
- Jangan hapus atau timpa cron job yang sudah ada di server ini.
- Jangan mencetak API key di mana pun.
- Jangan mengarang hasil verifikasi. Kalau gagal, bilang gagal beserta
  error aslinya.
- Jangan menyimpang dari RR yang dipatok (1:3 scalping, 1:2 intraday) dengan
  alasan "menyesuaikan kondisi market". Kalau ingin mengubah, minta izin dulu.
