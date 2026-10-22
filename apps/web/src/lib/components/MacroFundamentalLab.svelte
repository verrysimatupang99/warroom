<script lang="ts">
	/**
	 * MacroFundamentalLab.svelte
	 * Tab khusus Belajar Fundamental & Mekanika Pasar Global (Emas, Valuta, Kripto, Saham).
	 * Sumber ilmu kredibel: Federal Reserve (FRED), BIS, Ray Dalio (Economic Principles), Bank Indonesia, CFA Institute.
	 * Disajikan dalam bahasa manusia yang intuitif, padat, dan langsung bisa dihubungkan ke chart nyata.
	 */
	import HonestyTag from './HonestyTag.svelte';

	// Sub-topik belajar fundamental
	let activeTopic = $state<'korelasi' | 'makro' | 'sesi' | 'skenario'>('korelasi');

	// State interaktif untuk simulator skenario data ekonomi
	let selectedNews = $state<'cpi' | 'nfp' | 'fomc'>('cpi');
	let newsOutcome = $state<'naik' | 'turun'>('naik');

	const skenarioDampak = $derived.by(() => {
		if (selectedNews === 'cpi') {
			if (newsOutcome === 'naik') {
				return {
					judul: 'Inflasi (CPI) Lebih Tinggi dari Ekspektasi (Panas)',
					logika: 'Inflasi tinggi memaksa The Fed menahan suku bunga tinggi lebih lama (Hawkish) agar ekonomi melambat.',
					dxy: { status: 'MENGUAT (BULLISH)', ket: 'Dolar dicari karena yield AS tetap tinggi.' },
					gold: { status: 'TURUN (BEARISH)', ket: 'Biaya peluang memegang emas non-bunga jadi mahal saat imbal hasil dolar tinggi.' },
					btc: { status: 'TERTEKAN (BEARISH/VOLATIL)', ket: 'Aset spekulatif berisiko tinggi biasanya dijauhi saat likuiditas dolar ketat.' },
					kesimpulan: 'Hindari Buy Emas/Kripto sesaat setelah rilis. Peluang biasanya ada pada penguatan Dolar AS.'
				};
			} else {
				return {
					judul: 'Inflasi (CPI) Lebih Rendah dari Ekspektasi (Mendingin)',
					logika: 'Inflasi mendingin memberi ruang bagi The Fed untuk memangkas suku bunga (Dovish).',
					dxy: { status: 'MELEMAH (BEARISH)', ket: 'Dolar dijual karena prospek imbal hasil obligasi AS menurun.' },
					gold: { status: 'TERBANG (BULLISH)', ket: 'Emas menjadi primadona lindung nilai saat dolar melemah dan suku bunga riil turun.' },
					btc: { status: 'RELI (BULLISH)', ket: 'Likuiditas global longgar mengalir cepat ke pasar kripto dan saham tech.' },
					kesimpulan: 'Kondisi ideal untuk tren kelanjutan reli Emas (XAUUSD) dan Bitcoin.'
				};
			}
		} else if (selectedNews === 'nfp') {
			if (newsOutcome === 'naik') {
				return {
					judul: 'Tenaga Kerja (NFP) Sangat Kuat & Pengangguran Rendah',
					logika: 'Pasar tenaga kerja yang solid berarti ekonomi AS masih kuat & konsumsi tetap tinggi, meredam resesi tapi menunda pemotongan bunga.',
					dxy: { status: 'MENGUAT (BULLISH)', ket: 'Ekonomi AS dinilai tangguh dibanding Eropa atau Asia.' },
					gold: { status: 'TURUN SEMENTARA', ket: 'Ekspektasi pemangkasan bunga mundur ke bulan berikutnya.' },
					btc: { status: 'NETRAL / VOLATIL', ket: 'Kocokan dua arah sering terjadi pada menit-menit awal rilis.' },
					kesimpulan: 'Pasar sering melakukan reaksi pertama yang salah (fakeout 5m pertama), tunggu retest level struktur.'
				};
			} else {
				return {
					judul: 'Tenaga Kerja (NFP) Anjlok & Pengangguran Naik',
					logika: 'Sinyal bahaya perlambatan ekonomi. The Fed didesak segera memangkas suku bunga darurat.',
					dxy: { status: 'JATUH (BEARISH)', ket: 'Kekhawatiran resesi memicu arus keluar dari aset Dolar.' },
					gold: { status: 'BULLISH KUAT', ket: 'Emas diburu ganda: sebagai safe-haven resesi dan penerima manfaat pelemahan suku bunga.' },
					btc: { status: 'BULLISH', ket: 'Katalis pemangkasan suku bunga memicu narasi suntikan likuiditas baru.' },
					kesimpulan: 'Kondisi bullish struktural untuk komoditas logam mulia.'
				};
			}
		} else {
			// FOMC
			if (newsOutcome === 'naik') {
				return {
					judul: 'The Fed Menaikkan Suku Bunga atau Sikap Hawkish Keras',
					logika: 'Jerome Powell menegaskan perang inflasi belum usai, tidak ada pemangkasan dalam waktu dekat.',
					dxy: { status: 'RELIKAN (BULLISH)', ket: 'Imbal hasil US Treasury melonjak.' },
					gold: { status: 'TERTEKAN PARAH', ket: 'Suku bunga riil positif menekan emas.' },
					btc: { status: 'DUMP / TURUN', ket: 'Uang beralih dari aset berisiko ke obligasi pemerintah AS berbunga tinggi.' },
					kesimpulan: 'Mode Risk-Off global. Lindungi modal, jangan memaksakan melawan arah arus modal institusi.'
				};
			} else {
				return {
					judul: 'The Fed Memangkas Suku Bunga atau Sikap Dovish Lembut',
					logika: 'The Fed mulai mencetak/melonggarkan likuiditas (siklus pelonggaran moneter / Quantitative Easing).',
					dxy: { status: 'BEARISH JANGKA PANJANG', ket: 'Pasokan dolar bertambah, nilai tukar relatif turun.' },
					gold: { status: 'SUPER BULLISH', ket: 'Pelemahan daya beli fiat menguntungkan logam mulia secara historis.' },
					btc: { status: 'BULL RUN INFLOW', ket: 'Likuiditas berlebih mencari aset dengan pasokan terbatas (hard asset).' },
					kesimpulan: 'Awal dari siklus ekspansi pasar aset global (Risk-On environment).'
				};
			}
		}
	});
