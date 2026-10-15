Hermes Autotrade Spec: Crypto Majors, Meteora LP, GMGN Memecoin
Spesifikasi implementasi untuk agent Hermes · disusun 16 Oktober 2026 · versi 1.0 · status: DRAFT, belum teruji
0. Baca ini dulu (aturan wajib untuk Hermes)
Dokumen ini adalah spesifikasi, bukan jaminan profit. Semua angka parameter adalah hipotesis awal dari riset publik dan harus divalidasi lewat backtest dan paper trading sebelum uang sungguhan dipakai.
Aturan non-negosiabel:
1. Mode default = PAPER. Pindah ke LIVE hanya jika pemilik menyetel mode: live secara eksplisit per strategi DAN go-live checklist (bagian 10) terpenuhi.
2. Jangan pernah menaruh private key, seed phrase, API secret, atau token di kode frontend, repo, log, atau pesan chat. Simpan di environment variable atau secret manager di sisi server.
3. API key exchange: hanya izin read + trade, tanpa izin withdraw, dan whitelist IP bila tersedia. Wallet on-chain: wallet khusus bot dengan saldo terbatas, bukan wallet utama.
4. Jangan mengarang endpoint API. Untuk LP Agent, GMGN, dan exchange, baca dokumentasi resmi atau spesifikasi OpenAPI-nya, lalu implementasikan sesuai itu. Jika dokumentasi tidak bisa diakses, berhenti dan tanyakan ke pemilik.
5. Risk Engine (bagian 2) punya hak veto atas semua strategi. Kalau Risk Engine bilang stop, semua order baru berhenti.
6. Setiap keputusan (entry, exit, skip) wajib dicatat beserta alasannya.
7. Jangan klik link dari DM, grup, atau iklan. Hanya buka domain dalam allowlist (bagian 6.6). Situs phishing yang meniru login GMGN adalah risiko nyata.
8. Dilarang menaikkan leverage, menambah modal, atau melonggarkan batas risiko tanpa persetujuan tertulis pemilik.
Pertanyaan yang harus Hermes ajukan ke pemilik sebelum mulai ada di bagian 11.
1. Arsitektur
Pisahkan menjadi dua sisi:
* Worker (server-side, long-running): data feed, tiga strategy engine, risk engine, executor adapter, state store, notifier.
* War Room (0xgunsl1ng3r.xyz): hanya dashboard dan kontrol, tanpa secret dan tanpa logika eksekusi.
Komponen
	Tugas
	data_feed
	harga, volume, data pool, data wallet; tandai data basi
	strategy_majors / strategy_lp / strategy_meme
	menghasilkan intent (bukan order langsung)
	risk_engine
	validasi setiap intent, alokasi modal, kill switch
	executor_*
	satu adapter per venue (CEX, LP Agent/Meteora, GMGN), idempoten
	state_store
	posisi, order, konfigurasi berversi; rekonsiliasi saat start
	notifier
	alert ke channel pilihan pemilik
	dashboard_api
	read-only + kontrol terbatas (bagian 6)
	Alur: strategy → intent → risk_engine (approve/reject + alasan) → executor → state_store → log + dashboard.
2. Konfigurasi global dan Risk Engine
Default (semua dapat diubah pemilik):
mode_default: paper              # paper | live, diatur per strategi
capital:
 total_trading_capital_usd: <ISI_PEMILIK>   # hanya uang yang siap hilang
 allocation_pct: { majors: 50, meteora_lp: 35, gmgn_meme: 15 }
risk:
 max_daily_loss_pct: 3          # dari total_trading_capital; lewat batas = stop semua hari itu
 max_weekly_loss_pct: 8
 kill_switch_drawdown_pct: 20   # dari puncak equity; tutup posisi, HALTED, reset manual
 max_consecutive_errors: 5      # setelah itu pause strategi terkait
 stale_data_seconds: 60         # data lebih tua = jangan buka posisi baru
 max_open_positions_total: 12
