<script lang="ts">
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
			isi: 'Job runner menulis hasil ke tabel `facts` — append-only, tiap baris membawa sumber, waktu, dan TTL. Bila sebuah sub-bagian hilang, snapshot ditandai "separuh" dan alert dikirim, bukan diterbitkan sebagai "ok".',
			label: 'services/worker'
		},
		{
			n: 3,
			judul: 'API membaca fakta',
			isi: 'FastAPI menyajikan fakta lewat REST + SSE. Auth cookie + peran (owner/operator/viewer). API tidak menghitung ulang domain — ia membaca apa yang sudah dihitung.',
			label: 'services/api'
		},
		{
			n: 4,
			judul: 'Web menampilkan',
			isi: 'UI merender fakta. Tidak ada perhitungan di UI: angka kosong tampil "—" (bukan 0), dan angka yang belum lolos split beku wajib membawa catatan kejujurannya.',
			label: 'apps/web'
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

<svelte:head><title>Cara kerja — War Room</title></svelte:head>

<div class="cara">
	<header class="kepala">
		<h1>Cara kerja</h1>
		<p class="dim">Aliran yang benar-benar jalan, bukan rencana. Angka hanya dari tabel fakta.</p>
	</header>

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
	.cara {
		display: flex;
		flex-direction: column;
		gap: var(--grid-gap);
	}
	.kepala h1 {
		margin: 0;
		font-family: var(--font-display);
		font-size: var(--text-26);
		font-weight: 700;
		letter-spacing: -0.02em;
	}
	.kepala p {
		margin: 0.15rem 0 0;
		font-size: var(--text-13);
	}
	.kartu {
		background: var(--color-surface);
		border: 1px solid var(--color-line);
		border-radius: var(--radius-card);
		padding: var(--card-pad);
	}
	.judul {
		margin: 0 0 0.7rem;
		font-size: var(--text-14);
		font-weight: 700;
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
	.dim {
		color: var(--color-text-3);
		font-weight: 400;
	}
	.angka {
		font-family: var(--font-mono);
		font-variant-numeric: tabular-nums;
	}
</style>
