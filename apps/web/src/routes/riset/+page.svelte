<script lang="ts">
	import { page } from '$app/state';
	import { AREAS, SLUG_LAMA } from '$lib/nav';
	import MarketShell from '$lib/components/MarketShell.svelte';
	import QuantStrategyCard from '$lib/components/QuantStrategyCard.svelte';
	import MakroKalender from '$lib/components/market/MakroKalender.svelte';
	import PapanPeringkat from '$lib/components/market/PapanPeringkat.svelte';

	const area = AREAS.find((a) => a.kunci === 'riset')!;
	const sub = $derived.by(() => {
		const s = page.url.searchParams.get('sub') ?? 'kinerja';
		return SLUG_LAMA[s] ?? s;
	});
</script>

<svelte:head><title>Riset | War Room</title></svelte:head>

<MarketShell
	{area}
	aktif={sub}
	judul="Riset"
	deskripsi="Hasil uji strategi. Setiap angka wajib disertai jumlah trade dan periode, karena PF dari sampel kecil tidak berarti."
	sumber="pasar/quant-backtest"
>
	{#if sub === 'kinerja'}
		<QuantStrategyCard filter="all" />
	{:else if sub === 'bukti'}
		<div class="space-y-3">
			<QuantStrategyCard filter="forex" />
			<p class="text-11 text-text-3">
				Bukti per market aktif. Laporan lengkap tersimpan di repo laptop; angka di halaman ini
				adalah ringkasan yang disimpan server.
			</p>
		</div>
	{:else if sub === 'leaderboard'}
		<PapanPeringkat />
	{:else if sub === 'kalender'}
		<MakroKalender />
	{:else}
		<QuantStrategyCard filter="all" />
	{/if}
</MarketShell>