Aturan Risk Engine:
1. Tolak intent yang melanggar alokasi, batas posisi, atau aturan biaya (lihat tiap strategi).
2. Hitung equity gabungan (mark-to-market) tiap menit dan perbarui puncak equity.
3. Daily loss limit dihitung dari realized + unrealized dalam hari UTC.
4. Kill switch: tutup posisi yang bisa ditutup, batalkan order terbuka, kirim alert, set status HALTED. Hanya manusia yang boleh reset.
5. Semua batas hanya boleh diubah lewat config berversi, dengan catatan siapa dan kapan.
6. Alokasi memecoin sengaja paling kecil. Data CoinGecko menunjukkan sebagian besar keuntungan trader memecoin kecil (65,1% wallet untung hanya $1-$500 pada April 2026), dan studi itu hanya menghitung realized PnL sehingga tidak memasukkan token yang dipegang sampai nol.
3. Strategi A: Crypto Majors (CEX, spot)
3.1 Dasar
Trend following harian dengan transaksi jarang untuk menekan biaya. Studi CXO Advisory menemukan aturan pegang BTC saat harga di atas SMA dan cash saat di bawahnya menurunkan max drawdown dari -89,5% (buy-and-hold) ke kisaran -66% sampai -70% (gross). Drawdown tetap dalam, dan friksi trading bisa menghapus keunggulan. Karena itu biaya dan frekuensi transaksi rendah adalah inti desain.
3.2 Spesifikasi
Item
	Nilai awal
	Universe
	BTC, ETH, SOL spot vs USDT/USDC (konfirmasi pemilik)
	Timeframe
	1D, evaluasi sekali per hari setelah close candle UTC
	Sinyal
	LONG jika close > SMA(N); FLAT jika close <= SMA(N)
	N
	uji 50 dan 100; default 100
	Anti-whipsaw
	butuh confirm_closes: 2 close berturut-turut sebelum ubah posisi
	Leverage
	tidak ada; spot saja; tanpa short
	Sizing
	equal weight antar aset yang LONG; maks 40% bucket per aset; sisanya stable
	Stop darurat
	opsional catastrophic_stop_pct: 20 dari harga entry (jaring pengaman, bukan sinyal utama)
	Order
	limit dekat harga pasar; fallback market jika tidak terisi dalam 5 menit; client order id unik
	Biaya
	ambil fee tier aktual exchange; asumsi slippage backtest 0,05% sampai 0,1% (asumsi desain)
	Rebalance
	hanya saat sinyal berubah atau bobot menyimpang > 10 poin dari target; abaikan trade di bawah min_trade_usd
	3.3 Pseudocode
setiap hari setelah close UTC:
 untuk tiap aset:
   sinyal_long = close > SMA(N) selama confirm_closes hari berturut-turut
 target_weight = equal weight aset dengan sinyal_long (cap 40% per aset)
 intent = selisih target vs posisi sekarang
 kirim intent ke risk_engine
