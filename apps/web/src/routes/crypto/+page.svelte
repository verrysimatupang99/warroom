<script lang="ts">
	import { page } from '$app/state';
	import { AREAS, SLUG_LAMA } from '$lib/nav';
	import MarketShell from '$lib/components/MarketShell.svelte';
	import PasarUji from '$lib/components/market/PasarUji.svelte';
	import CryptoSinyal from '$lib/components/market/CryptoSinyal.svelte';
	import CryptoRingkas from '$lib/components/market/CryptoRingkas.svelte';
	import JournalPanel from '$lib/components/JournalPanel.svelte';
	import BatasPasar from '$lib/components/BatasPasar.svelte';
	import RiwayatKeputusan from '$lib/components/market/RiwayatKeputusan.svelte';
	import JurnalSinyal from '$lib/components/market/JurnalSinyal.svelte';

	const area = AREAS.find((a) => a.kunci === 'crypto')!;
	const sub = $derived.by(() => {
		const s = page.url.searchParams.get('sub') ?? 'ringkas';
		return SLUG_LAMA[s] ?? s;
	});
</script>

<svelte:head><title>Crypto | War Room</title></svelte:head>

<MarketShell
	{area}
	aktif={sub}
	judul="Crypto"
	tag="PAPER"
	deskripsi="Paper trading momentum di 40 koin teratas menurut volume. Tanpa order nyata, hanya pencatatan."
	sumber="MEXC + momentum_paper.json"
	terverifikasi={true}
>
	{#if sub === 'ringkas'}
		<div class="space-y-4">
			<CryptoRingkas />
			<BatasPasar market="crypto" />
		</div>
	{:else if sub === 'sinyal'}
		<div class="space-y-4">
			<CryptoSinyal />
			<RiwayatKeputusan market="crypto" />
			<JurnalSinyal />
		</div>
	{:else if sub === 'uji'}
		<PasarUji filter="crypto" />
	{:else if sub === 'eksekusi'}
		<JournalPanel market="crypto" />
	{:else}
		<CryptoRingkas />
	{/if}
</MarketShell>
