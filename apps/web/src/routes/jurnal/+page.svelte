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

	<div
		class="inline-flex flex-wrap gap-1 rounded-card border border-line bg-surface p-1"
		role="tablist"
		aria-label="Filter market"
	>
		{#each PILIHAN as p (p.nilai)}
			<button
				type="button"
				role="tab"
				aria-selected={market === p.nilai}
				class="label-mikro transisi min-h-[34px] rounded-control border px-3 py-1 {market === p.nilai
					? 'border-accent/60 bg-surface-2 text-accent'
					: 'border-transparent text-text-3 hover:border-line hover:bg-surface-2/60 hover:text-text'}"
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