3.4 Validasi (wajib lulus sebelum LIVE)
* Backtest minimal 4 tahun yang mencakup fase bear market, dengan fee dan slippage, tanpa look-ahead (sinyal hanya memakai candle yang sudah close).
* Pisahkan in-sample dan out-of-sample (minimal 30% data terakhir). Pilih area parameter yang stabil, bukan satu angka terbaik. Ribuan iterasi parameter sangat rentan overfitting.
* Pembanding: buy-and-hold dan DCA bulanan dengan modal sama.
* Lulus jika, setelah biaya: max drawdown lebih kecil dari buy-and-hold, Sharpe atau Calmar tidak lebih buruk, dan hasil tidak hanya bergantung pada satu tahun atau satu trade.
* Paper trading minimal 30 hari, lalu live dengan 5% dari alokasi.
4. Strategi B: Meteora DLMM LP (via LP Agent, fallback SDK)
4.1 Fakta dari dokumentasi Meteora
* Likuiditas dipasang pada range harga (bin). Di luar range, posisi berhenti dapat fee dan tinggal satu token.
* Range tidak bisa diubah setelah posisi dibuat. Rebalance berarti withdraw lalu buka posisi baru.
* Fee tidak auto-compound; harus di-claim.
* Default 69 bin; maksimal 1.400 bin.
* Bentuk likuiditas: Spot (default jika ragu), Curve (stabil atau jarang bergerak), Bid-Ask (single-sided, DCA masuk/keluar).
* Rent posisi: sebagian refundable; pembuatan bin array baru non-refundable.
* Protocol fee tercatat 5% di panduan lama dan 10% (20% untuk Launch Pool) di panduan Dynamic Terminal. Baca dari pool, jangan hardcode.
* Posisi tidak bisa dipindah antar wallet. Withdraw single-sided dari active bin tidak bisa. Zap out ke satu token tersedia untuk posisi sampai 250 bin.
4.2 Integrasi
* Opsi 1 (utama): LP Agent REST API (punya OpenAPI spec). Baca spesifikasinya, jangan menebak endpoint. Fungsi yang dibutuhkan: analisis pool/posisi, open, rebalance, close, claim.
* Opsi 2 (fallback, kontrol penuh): SDK @meteora-ag/dlmm (TypeScript) bersama @solana/web3.js. Baca dokumentasi SDK resmi.
* Copy LP (Smart LP) = OFF secara default. Aktifkan hanya setelah vetting wallet (4.6).
4.3 Screening pool (semua syarat harus lolos)
Semua angka di bawah adalah titik awal untuk dikalibrasi, bukan hasil riset terbukti.
Parameter
	Nilai awal
	min_tvl_usd
	100000
	min_24h_volume_usd
	500000
	min_fee_tvl_24h_pct
	1.0 (jika sangat tinggi, cari penyebabnya sebelum masuk)
	min_organic_score
	ikuti skala Jupiter Organic Score; mulai dari ambang tengah lalu kalibrasi
	min_holders
	1000
	max_top10_holder_pct
	40 (kecualikan alamat LP/protokol)
	min_token_age_hours
	48
	rugcheck
	tidak ada risiko kritis
	bubblemaps
	tidak ada cluster wallet terkoordinasi yang besar
	max_pool_price_deviation_vs_jupiter_pct
	0.5
	bin_step
	kecil untuk pasangan stabil/blue-chip, lebih besar untuk token volatil (ikuti panduan Meteora, kalibrasi)
	Jangan deposit jika harga pool tidak sinkron dengan pasar: deposit akan kena arbitrase.
4.4 Entry
* Bentuk: stable/blue-chip → Curve atau Spot; token volatil → Spot dengan range lebih lebar; masuk atau keluar bertahap → Bid-Ask single-sided.
* Range: default 69 bin. Token volatil: lebar = max(69 bin, k × volatilitas realisasi 24 jam), k mulai 2, batas atas 1.400 bin.
* Ukuran: maksimal 10% bucket LP per posisi; maksimal 3 posisi bersamaan; satu posisi per token.
* Sebelum deposit: cek sinkron harga, slippage deposit, saldo SOL untuk rent dan fee.
4.5 Monitoring dan exit (loop tiap 1-5 menit)
Kondisi
	Aksi
	Active bin di dalam range
	tetap; claim fee bila unclaimed >= claim_threshold_usd (mulai 5)
	Out of range lebih dari oor_timeout_min (mulai 30)
	evaluasi rebalance (4.5.1) atau close
	Net PnL posisi <= -15% (nilai posisi + fee - modal awal, dalam USD)
	close dan zap out ke quote token/stable
	Peringatan risiko token (likuiditas ditarik, holder makin terkonsentrasi, flag baru)
	close segera
	Harga pool menyimpang dari pasar melebihi ambang
	jangan tambah likuiditas; pertimbangkan close
	Fee yield 24 jam di bawah ambang selama 3 siklus berturut-turut
	close, cari pool lain
	4.5.1 Aturan rebalance
