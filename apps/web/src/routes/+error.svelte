<script lang="ts">
	// Halaman galat rute. Temuan QA 15 Okt (Low): 404 dulu "Not Found" polos —
	// judul tab generik dan tanpa tautan kembali. Status HTTP tetap dari SvelteKit.
	import { page } from '$app/state';
	import Ikon from '$lib/components/Ikon.svelte';
</script>

<svelte:head>
	<title>{page.status} · War Room</title>
</svelte:head>

<div class="mx-auto mt-20 w-full max-w-md text-center" data-testid="halaman-galat">
	<div class="text-45 font-bold text-text-3 font-mono">{page.status}</div>
	<h1 class="mt-2 text-19 text-text">{page.status === 404 ? 'Halaman tidak ditemukan' : 'Terjadi galat'}</h1>
	<p class="mt-2 text-13 text-text-3">
		{page.status === 404
			? 'Rute ini tidak ada di War Room. Alamat mungkin salah atau halamannya dipindah.'
			: (page.error?.message ?? 'Galat tak terduga.')}
	</p>
	<a
		class="target-44 mt-5 inline-flex items-center gap-2 rounded-control border border-line bg-surface px-4 text-13 text-text hover:border-accent-2"
		href="/"
	>
		<Ikon nama="home" ukuran={14} />
		kembali ke Home
	</a>
</div>
