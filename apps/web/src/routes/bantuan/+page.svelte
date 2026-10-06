<script lang="ts">
	// Bantuan — padanan /faq algentis, ditulis dari produk kita sendiri.
	// Setiap jawaban mengacu ke perilaku nyata (bukan janji). Pertanyaan yang
	// jawabannya "belum ada" ditulis apa adanya, bukan dijawab seolah sudah ada.
	const tanya: { q: string; a: string; status?: 'ada' | 'belum' }[] = [
		{
			q: 'Kenapa angka pasar yang kosong tampil "—", bukan 0?',
			a: 'Karena 0 adalah angka, dan "tidak ada" bukan. Menampilkan 0 untuk data yang tidak ada membuat pasar terlihat punya nilai padahal tidak. Setiap "—" disertai alasan kosongnya.',
			status: 'ada'
		},
		{
			q: 'Apa arti "BELUM TERVERIFIKASI" di kartu sinyal?',
			a: 'Artinya angka itu belum lolos split beku — jadi ia klaim eksplorasi, bukan edge terbukti. Sistem menolak menampilkan skor sebagai "terbukti" selama belum dihitung ulang di repo ini.',
			status: 'ada'
		},
		{
			q: 'Di mana saya lihat harga masuk, stop, dan target?',
			a: 'Di Home: verdikt besar menampilkan "Setup entry" (masuk/stop/target/risiko) untuk pasar teratas, dan tiap baris pasar punya setup ringkasnya sendiri. Yang belum punya sinyal tidak menampilkan setup — karena memang tidak ada.',
			status: 'ada'
		},
		{
			q: 'Apakah ini sudah trading dengan uang nyata?',
			a: 'Belum. Semua eksekusi berjalan mode paper. Live butuh tiga hal yang belum ada: dana terverifikasi, RPC on-chain, dan keputusan pemilik. Selama itu belum, gate menolak.',
			status: 'ada'
		},
		{
			q: 'Kenapa data bisa terasa "tidak hidup"?',
			a: 'Sistem bekerja dengan snapshot, bukan realtime. Snapshot ditulis tiap siklus (~15 menit); UI menyatakan umurnya daripada berpura-pura hidup. Aliran SSE di bar atas menunjukkan koneksi.',
			status: 'ada'
		},
		{
			q: 'Dari mana asal berita dan kalender?',
			a: 'Berita dari RSS publik (Cointelegraph, Decrypt) — hanya judul + tautan, ringkasan tidak disalin. Kalender dari ForexFactory (JSON publik). Keduanya tanpa API key, jadi tidak menambah kuota.',
			status: 'ada'
		},
		{
			q: 'Kalau kuota API habis, apa yang terjadi?',
			a: 'Kolektor berhenti sebelum memanggil (guard kuota), dan UI menampilkan data cache terakhir beserta umurnya. Yang tidak dilakukan: menampilkan angka lama seolah baru.',
			status: 'ada'
		},
		{
			q: 'Apakah saya bisa ekspor data?',
			a: 'Ya — tabel di halaman Sistem dan Riset punya tombol Ekspor CSV.',
			status: 'ada'
		},
		{
			q: 'Kenapa hanya satu tema (gelap)?',
			a: 'Pilihan pemilik. Dua tema berarti dua sistem yang harus dijaga konsisten; satu tema berarti satu kebenaran. Tema terang dihapus, bukan disembunyikan.',
			status: 'ada'
		},
		{
			q: 'Bagaimana menambah pasar baru?',
			a: 'Belum ada jalur UI untuk itu. Pasar didefinisikan di kode (kolektor + entri nav); menambah pasar berarti menambah kolektor, bukan sekadar konfigurasi.',
			status: 'belum'
		}
	];

	let buka = $state<number | null>(0);
</script>

<svelte:head><title>Bantuan — War Room</title></svelte:head>

<div class="bantuan">
	<header class="kepala">
		<h1>Bantuan</h1>
		<p class="dim">Jawaban dari perilaku nyata sistem. Yang belum ada ditulis belum ada.</p>
	</header>

	<ul class="daftar">
		{#each tanya as t, i (t.q)}
			<li>
				<button
					type="button"
					class="tanya"
					aria-expanded={buka === i}
					onclick={() => (buka = buka === i ? null : i)}
				>
					<span>{t.q}</span>
					<span class="tanda" aria-hidden="true">{buka === i ? '−' : '+'}</span>
				</button>
				{#if buka === i}
					<p class="jawab">
						{t.a}
						{#if t.status === 'belum'}
							<span class="belum">Belum tersedia — bukan sesuatu yang bisa dilakukan sekarang.</span>
						{/if}
					</p>
				{/if}
			</li>
		{/each}
	</ul>

	<section class="kartu">
		<h2>Masih bingung?</h2>
		<p>
			Catatan teknis lengkap ada di <a href="/catatan">Catatan</a>. Untuk pertanyaan yang
			jawabannya belum ada di sini, tanyakan langsung lewat Telegram.
		</p>
	</section>
</div>

<style>
	.bantuan {
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
	.daftar {
		list-style: none;
		margin: 0;
		padding: 0;
		background: var(--color-surface);
		border: 1px solid var(--color-line);
		border-radius: var(--radius-card);
		overflow: hidden;
	}
	.daftar li {
		border-bottom: 1px solid var(--color-line-soft);
	}
	.daftar li:last-child {
		border-bottom: 0;
	}
	.tanya {
		width: 100%;
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 1rem;
		background: none;
		border: 0;
		padding: 0.7rem 0.9rem;
		text-align: left;
		font-size: var(--text-14);
		font-weight: 500;
		color: var(--color-text);
		transition: background-color 160ms var(--ease-out);
	}
	.tanya:hover {
		background: var(--color-surface-2);
	}
	.tanda {
		color: var(--color-accent);
		font-family: var(--font-mono);
		font-size: var(--text-16);
		flex: none;
	}
	.jawab {
		margin: 0;
		padding: 0 0.9rem 0.8rem;
		font-size: var(--text-13);
		line-height: 1.6;
		color: var(--color-text-2);
	}
	.belum {
		display: block;
		margin-top: 0.35rem;
		color: var(--color-warn);
		font-size: var(--text-12);
	}
	.kartu {
		background: var(--color-surface);
		border: 1px solid var(--color-line);
		border-radius: var(--radius-card);
		padding: var(--card-pad);
	}
	.kartu h2 {
		margin: 0 0 0.35rem;
		font-size: var(--text-14);
		font-weight: 700;
	}
	.kartu p {
		margin: 0;
		font-size: var(--text-13);
		color: var(--color-text-2);
		line-height: 1.6;
	}
	.kartu a {
		color: var(--color-accent);
	}
	.dim {
		color: var(--color-text-3);
		font-weight: 400;
	}
</style>
