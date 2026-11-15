<script lang="ts">
	import PageHeader from '$lib/components/PageHeader.svelte';
	// Cara kerja — padanan /system algentis. Menjelaskan aliran War Room apa adanya,
	// bukan aspirasi: alur yang benar-benar jalan (domain → worker → API → web).
	// Ditulis dari kode, bukan dari rencana.
	const alur = [
		{
			n: 1,
			judul: 'Domain mengumpulkan',
			isi: 'Kolektor mengambil data dari sumber: bursa kripto, TradingView & arsip tick (IDX), ForexFactory (kalender), RSS (berita), Polymarket, GMGN. Setiap sumber punya cache + TTL sendiri.',
			label: 'packages/live-trading'
		},
		{
			n: 2,
			judul: 'Worker menerbitkan fakta',
			isi: 'Job runner menulis hasil ke tabel `facts`, append-only, tiap baris membawa sumber, waktu, dan TTL. Bila sebuah sub-bagian hilang, snapshot ditandai "separuh" dan alert dikirim, bukan diterbitkan sebagai "ok".',
			label: 'services/worker'
		},
		{
			n: 3,
			judul: 'API membaca fakta',
			isi: 'FastAPI menyajikan fakta lewat REST + SSE. Auth cookie + peran (owner/operator/viewer). API tidak menghitung ulang domain, ia membaca apa yang sudah dihitung.',
			label: 'services/api'
		},
		{
			n: 4,
			judul: 'Web menampilkan',
			isi: 'UI merender fakta. Tidak ada perhitungan di UI: angka kosong tampil "—" (bukan 0), dan angka yang belum lolos split beku wajib membawa catatan kejujurannya.',
			label: 'apps/web'
		}
	];

	const metode = [
		{
			pasar: 'Crypto',
			sumber: 'OKX Publik',
			strategi: 'Paper Momentum 65 Koin + Kalkulasi Lokal',
			isi: 'Paper trader momentum berjalan di 65 koin likuid OKX (breakout 55 bar), dilengkapi inspeksi lokal ATR-14, EMA-20, RSI-14, dan Swing Range pada 485+ pair OKX.',
			bukti: 'State paper trader momentum_paper.json + ledger eksekusi R. Tanpa klaim SMC eksternal karena node lama tidak dipakai.'
		},
		{
			pasar: 'Memecoin',
			sumber: 'GMGN / FOMO',
			strategi: 'Flow + safety gate',
			isi: 'Pindai token baru multi-chain (sol, bsc, base, eth, robinhood, arc, stable). Saring: bundler ≤ 0,25 · dev hold ≤ 0,05 · entrapment ≤ 0,95 · likuiditas ≥ $100k · mcap ≥ $500k · skor ≥ 60. Profil masuk "flow", TP +100% jual 50% / +300% jual 100%, posisi $6, maks 8 terbuka.',
			bukti: 'Bot paper menulis signals.jsonl + positions.json (jujur bila berkas rusak). Profil pembanding: base_tp100/300_sl65, fast_tp50/150_sl35, tight_tp40/sl25.'
		},
		{
			pasar: 'LP Solana',
			sumber: 'Meteora (DLMM / DAMM v2)',
			strategi: 'LP terukur: fee vs IL',
			isi: 'Pilih pool, catat V/L awal, tandai fee/hari, lalu nilai ulang tiap siklus: bila IL tumbuh lebih dalam daripada fee → verdict KELUAR (contoh nyata: IL -5,94% pada V/L 4,83 → 0,76).',
			bukti: 'Mark lokal per alamat pool (DexScreener) + verifikasi 3 sumber. Rekonsiliasi on-chain BELUM ada, dinyatakan apa adanya.'
		},
		{
			pasar: 'LP Robinhood Chain',
			sumber: 'Uniswap v2/v3/v4 (L2, chain 4663)',
			strategi: 'Pantau, belum ada posisi',
			isi: 'Kumpulkan pool Stock Token + pool aktif, verifikasi harga, siapkan tempat bila kandidat layak. Belum ada posisi paper.',
			bukti: 'lp_verifikasi (contoh TSLA/WETH: baru 1 sumber, status SEBAGIAN).'
		},
		{
			pasar: 'IDX',
			sumber: 'Stock Arjum',
			strategi: 'Bandarmologi · BSJP · ARA Hunter (berdiri sendiri)',
			isi: 'Dua hal berbeda, bukan turunan. (1) Bandarmologi = cara baca: aliran broker (ATS, frekuensi, no-sell) → skor 0–100 per emiten. (2) Strategi = aturan beli/jual yang diuji sendiri, terpisah dari cara baca: BSJP (beli sore, jual pagi), ARA Hunter, INTRADAY, MOMENTUM, BREAKOUT, REVERSAL, SWING.',
			bukti: 'Ledger mesin (616+ trade) dengan grader v3; hanya trade TUNTAS masuk metrik.'
		},
		{
			pasar: 'Forex',
			sumber: 'MT5 Bridge Exness + Yahoo Finance',
			strategi: 'GOLD_Reaper_Hexa v3.0 & BTC_Reaper_Hexa v2.0 (Live)',
			isi: 'Tiga terminal MT5 Exness Cent & Standard mengirim telemetri live (saldo, ekuitas, floating, posisi terbuka, riwayat deal) ke War Room setiap detik, digabung dengan level teknikal Yahoo Finance & kalender makro.',
			bukti: 'Rekonsiliasi live MT5 Multi-EA + ledger eksekusi Cent (USC) dan Standard (USD) tercatat apa adanya.'
		},
		{
			pasar: 'Polymarket',
			sumber: 'poly-agent + favorite-live-verdict',
			strategi: '4-Arm Paper Mirror + AI Agent Harness',
			isi: 'Memantau window biner BTC & ETH 5m dalam 4 eksperimen paper (Arm D Favorit 0,70–0,95, Arm B Kandidat, Arm A Shadow, Arm C Fade) serta penilaian skor poly-agent; eksekusi live CLOB ditangguhkan sementara.',
			bukti: 'Verdict statistik Wilson 95% CI vs break-even + jejak keputusan agent-events.jsonl dan pembelajaran otomatis.'
		}
	];

	const prinsip = [
		{ t: 'Jujur mengalahkan terlihat bagus', d: 'Angka yang belum pasti terlihat belum pasti. "76,25%" yang belum terverifikasi wajib berbeda dari yang terukur.' },
		{ t: 'Kosong itu jawaban', d: '"Tidak ada sinyal" adalah informasi, bukan kegagalan render. Alasan kosongnya ditampilkan; tidak diisi nol.' },
		{ t: 'Satu keputusan per pasar', d: 'Home menjawab "mana yang layak?" dulu. Rincian menyusul, tidak ditumpuk di depan.' },
		{ t: 'Paper dan live jalur yang sama', d: 'Paper dan live melewati jalur keputusan yang sama; yang berbeda hanya sakelar eksekusi.' },
		{ t: 'UI tidak menambah beban API', d: 'Menampilkan lebih banyak bukan alasan memanggil lebih banyak.' }
	];
