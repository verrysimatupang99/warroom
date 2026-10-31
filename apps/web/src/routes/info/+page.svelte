<script lang="ts">
	import { page } from '$app/state';
	import { AREAS, SLUG_LAMA } from '$lib/nav';
	import MarketShell from '$lib/components/MarketShell.svelte';
	import CatatanView from '$lib/components/info/CatatanView.svelte';
	import BeritaView from '$lib/components/info/BeritaView.svelte';
	import CaraKerjaView from '$lib/components/info/CaraKerjaView.svelte';
	import BantuanView from '$lib/components/info/BantuanView.svelte';

	const area = AREAS.find((a) => a.kunci === 'info')!;
	const sub = $derived.by(() => {
		const s = page.url.searchParams.get('sub') ?? 'catatan';
		return SLUG_LAMA[s] ?? s;
	});
</script>

<svelte:head><title>Info | War Room</title></svelte:head>

<MarketShell {area} aktif={sub} tanpaKepala={true}>
	{#if sub === 'catatan'}
		<CatatanView />
	{:else if sub === 'berita'}
		<BeritaView />
	{:else if sub === 'cara-kerja'}
		<CaraKerjaView />
	{:else if sub === 'bantuan'}
		<BantuanView />
	{:else}
		<CatatanView />
	{/if}
</MarketShell>