* Rebalance hanya jika estimasi fee tambahan > 2 × biaya rebalance. Biaya = rent non-refundable + swap fee/slippage + protocol fee.
* Maksimal 3 rebalance per posisi per hari.
* Jika harga keluar range ke sisi bawah, posisi sudah penuh token yang turun. Jika tren masih turun, close, jangan rebalance, karena rebalance ke bawah berarti menambah eksposur ke aset yang jatuh.
4.6 Vetting wallet untuk Copy LP (opsional)
* Riwayat minimal 3 bulan, PnL positif konsisten lintas bulan (bukan satu bulan bagus).
* Minimal 50 posisi tertutup; posisi terbaik tidak lebih dari 30% total profit.
* Copy percentage kecil (mulai 5%).
* Angka profit viral di media sosial berasal dari wallet pilihan (survivorship bias), jangan dijadikan ekspektasi rata-rata.
4.7 Metrik wajib dan go-live
Catat: net PnL (fee + perubahan nilai - semua biaya), IL dibanding hold, fee yield per hari, jumlah dan biaya rebalance, persentase waktu in-range.
Go-live: uji di Playground LP Army (uang palsu) atau paper mode minimal 14 hari, lalu live maksimal 5% alokasi.
5. Strategi C: Memecoin via GMGN
5.1 Peringatan
Bucket terkecil; anggap uangnya siap hilang. Fee GMGN 1% per transaksi (sekitar 2% round trip sebelum priority fee). Dokumentasi GMGN sendiri memperingatkan bahwa priority fee dari order yang sering bisa mengubah target yang profit menjadi copy yang rugi.
5.2 Integrasi dan batasan
* Gunakan fitur native GMGN (copy task, order otomatis TP/SL/trailing) dan/atau GMGN.dev API. Baca dokumentasi resmi, jangan menebak endpoint.
* Copy trading dan order otomatis hanya berjalan di wallet yang dibuat GMGN, dan private key tidak bisa diekspor. Danai secukupnya.
* GMGN membatasi maksimal 10 copy task aktif; Hermes memakai maksimal 5.
* Mode paper: jika GMGN tidak menyediakan simulasi, Hermes mensimulasikan sendiri: lacak trade wallet target dari data, lalu terapkan sim_delay_seconds (3-15), slippage, fee 1%, dan priority fee ke hasilnya.
5.3 Vetting wallet target (semua harus lolos)
* Win rate di atas 60% dengan minimal 30 trade (rekomendasi satu panduan; perlakukan sebagai batas minimum, bukan jaminan).
* Realized PnL positif pada minimal 3 periode mingguan berbeda.
* Trade terbaik tidak lebih dari 40% total profit.
* Bukan bot MEV/arbitrase dan bukan sniper blok pertama (holding time median di atas 60 detik).
* Frekuensi trade wajar; frekuensi tinggi menggerus hasil lewat priority fee.
* Evaluasi ulang tiap minggu. Hentikan copy jika performa 14 hari terakhir negatif secara net setelah biaya simulasi.
5.4 Filter token (semua harus lolos sebelum entry)
* Tidak honeypot, mint authority dicabut, likuiditas dibakar atau dikunci (hasil security check GMGN + Rugcheck).
* min_liquidity_usd: 20000.
* Top 10 holder maksimal 35%; tanpa cluster insider besar (Bubblemaps dan flag insider GMGN).
* Jika developer menjual, keluar penuh (fitur Dev Sell).
5.5 Eksekusi dan biaya
Parameter
	Nilai awal
	Priority fee / tip
	mulai 0,006 SOL untuk order otomatis; naikkan hanya jika sering gagal. Sumber berbeda menyarankan 0,002 sampai 0,1 SOL, jadi uji sendiri
	Anti-MEV
	ON (di Solana butuh tip minimal 0,002 SOL)
	max_buy_sol
	ditetapkan pemilik; default rendah
	max_roundtrip_cost_pct
	5 (skip trade jika (fee 1% + tip) x 2 / ukuran trade melebihi ini)
	Aturan tip
	tip tidak boleh melebihi ukuran trade
	Catatan: dengan tip 0,002 SOL, trade di bawah sekitar 0,15 SOL otomatis ditolak aturan biaya; dengan tip 0,006 SOL trade harus sekitar 0,4 SOL ke atas. Untuk modal kecil, biaya adalah penghalang utama.
