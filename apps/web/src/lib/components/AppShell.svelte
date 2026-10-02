<script lang="ts">
	// Kerangka aplikasi: rail (desktop) + bottom tab (mobile), SSE dikelola di sini sekali.
	import type { Snippet } from 'svelte';
	import { page } from '$app/state';
	import { live } from '$lib/api/live.svelte';
	import RailNav from './RailNav.svelte';
	import BottomNav from './BottomNav.svelte';
	import TopBar from './TopBar.svelte';

	let { children }: { children: Snippet } = $props();
	const jalur = $derived(page.url.pathname);

	$effect(() => {
		live.mulai();
		return () => live.hentikan();
	});
</script>

<a
	href="#konten"
	class="sr-only transisi focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-50 focus:rounded-control focus:border focus:border-accent-2 focus:bg-surface focus:px-3 focus:py-2 focus:text-13"
>
	Lompat ke konten
</a>

<div class="min-h-screen md:grid md:grid-cols-[15rem_1fr]">
	<aside
		class="sticky top-0 hidden h-screen overflow-auto border-r border-line bg-bg-2 md:block"
	>
		<div class="border-b border-line p-3">
			<p class="text-15 text-text">War Room</p>
			<p class="label-mikro">satu layar · 7 area</p>
		</div>
		<RailNav {jalur} />
	</aside>

	<div class="min-w-0">
		<TopBar {jalur} />
		<main id="konten" class="p-3 pb-28 md:pb-8" tabindex="-1">{@render children()}</main>
	</div>
</div>

<BottomNav {jalur} />