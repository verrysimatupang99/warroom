<script lang="ts">
	import { page } from '$app/state';
	import { AREAS, SLUG_LAMA } from '$lib/nav';
	import MarketShell from '$lib/components/MarketShell.svelte';
	import ForexCockpitExness from '$lib/components/ForexCockpitExness.svelte';
	import ForexSinyal from '$lib/components/market/ForexSinyal.svelte';
	import ForexAlat from '$lib/components/market/ForexAlat.svelte';
	import PasarUji from '$lib/components/market/PasarUji.svelte';
	import JournalPanel from '$lib/components/JournalPanel.svelte';
	import BatasPasar from '$lib/components/BatasPasar.svelte';
	import PerbandinganEA from '$lib/components/market/PerbandinganEA.svelte';
	import KalkulatorPosisi from '$lib/components/market/KalkulatorPosisi.svelte';
	import AkunMT5 from '$lib/components/market/AkunMT5.svelte';

	const area = AREAS.find((a) => a.kunci === 'forex')!;
	const sub = $derived.by(() => {
		const s = page.url.searchParams.get('sub') ?? 'ringkas';
		return SLUG_LAMA[s] ?? s;
	});
</script>

<svelte:head><title>Forex | War Room</title></svelte:head>

<MarketShell
	{area}
	aktif={sub}
	judul="Forex & Gold"
	tag="AKTIF"
	deskripsi="Eksekusi demo XAUUSD lewat EA Reaper di Azure. Sinyal dihitung lokal di EA (EMA+RSI), telemetri dicatat ke server."
	sumber="Telemetri MT5 + fills.csv"
	terverifikasi={true}
>
	{#if sub === 'ringkas'}
		<div class="space-y-4">
			<ForexCockpitExness />
			<AkunMT5 />
			<BatasPasar market="forex" />
		</div>
	{:else if sub === 'sinyal'}
		<ForexSinyal />
	{:else if sub === 'uji'}
		<div class="space-y-4">
			<PerbandinganEA />
			<PasarUji filter="forex" />
		</div>
	{:else if sub === 'eksekusi'}
		<JournalPanel market="forex" />
	{:else if sub === 'paper'}
		<JournalPanel market="forex" />
	{:else if sub === 'alat'}
		<div class="space-y-4">
			<KalkulatorPosisi />
			<ForexAlat />
		</div>
	{:else}
		<ForexCockpitExness />
	{/if}
</MarketShell>
