<script lang="ts">
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import JournalPanel from '$lib/components/JournalPanel.svelte';

	const market = $derived.by(() => {
		const m = page.url.searchParams.get('market') ?? 'all';
		return ['all', 'forex', 'crypto'].includes(m) ? (m as 'all' | 'forex' | 'crypto') : 'all';
	});

	const PILIHAN = [
		{ nilai: 'all', label: 'Semua market' },
		{ nilai: 'forex', label: 'Forex' },
		{ nilai: 'crypto', label: 'Crypto' }
	] as const;

	function pilih(nilai: string) {
		if (typeof window !== 'undefined') {
			void goto(`/jurnal?market=${nilai}`, { keepFocus: true, noScroll: true });
		}
	}
</script>

<svelte:head><title>Jurnal | War Room</title></svelte:head>

<div class="space-y-4">
	<PageHeader
		eyebrow="War Room · Eksekusi"
		title="Jurnal lintas market"
		tag="LOKAL"
		description="Satu tempat untuk seluruh riwayat eksekusi: forex dari telemetri MT5 dan catatan fill, crypto dari paper trader momentum. Filter market mengubah seluruh blok di halaman ini."
		terverifikasi={true}
		sumber="fills.csv + momentum_trades.csv + mt5_snapshot"
	/>

	<div class="flex flex-wrap gap-1" role="tablist" aria-label="Filter market">
		{#each PILIHAN as p (p.nilai)}
			<button
				type="button"
				role="tab"
				aria-selected={market === p.nilai}
				class="label-mikro transisi min-h-[44px] rounded-control border px-2.5"
				class:border-accent={market === p.nilai}
				class:text-accent={market === p.nilai}
				class:border-line={market !== p.nilai}
				class:text-text-3={market !== p.nilai}
				onclick={() => pilih(p.nilai)}
			>
				{p.label}
			</button>
		{/each}
	</div>

	{#key market}
		<JournalPanel {market} />
	{/key}
</div>