</script>

<div class="fundamental-lab font-sans">
	<!-- Header Modul Belajar Fundamental -->
	<div class="lab-header">
		<div>
			<div class="flex items-center gap-2 mb-1">
				<span class="oy-tag font-mono">FUNDAMENTAL &amp; MACRO RADAR</span>
				<span class="text-11 text-text-3 font-mono">EDUKASI MEKANIKA PASAR</span>
			</div>
			<h2 class="lab-title">Laboratorium Fundamental Pasar Global</h2>
			<p class="lab-subtitle">
				Memahami <i>mengapa</i> harga bergerak: korelasi antar-aset, likuiditas bank sentral, dan siklus arus modal dunia.
			</p>
		</div>
		<HonestyTag terverifikasi={true} sumber="CFA &amp; BIS Macro Principles" />
	</div>

	<!-- Navigasi Topik Belajar -->
	<div class="topic-nav font-mono">
		<button 
			type="button" 
			class="topic-btn {activeTopic === 'korelasi' ? 'active' : ''}" 
			onclick={() => (activeTopic = 'korelasi')}
		>
			<span>01</span> Segitiga Korelasi (DXY - Yield - Gold)
		</button>
		<button 
			type="button" 
			class="topic-btn {activeTopic === 'skenario' ? 'active' : ''}" 
			onclick={() => (activeTopic = 'skenario')}
		>
			<span>02</span> Simulator Dampak Berita Makro
		</button>
		<button 
			type="button" 
			class="topic-btn {activeTopic === 'makro' ? 'active' : ''}" 
			onclick={() => (activeTopic = 'makro')}
		>
			<span>03</span> 4 Pilar Fundamental Utama
		</button>
		<button 
			type="button" 
			class="topic-btn {activeTopic === 'sesi' ? 'active' : ''}" 
			onclick={() => (activeTopic = 'sesi')}
		>
			<span>04</span> Anatomi 3 Sesi Likuiditas Dunia
		</button>
	</div>

	<!-- KONTEN TOPIK 1: SEGITIGA KORELASI GLOBAL -->
	{#if activeTopic === 'korelasi'}
		<div class="topic-content space-y-4">
			<div class="grid grid-cols-1 md:grid-cols-3 gap-3 font-mono">
				<div class="concept-card">
					<div class="flex items-center justify-between pb-1.5 border-b border-line mb-2">
						<span class="font-bold text-accent text-13">1. DXY (U.S. Dollar Index)</span>
						<span class="text-10 text-text-3">Tolok Ukur Valuta</span>
					</div>
					<p class="font-sans text-12 text-text-2 leading-relaxed">
						Mengukur kekuatan Dolar AS terhadap 6 mata uang utama dunia (Euro, Yen, Pound, dll). 
						Karena komoditas dunia dihargai dalam USD, saat DXY menguat tajam, harga Emas &amp; Minyak menjadi lebih mahal bagi pemegang mata uang lain &rarr; <b>permintaan turun</b>.
					</p>
					<div class="mt-2 pt-2 border-t border-line-soft text-11 text-text-3 font-mono">
						Aturan Dasar: <b class="text-neg">DXY Naik &rarr; Emas &amp; Kripto Cenderung Turun</b>
					</div>
				</div>

				<div class="concept-card">
					<div class="flex items-center justify-between pb-1.5 border-b border-line mb-2">
						<span class="font-bold text-accent text-13">2. US 10Y Yield (Obligasi AS)</span>
						<span class="text-10 text-text-3">Biaya Peluang (Opportunity Cost)</span>
					</div>
					<p class="font-sans text-12 text-text-2 leading-relaxed">
						Imbal hasil obligasi pemerintah AS 10 tahun. Emas adalah aset tanpa bunga (*zero-yield*). 
						Saat yield obligasi naik di atas 4.5%, investor institusi lebih memilih memegang obligasi bebas risiko daripada memegang emas fisik.
					</p>
					<div class="mt-2 pt-2 border-t border-line-soft text-11 text-text-3 font-mono">
						Aturan Dasar: <b class="text-neg">Yield Naik &rarr; Tekanan Jual Emas Meningkat</b>
					</div>
				</div>

				<div class="concept-card">
					<div class="flex items-center justify-between pb-1.5 border-b border-line mb-2">
						<span class="font-bold text-accent text-13">3. Emas (XAUUSD) &amp; Safe Haven</span>
						<span class="text-10 text-text-3">Penyimpan Nilai Hakiki</span>
					</div>
					<p class="font-sans text-12 text-text-2 leading-relaxed">
						Emas adalah uang murni tertua yang tidak dapat dicetak oleh bank sentral mana pun. 
						Emas menguat paling kencang saat: (1) Inflasi riil tinggi, (2) Eskalasi geopolitik / perang, dan (3) Ekspektasi bank sentral memangkas suku bunga.
					</p>
					<div class="mt-2 pt-2 border-t border-line-soft text-11 text-text-3 font-mono">
						Aturan Dasar: <b class="text-pos">Suku Bunga Turun &rarr; Reli Emas Dimulai</b>
					</div>
				</div>
			</div>

			<!-- Peta Alur Hubungan Visual -->
			<div class="p-3.5 rounded bg-surface border border-line">
				<div class="text-12 font-bold text-text mb-2 font-mono flex items-center gap-2">
					<span class="w-2 h-2 rounded-full bg-accent"></span>
					RANGKUMAN CEPAT KORELASI DALAM SATU FORMULA:
				</div>
				<div class="grid grid-cols-1 sm:grid-cols-2 gap-3 text-12 font-sans text-text-2">
					<div class="p-2.5 rounded bg-surface-2 border border-line-soft">
						<b class="text-pos font-mono block mb-1">MODE RISK-ON (Pasar Berani Ambil Risiko):</b>
						Suku bunga rendah, likuiditas melimpah, Dolar melemah. Uang mengalir deras ke saham bertumbuh, Bitcoin, dan komoditas.
					</div>
					<div class="p-2.5 rounded bg-surface-2 border border-line-soft">
						<b class="text-neg font-mono block mb-1">MODE RISK-OFF (Pasar Takut &amp; Mengunci Modal):</b>
						Suku bunga naik, perang, krisis likuiditas. Investor memburu Dolar AS (cash is king) dan instrumen pasar uang berjangka pendek.
					</div>
				</div>
			</div>
		</div>
	{/if}

	<!-- KONTEN TOPIK 2: SIMULATOR SKENARIO DATA EKONOMI -->
	{#if activeTopic === 'skenario'}
		<div class="topic-content space-y-4">
			<div class="p-3 bg-surface border border-line rounded">
				<span class="font-mono text-11 text-accent font-bold block mb-1">SIMULATOR INTERAKTIF</span>
				<p class="text-12 text-text-3 font-sans">
					Pilih rilis berita makro dan hasilnya untuk melihat rantai sebab-akibat fundamental ke DXY, Emas, dan Bitcoin:
				</p>

				<div class="flex flex-wrap items-center gap-3 mt-3 font-mono text-12">
					<div>
						<span class="text-11 text-text-3 block mb-1">1. PILIH PERISTIWA EKONOMI:</span>
						<div class="flex gap-1.5">
							<button type="button" class="chip-btn {selectedNews === 'cpi' ? 'on' : ''}" onclick={() => selectedNews = 'cpi'}>
								US CPI (Inflasi)
							</button>
							<button type="button" class="chip-btn {selectedNews === 'nfp' ? 'on' : ''}" onclick={() => selectedNews = 'nfp'}>
								US NFP (Tenaga Kerja)
							</button>
							<button type="button" class="chip-btn {selectedNews === 'fomc' ? 'on' : ''}" onclick={() => selectedNews = 'fomc'}>
								FOMC (Suku Bunga Fed)
							</button>
						</div>
					</div>

					<div>
						<span class="text-11 text-text-3 block mb-1">2. HASIL AKTUAL:</span>
						<div class="flex gap-1.5">
							<button type="button" class="chip-btn {newsOutcome === 'naik' ? 'on' : ''}" onclick={() => newsOutcome = 'naik'}>
								{selectedNews === 'cpi' ? 'Lebih Tinggi (Panas)' : selectedNews === 'nfp' ? 'Lebih Kuat (Banyak Kerja)' : 'Hawkish / Tahan Bunga'}
							</button>
							<button type="button" class="chip-btn {newsOutcome === 'turun' ? 'on' : ''}" onclick={() => newsOutcome = 'turun'}>
								{selectedNews === 'cpi' ? 'Lebih Rendah (Dingin)' : selectedNews === 'nfp' ? 'Lebih Lemah (Lesu)' : 'Dovish / Pangkas Bunga'}
							</button>
						</div>
					</div>
				</div>
			</div>

			<!-- Hasil Reaksi Fundamental -->
			<div class="sc-result-box">
				<div class="flex items-center justify-between pb-2 border-b border-line mb-3">
					<h3 class="text-14 font-bold text-text font-sans">{skenarioDampak.judul}</h3>
					<span class="text-11 font-mono text-accent">ANALISIS DAMPAK FUNDAMENTAL</span>
				</div>

				<p class="text-12 text-text-2 font-sans mb-3 leading-relaxed">
					<b>Mekanisme Pasar:</b> {skenarioDampak.logika}
				</p>

				<div class="grid grid-cols-1 md:grid-cols-3 gap-3 font-mono text-12 mb-3">
					<div class="p-2.5 rounded bg-surface border border-line">
						<span class="text-10 text-text-3 block">DXY (DOLAR AS)</span>
						<span class="font-bold block my-1 {skenarioDampak.dxy.status.includes('MENGUAT') || skenarioDampak.dxy.status.includes('RELIKAN') ? 'text-pos' : 'text-neg'}">
							{skenarioDampak.dxy.status}
						</span>
						<span class="text-11 text-text-3 font-sans">{skenarioDampak.dxy.ket}</span>
					</div>

					<div class="p-2.5 rounded bg-surface border border-line">
						<span class="text-10 text-text-3 block">EMAS (XAUUSD)</span>
						<span class="font-bold block my-1 {skenarioDampak.gold.status.includes('BULLISH') || skenarioDampak.gold.status.includes('TERBANG') ? 'text-pos' : 'text-neg'}">
							{skenarioDampak.gold.status}
						</span>
						<span class="text-11 text-text-3 font-sans">{skenarioDampak.gold.ket}</span>
					</div>

					<div class="p-2.5 rounded bg-surface border border-line">
						<span class="text-10 text-text-3 block">BITCOIN / KRIPTO</span>
						<span class="font-bold block my-1 {skenarioDampak.btc.status.includes('BULL') ? 'text-pos' : skenarioDampak.btc.status.includes('BEAR') || skenarioDampak.btc.status.includes('DUMP') ? 'text-neg' : 'text-warn'}">
							{skenarioDampak.btc.status}
						</span>
						<span class="text-11 text-text-3 font-sans">{skenarioDampak.btc.ket}</span>
					</div>
				</div>

				<div class="p-2.5 rounded bg-accent/10 border border-accent/25 text-12 text-accent font-sans">
					<b>Pesan untuk Trader:</b> {skenarioDampak.kesimpulan}
				</div>
			</div>
		</div>
	{/if}

	<!-- KONTEN TOPIK 3: 4 PILAR FUNDAMENTAL UTAMA -->
	{#if activeTopic === 'makro'}
		<div class="topic-content grid grid-cols-1 md:grid-cols-2 gap-3 font-sans text-12">
			<div class="concept-card">
				<div class="flex items-center gap-2 mb-2 font-mono text-accent text-13 font-bold border-b border-line pb-1.5">
					<span>Pilar 1:</span> Suku Bunga Acuan (Central Bank Policy Rate)
				</div>
				<p class="text-text-2 leading-relaxed">
					Suku bunga adalah "harga uang". Jika bank sentral menaikkan bunga, meminjam uang menjadi mahal &rarr; konsumsi turun, laba perusahaan berkurang &rarr; pasar saham terkoreksi. Namun bagi valuta, suku bunga tinggi menarik simpanan modal luar negeri (*carry trade*).
				</p>
			</div>

			<div class="concept-card">
				<div class="flex items-center gap-2 mb-2 font-mono text-accent text-13 font-bold border-b border-line pb-1.5">
					<span>Pilar 2:</span> Inflasi (CPI &amp; PCE)
				</div>
				<p class="text-text-2 leading-relaxed">
					Tingkat kenaikan harga barang dan jasa. Target normal bank sentral dunia adalah 2% per tahun. Inflasi di atas 3-4% mengikis daya beli masyarakat, memaksa bank sentral menaikkan suku bunga secara agresif.
				</p>
			</div>

			<div class="concept-card">
				<div class="flex items-center gap-2 mb-2 font-mono text-accent text-13 font-bold border-b border-line pb-1.5">
					<span>Pilar 3:</span> Pertumbuhan Ekonomi (GDP &amp; PMI)
				</div>
				<p class="text-text-2 leading-relaxed">
					PMI (Purchasing Managers' Index) di atas angka 50 menunjukkan sektor manufaktur sedang berekspansi (tumbuh sehat). Di bawah 50 berarti kontraksi (ekonomi lesu &rarr; risiko resesi meningkat).
				</p>
			</div>

			<div class="concept-card">
				<div class="flex items-center gap-2 mb-2 font-mono text-accent text-13 font-bold border-b border-line pb-1.5">
					<span>Pilar 4:</span> Likuiditas Global (M2 Money Supply)
				</div>
				<p class="text-text-2 leading-relaxed">
					Berapa total uang fiat yang beredar di dunia. Ketika jumlah uang beredar (M2) naik pesat (seperti saat stimulus pandemi), harga aset dengan pasokan terbatas (Emas, Bitcoin, Properti) pasti terapresiasi drastis.
				</p>
			</div>
		</div>
	{/if}

	<!-- KONTEN TOPIK 4: ANATOMI 3 SESI LIKUIDITAS DUNIA -->
	{#if activeTopic === 'sesi'}
		<div class="topic-content space-y-3 font-mono text-12">
			<div class="grid grid-cols-1 md:grid-cols-3 gap-3">
				<div class="p-3 rounded bg-surface border border-line">
					<div class="flex justify-between items-center text-accent font-bold mb-1 border-b border-line pb-1">
						<span>SESI ASIA (TOKYO/SYDNEY)</span>
						<span class="text-10 text-text-3">06:00 - 14:00 WIB</span>
					</div>
					<div class="font-sans text-11 text-text-2 space-y-1.5 mt-2">
						<p><b>Karakteristik:</b> Volatilitas rendah, rentang harga sempit (*consolidation range*).</p>
						<p><b>Fungsi:</b> Membentuk level *High* dan *Low* harian awal yang sering kali akan "disapu" (*liquidity sweep*) di sesi berikutnya.</p>
					</div>
				</div>

				<div class="p-3 rounded bg-surface border border-line">
					<div class="flex justify-between items-center text-pos font-bold mb-1 border-b border-line pb-1">
						<span>SESI EROPA (LONDON)</span>
						<span class="text-10 text-text-3">14:00 - 22:00 WIB</span>
					</div>
					<div class="font-sans text-11 text-text-2 space-y-1.5 mt-2">
						<p><b>Karakteristik:</b> Volume meledak, manipulasi pembuka (Judas Swing), penentuan arah tren riil harian.</p>
						<p><b>Fungsi:</b> Sesi terbaik untuk menangkap pola *Break &amp; Retest* pada pasangan mata uang EUR, GBP, dan Emas.</p>
					</div>
				</div>

				<div class="p-3 rounded bg-surface border border-line">
					<div class="flex justify-between items-center text-warn font-bold mb-1 border-b border-line pb-1">
						<span>SESI AMERIKA (NEW YORK)</span>
						<span class="text-10 text-text-3">19:00 - 04:00 WIB</span>
					</div>
					<div class="font-sans text-11 text-text-2 space-y-1.5 mt-2">
						<p><b>Karakteristik:</b> Rilis berita makro AS (CPI, NFP, FOMC) terjadi di sesi ini. Volatilitas puncak dunia.</p>
						<p><b>Golden Window (19:00 - 23:00 WIB):</b> Tumpang tindih London &amp; New York menghasilkan likuiditas terbesar harian.</p>
					</div>
				</div>
			</div>
		</div>
	{/if}
</div>

<style>
	.fundamental-lab {
		background: var(--color-surface);
		border: 1px solid var(--color-line);
		border-radius: 8px;
		padding: 1.25rem;
		margin-block: 1rem 1.5rem;
	}
	.lab-header {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
		border-bottom: 1px solid var(--color-line);
		padding-bottom: 0.85rem;
		margin-bottom: 1rem;
	}
	@media (min-width: 768px) {
		.lab-header {
			flex-direction: row;
			align-items: center;
			justify-content: space-between;
		}
	}
	.oy-tag {
		font-size: 9.5px;
		font-weight: 700;
		color: var(--color-accent);
		letter-spacing: 0.08em;
	}
	.lab-title {
		font-size: 18px;
		font-weight: 700;
		color: var(--color-text);
		margin: 0;
	}
	.lab-subtitle {
		font-size: 13px;
		color: var(--color-text-2);
		margin: 0.25rem 0 0;
	}
	.topic-nav {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
		margin-bottom: 1.15rem;
	}
	.topic-btn {
		font-size: 11.5px;
		font-weight: 500;
		padding: 0.45rem 0.75rem;
		border-radius: 6px;
		background: var(--color-surface-2);
		color: var(--color-text-3);
		border: 1px solid var(--color-line);
		display: inline-flex;
		align-items: center;
		gap: 0.45rem;
		transition: all 120ms ease-out;
	}
	.topic-btn span {
		opacity: 0.6;
		font-size: 10px;
	}
	.topic-btn:hover {
		color: var(--color-text);
		border-color: var(--color-line-soft);
	}
	.topic-btn.active {
		background: var(--color-accent);
		color: var(--color-on-accent);
		border-color: var(--color-accent);
		font-weight: 700;
	}
	.topic-btn.active span {
		color: var(--color-on-accent);
		opacity: 0.8;
	}
	.concept-card {
		background: var(--color-surface-2);
		border: 1px solid var(--color-line);
		border-radius: 6px;
		padding: 0.95rem;
	}
	.chip-btn {
		font-size: 11px;
		padding: 0.35rem 0.65rem;
		border-radius: 4px;
		background: var(--color-surface-2);
		color: var(--color-text-2);
		border: 1px solid var(--color-line);
		transition: all 120ms;
	}
	.chip-btn.on {
		background: var(--color-accent);
		color: var(--color-on-accent);
		border-color: var(--color-accent);
		font-weight: 700;
	}
	.sc-result-box {
		background: var(--color-surface-2);
		border: 1px solid var(--color-line);
		border-radius: 6px;
		padding: 1rem;
	}
</style>
