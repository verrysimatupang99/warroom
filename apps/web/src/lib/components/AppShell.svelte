<script lang="ts">
	// Kerangka aplikasi — rombak total (6 Okt 2026).
	//
	// Struktur BARU: TopBar tipis (sticky) → NavBar horizontal (sticky) → konten
	// terpusat (max-width). Rail kiri 240px DIHAPUS: ia memakan lebar untuk 7 tautan
	// dan memaksa tata letak berbeda antara Home dan halaman area. Bottom-nav mobile
	// tetap ada (pola ponsel yang benar), tapi kini hanya < md.
	import type { Snippet } from 'svelte';
	import { page } from '$app/state';
	import { live } from '$lib/api/live.svelte';
	import TopBar from './TopBar.svelte';
	import NavBar from './NavBar.svelte';
	import BottomNav from './BottomNav.svelte';

	let { children }: { children: Snippet } = $props();
	const jalur = $derived(page.url.pathname);

	$effect(() => {
		live.mulai();
		return () => live.hentikan();
	});
</script>

<a
	href="#konten"
	class="sr-only transisi focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-50 focus:rounded-control focus:border focus:border-accent focus:bg-surface focus:px-3 focus:py-2 focus:text-13"
>
	Lompat ke konten
</a>

<TopBar />
<NavBar />

<!-- data-app-siap: penanda bahwa aplikasi HIDUP (hydration selesai). Dipakai e2e untuk
     menunggu interaksi benar-benar siap — insiden 7 Okt: klik sebelum listener terpasang
     hilang diam-diam sehingga tes flaky (dan shell sempat menutupi halaman). -->
<main id="konten" class="konten" data-app-siap tabindex="-1">{@render children()}</main>

<BottomNav {jalur} />

<style>
	.konten {
		max-width: 76rem;
		margin: 0 auto;
		padding: 1rem 1rem 6rem;
	}
	@media (min-width: 768px) {
		.konten {
			padding: 1.25rem 1.5rem 3rem;
		}
	}
</style>
