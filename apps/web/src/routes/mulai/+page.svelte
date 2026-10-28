<script lang="ts">
	// Halaman publik: satu-satunya halaman yang bisa dibaca tanpa sesi.
	// Sengaja tanpa angka yang diambil dari API — pengunjung tanpa kredensial tidak
	// boleh melihat posisi, ekuitas, atau sinyal. Yang tampil hanya penjelasan.
	import { urlApi } from '$lib/api/client';
	import { onMount } from 'svelte';

	let build = $state<string>('');

	onMount(() => {
		fetch(urlApi('/api/v1/health'))
			.then((r) => r.json())
			.then((d) => (build = d?.build ?? ''))
			.catch(() => null);
	});

	const KERJA = [
		{
			judul: 'Membaca pasar',
			isi: 'Crypto dipindai dari MEXC, emas dan indeks dari sumber publik dan telemetri MT5. Tiap angka menyebut sumbernya.'
		},
		{
			judul: 'Menolak setup lemah',
			isi: 'Sinyal harus lolos gerbang probabilitas, tren, sesi, dan spread. Kalau tidak lolos, War Room diam dan mencatat alasannya.'
		},
		{
			judul: 'Mencatat eksekusi',
			isi: 'Setiap keputusan dan setiap fill dicatat di jurnal. Selisih antara sinyal dan harga eksekusi ikut dicatat, bukan disembunyikan.'
		}
	];

	const BATAS = [
		'Ini alat kerja pribadi, bukan layanan berlangganan dan bukan nasihat keuangan.',
		'Sebagian besar angka di dalamnya hasil paper trading, bukan uang nyata.',
		'Uji backtest memakai data OHLC; hasil real tick bisa lebih buruk.',
		'Kalau satu sumber data mati, halaman terkait akan kosong dan menyebut sebabnya.'
	];
</script>

<svelte:head>
	<title>War Room — satu jalur, tiga gerbang</title>
	<meta name="description" content="War Room adalah ruang kerja trading yang memutuskan apakah ada setup layak dieksekusi, atau diam." />
</svelte:head>

<div class="min-h-dvh bg-bg text-text">
	<header class="mx-auto flex max-w-3xl items-center justify-between px-4 py-5">
		<span class="font-mono text-12 font-bold tracking-tight">WAR ROOM</span>
		<a href="/masuk" class="rounded-control border border-line px-3 py-2 text-12 text-text-2 hover:border-accent hover:text-accent">
			Masuk
		</a>
	</header>

	<main class="mx-auto max-w-3xl px-4 pb-16">
		<p class="font-mono text-10 uppercase tracking-widest text-text-3">Ruang kerja trading</p>
		<h1 class="mt-2 text-24 font-bold leading-tight sm:text-32">Satu jalur, tiga gerbang.</h1>
		<p class="mt-3 max-w-2xl text-14 leading-relaxed text-text-2">
			War Room tidak menjanjikan sinyal. Ia memutuskan apakah ada setup yang layak dieksekusi
			hari ini. Kalau tidak ada yang lolos gerbang, ia diam — dan diam itu tercatat.
		</p>

		<div class="mt-8 grid gap-3 sm:grid-cols-3">
			{#each KERJA as k (k.judul)}
				<section class="rounded-card border border-line bg-surface p-4">
					<h2 class="text-13 font-bold text-text">{k.judul}</h2>
					<p class="mt-1.5 text-12 leading-relaxed text-text-2">{k.isi}</p>
				</section>
			{/each}
		</div>

		<section class="mt-8 rounded-card border border-line bg-surface p-4">
			<h2 class="text-13 font-bold text-text">Tiga gerbang sebelum order</h2>
			<ol class="mt-2 space-y-2 text-12 leading-relaxed text-text-2">
				<li><span class="font-mono text-text-3">01</span> · Gerbang data. Sumber harus segar; data basi membatalkan keputusan.</li>
				<li><span class="font-mono text-text-3">02</span> · Gerbang setup. Probabilitas harus melewati ambang, arah harus sejalan tren.</li>
				<li><span class="font-mono text-text-3">03</span> · Gerbang biaya. Spread harus kecil dibanding jarak stop.</li>
			</ol>
		</section>

		<section class="mt-4 rounded-card border border-line bg-surface p-4">
			<h2 class="text-13 font-bold text-text">Batas jujur</h2>
			<ul class="mt-2 space-y-1.5 text-12 leading-relaxed text-text-2">
				{#each BATAS as b (b)}
					<li class="flex gap-2"><span class="font-mono text-text-3">·</span><span>{b}</span></li>
				{/each}
			</ul>
		</section>

		<div class="mt-8 flex flex-wrap items-center gap-3">
			<a href="/masuk" class="rounded-control bg-accent px-4 py-2.5 text-13 font-bold text-bg hover:opacity-90">
				Masuk ke War Room
			</a>
			{#if build}
				<span class="font-mono text-10 text-text-3">build {build}</span>
			{/if}
		</div>

		<footer class="mt-10 border-t border-line pt-4 text-11 leading-relaxed text-text-3">
			Bukan nasihat keuangan. Trading membawa risiko kehilangan modal. Angka historis tidak menjamin hasil.
		</footer>
	</main>
</div>