5.6 Exit dan limit
* Stop-loss -35% (sumber menyarankan rentang -30% sampai -40%).
* Take profit: jual 50% di 2x (modal kembali), sisanya dengan trailing stop 20% dari puncak (parameter untuk diuji).
* Time stop: tutup jika posisi belum mencapai +20% dalam max_hold_minutes (mulai 180, parameter untuk diuji).
* Dev sell atau flag risiko baru: keluar penuh.
* Pause 24 jam jika rugi harian bucket memecoin mencapai 25% bucket atau terjadi 3 loss berturut-turut.
5.7 Keamanan operasional
* Gunakan wallet khusus dengan saldo terbatas.
* Hanya buka domain dalam allowlist; jangan connect wallet atau login lewat link dari DM, grup, atau iklan.
* Jangan beri approval token ke kontrak asing. Hermes hanya boleh menandatangani jenis transaksi yang tercantum di config.
6. Integrasi dengan War Room (0xgunsl1ng3r.xyz)
Catatan jujur: saat dokumen ini disusun, halaman situs hanya menampilkan judul 'War Room' dan teks memuat (aplikasi yang dirender lewat JavaScript), sehingga isi dan stack-nya tidak terbaca. Hermes harus memeriksa kode dan stack situs lebih dulu sebelum memilih cara integrasi.
6.1 Prinsip
Frontend hanya menampilkan data dan mengirim perintah kontrol. Semua kunci dan eksekusi berada di worker.
6.2 API (rancangan, Hermes yang mengimplementasi)
Endpoint
	Fungsi
	GET /api/status
	status sistem, mode per strategi, status Risk Engine
	GET /api/positions
	posisi terbuka semua strategi
	GET /api/pnl?strategy=
	PnL bersih per strategi dan gabungan
	GET /api/risk
	equity, drawdown, batas harian dan mingguan
	GET /api/events?limit=
	log keputusan dan alasan
	POST /api/control/pause
	pause satu strategi
	POST /api/control/kill
	kill switch
	POST /api/control/resume
	lanjutkan; reset setelah kill butuh konfirmasi tambahan
	6.3 Autentikasi dan keamanan