</script>

<svelte:head><title>Cara kerja, War Room</title></svelte:head>

<div class="space-y-4">
	<PageHeader
		eyebrow="DOKUMEN / CARA-KERJA"
		title="Cara Kerja"
		tag="arsitektur"
		terverifikasi={true}
		sumber="fakta & kode produksi"
		alasan="dokumentasi arsitektur nyata"
		description="Aliran yang benar-benar jalan, bukan rencana. Angka hanya dari tabel fakta."
	/>

	<section class="kartu">
		<h2 class="judul">Aliran</h2>
		<ol class="alur">
			{#each alur as a (a.n)}
				<li>
					<span class="n angka">{a.n}</span>
					<div>
						<h3>{a.judul}</h3>
						<p>{a.isi}</p>
						<code>{a.label}</code>
					</div>
				</li>
			{/each}
		</ol>
	</section>

	<section class="kartu">
		<h2 class="judul">Prinsip yang mengikat</h2>
		<dl class="prinsip">
			{#each prinsip as p (p.t)}
				<div>
					<dt>{p.t}</dt>
					<dd>{p.d}</dd>
				</div>
			{/each}
		</dl>
	</section>

	<section class="kartu">
		<h2 class="judul">Metode &amp; strategi per pasar</h2>
		<p class="catatan">
			Ini jawaban atas "strategi atau metode yang sudah gw sebutkan": semuanya ditulis dari
			kode yang benar-benar jalan, bukan daftar cita-cita. Hasilnya ada di halaman tiap pasar.
		</p>
		<div class="metode">
			{#each metode as m (m.pasar)}
				<article class="m">
					<header>
						<h3>{m.pasar}</h3>
						<span class="sumber">{m.sumber}</span>
					</header>
					<p class="strategi">{m.strategi}</p>
					<p>{m.isi}</p>
					<p class="bukti"><b>Buktinya:</b> {m.bukti}</p>
				</article>
			{/each}
		</div>
	</section>

	<section class="kartu">
		<h2 class="judul">Batas yang jujur</h2>
		<ul class="batas">
			<li><b>Snapshot, bukan realtime.</b> Data bisa setua satu siklus; kesegarannya dinyatakan, tidak dipura-pura hidup.</li>
			<li><b>Live belum menyala.</b> Semua eksekusi berjalan mode paper. Live butuh dana terverifikasi + keputusan pemilik.</li>
			<li><b>Belum ada split beku.</b> Selama itu belum ada, tidak ada angka yang boleh disebut "edge terbukti".</li>
			<li><b>Kuota API nyata.</b> Arjum 6.003/hari; UI tidak menambah panggilan yang tidak perlu.</li>
		</ul>
	</section>
</div>

<style>
	.kartu {
		background: var(--color-surface);
		border: 1px solid var(--color-line);
		border-radius: var(--radius-card);
		padding: var(--card-pad);
	}
	/* Perapihan dokumen (DESIGN-USULAN 16 Okt): judul bagian = eyebrow mono
	   uppercase dengan tracking lebar — terbaca sebagai label struktur. */
	.judul {
		margin: 0 0 0.7rem;
		font-family: var(--font-mono);
		font-size: 0.8rem;
		font-weight: 700;
		letter-spacing: 0.12em;
		text-transform: uppercase;
		color: var(--color-text-3);
	}
	.alur {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}
	.alur li {
		display: grid;
		grid-template-columns: 2rem 1fr;
		gap: 0.75rem;
		align-items: start;
	}
	.n {
		display: grid;
		place-items: center;
		width: 2rem;
		height: 2rem;
		border-radius: 999px;
		background: color-mix(in srgb, var(--color-accent) 14%, transparent);
		color: var(--color-accent);
		font-weight: 700;
		font-size: var(--text-14);
	}
	.alur h3 {
		margin: 0;
		font-size: var(--text-14);
		font-weight: 600;
	}
	.alur p {
		margin: 0.2rem 0 0.3rem;
		font-size: var(--text-13);
		color: var(--color-text-2);
		line-height: 1.55;
	}
	.alur code {
		font-family: var(--font-mono);
		font-size: var(--text-11);
		color: var(--color-text-3);
		background: var(--color-canvas);
		padding: 0.1rem 0.35rem;
		border-radius: 4px;
	}
	.catatan {
		margin: 0 0 0.7rem;
		font-size: var(--text-12);
		color: var(--color-text-3);
	}
	.metode {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(17rem, 1fr));
		gap: 0.7rem;
	}
	.m {
		border: 1px solid var(--color-line);
		border-radius: var(--radius-control, 0.6rem);
		padding: 0.7rem 0.8rem;
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
		font-size: var(--text-12);
	}
	.m header {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: 0.5rem;
	}
	.m h3 {
		margin: 0;
		font-size: var(--text-13);
	}
	.m .sumber {
		font-size: var(--text-10, 0.65rem);
		color: var(--color-text-3);
		border: 1px solid var(--color-line);
		border-radius: 999px;
		padding: 0 0.45rem;
		white-space: nowrap;
	}
	.m .strategi {
		margin: 0;
		font-weight: 600;
		color: var(--color-accent);
	}
	.m p {
		margin: 0;
		color: var(--color-text-2, var(--color-text));
	}
	.m .bukti {
		color: var(--color-text-3);
	}
	.prinsip {
		margin: 0;
		display: flex;
		flex-direction: column;
		gap: 0.6rem;
	}
	.prinsip dt {
		font-weight: 600;
		font-size: var(--text-14);
	}
	.prinsip dd {
		margin: 0.15rem 0 0;
		font-size: var(--text-13);
		color: var(--color-text-2);
		line-height: 1.55;
	}
	.batas {
		margin: 0;
		padding-left: 1.1rem;
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
		font-size: var(--text-13);
		color: var(--color-text-2);
		line-height: 1.55;
	}
	.batas b {
		color: var(--color-text);
	}
	.angka {
		font-family: var(--font-mono);
		font-variant-numeric: tabular-nums;
	}
</style>