* Wajib login kuat (misalnya passkey atau TOTP) sebelum endpoint kontrol aktif. Endpoint baca pun tidak boleh publik.
* Rate limit, CORS terbatas, perlindungan CSRF, dan audit log untuk setiap aksi kontrol.
* Jangan pernah mengirim secret, private key, atau API key ke browser.
6.4 Panel dashboard
Ringkasan equity dan drawdown; status Risk Engine; tab per strategi (posisi, PnL bersih, biaya); log keputusan; tombol pause dan kill.
6.5 Rekomendasi tampilan metrik
Tampilkan selalu PnL bersih setelah fee, tip, rent, dan slippage, plus perbandingan dengan alternatif sederhana (hold untuk majors; hold token atau stable untuk LP).
6.6 Allowlist domain
docs.meteora.ag, app.meteora.ag, app.lpagent.io, gmgn.ai, dan domain exchange pilihan pemilik (diisi pemilik).
7. Data model dan logging
Tabel minimal: config_versions, signals, intents, orders, fills, positions, lp_positions, risk_events, pnl_snapshots, errors.
* Setiap intent mencatat strategi, aset atau pool, alasan, dan keputusan Risk Engine.
* PnL selalu net. Log tidak boleh memuat secret.
* Rekonsiliasi saat start dan tiap 15 menit: bandingkan state lokal dengan state sebenarnya (exchange, on-chain). Jika berbeda, pause strategi terkait dan kirim alert. Sumber kebenaran adalah exchange atau on-chain.
8. Penanganan kegagalan
* RPC atau API gagal: retry dengan exponential backoff, pakai RPC cadangan; setelah max_consecutive_errors, pause.
* Order idempoten: pakai client order id dan cek status sebelum kirim ulang agar tidak ada order ganda.
* Partial fill: catat, lalu selesaikan atau batalkan sisa sesuai aturan.
* Data basi atau harga anomali (lonjakan tidak wajar dibanding sumber kedua): jangan trade.
* Restart: jangan ulang order lama; rekonsiliasi dulu.
* Semua timestamp UTC dan jam server disinkronkan (NTP).
9. Pengujian
* Unit test: sizing, filter, aturan biaya, perhitungan PnL.
* Backtest dan simulasi sesuai bagian strategi.
* Test integrasi di sandbox atau testnet bila tersedia.
* Failure injection: RPC mati, data basi, fill parsial, restart di tengah order.
* Test kill switch: harus menghentikan semua order baru dan menutup posisi dalam satu siklus.
10. Fase rollout dan go-live checklist
Fase
	Isi
	Syarat lanjut
	0 Build
	kode, test, dashboard read-only
	semua test lulus
	1 Backtest/Simulasi
	A: backtest; B: screening historis atau Playground; C: simulasi copy
	kriteria validasi tiap strategi
	2 Paper
	minimal 30 hari (A), 14 hari (B dan C)
	net positif setelah biaya dan tanpa pelanggaran risk
	3 Live mikro
	maksimal 5% alokasi tiap strategi
	30 hari tanpa insiden; PnL bersih dan drawdown sesuai batas
	4 Skala
	naik bertahap, maksimal 2x per tahap
	persetujuan tertulis pemilik di tiap tahap
	Go-live checklist: secret aman, API key tanpa izin withdraw, kill switch teruji, alert berfungsi, rekonsiliasi berjalan, pemilik menyetujui mode live.
Turunkan atau hentikan sebuah strategi jika hasil bersih setelah biaya tidak mengalahkan alternatif sederhana, atau drawdown-nya melebihi 2x hasil backtest.
11. Pertanyaan untuk pemilik
1. Exchange apa untuk majors, dan berapa fee tier-nya?
2. Berapa total modal trading dan alokasi per strategi?
3. Berapa toleransi drawdown maksimum?
4. Pakai LP Agent API atau SDK Meteora langsung?
5. Bagaimana akses GMGN (login, wallet yang dipakai)?
6. Channel notifikasi apa (Telegram, email, lainnya)?
7. Apa stack War Room (framework, hosting, sistem login)?
8. Zona waktu untuk laporan harian?
12. Sumber dan kualitas bukti
* Meteora (resmi): https://docs.meteora.ag/user-guide/guides/how-to-use-dlmm dan https://docs.meteora.ag/security-and-risks/risk-of-impermanent-loss-il
* LP Agent: https://solanacompass.com/projects/lp-agent
* GMGN: https://www.datawallet.com/crypto/gmgn-explained dan https://solanacompass.com/projects/GMGN
* Setting GMGN (blog afiliasi, kualitas bukti rendah): https://coincodecap.com/best-settings-for-gmgn-bot
* SMA pada BTC: https://cxoadvisory.com/?p=30879
* Profitabilitas trader memecoin: https://www.coingecko.com/research/publications/pump-fun-traders-are-making-a-comeback
* Contoh screening pool: https://github.com/junwatu/meridian
Catatan: angka parameter yang tidak punya sumber di atas adalah asumsi desain penulis, bukan hasil riset. Kalibrasi lewat backtest dan paper trading.
Disclaimer: dokumen ini bukan nasihat keuangan. Trading kripto dan DeFi bisa menyebabkan kerugian total, dan penulisnya bukan penasihat keuangan.