<script lang="ts">
	import { onMount } from 'svelte';
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

	type ModularStrategy = {
		id: string;
		name: string;
		market: string;
		version: string;
		description: string;
		enabled: boolean;
	};
	let strategies = $state<ModularStrategy[]>([]);
	async function loadStrategies() {
		try {
			const res = await fetch('/api/v1/strategies', { credentials: 'include' });
			if (res.ok) {
				const j = (await res.json()) as { strategies?: ModularStrategy[] };
				strategies = Array.isArray(j.strategies) ? j.strategies : [];
			}
		} catch {}
	}
	async function toggleStrategy(id: string, nextEnabled: boolean) {
		try {
			const res = await fetch(`/api/v1/strategies/${id}/toggle`, {
				method: 'POST',
				headers: { 'content-type': 'application/json' },
				credentials: 'include',
				body: JSON.stringify({ enabled: nextEnabled })
			});
			if (res.ok) {
				strategies = strategies.map((s) => (s.id === id ? { ...s, enabled: nextEnabled } : s));
			}
		} catch {}
	}
	let backtestMsg = $state<string | null>(null);
	async function runBacktest(id: string) {
		backtestMsg = `Menjalankan backtest ${id}…`;
		try {
			const res = await fetch(`/api/v1/strategies/${id}/backtest`, {
				method: 'POST',
				credentials: 'include'
			});
			if (res.ok) {
				const j = (await res.json()) as { result?: { status?: string; trades?: number } };
				backtestMsg = `Backtest ${id} selesai (${j.result?.status ?? 'OK'})`;
			} else {
				backtestMsg = `Backtest ${id} gagal (HTTP ${res.status})`;
			}
		} catch {
			backtestMsg = `Backtest ${id} gagal`;
		}
	}
	onMount(() => {
		void loadStrategies();
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
		{#if strategies.length > 0}
			<section class="mb-4 rounded-card border border-line bg-surface p-4 space-y-3">
				<div class="flex items-center justify-between">
					<h2 class="font-mono text-12 font-bold text-text">Strategi Modular Terdaftar ({strategies.length})</h2>
					<span class="font-mono text-10 text-dim">Plug-and-Play Registry</span>
				</div>
				<div class="grid gap-2.5 md:grid-cols-2">
					{#each strategies as st (st.id)}
						<div class="flex items-start justify-between gap-3 rounded-control border border-line bg-surface-2 p-3">
							<div class="min-w-0">
								<div class="flex items-center gap-2">
									<span class="font-mono text-12 font-bold text-text">{st.name}</span>
									<span class="rounded border border-line px-1.5 py-0.5 font-mono text-10 uppercase text-accent">{st.market}</span>
								</div>
								<p class="mt-1 text-11 text-text-3">{st.description}</p>
							</div>
							<div class="flex shrink-0 items-center gap-1.5">
								<button
									type="button"
									onclick={() => void runBacktest(st.id)}
									class="rounded-control border border-line bg-canvas px-2 py-1 font-mono text-10 font-bold text-text-2 hover:border-accent hover:text-accent"
								>
									Backtest
								</button>
								<button
									type="button"
									onclick={() => void toggleStrategy(st.id, !st.enabled)}
									class="rounded-control border px-2.5 py-1 font-mono text-10 font-bold {st.enabled
										? 'border-pos bg-pos/15 text-pos'
										: 'border-line bg-canvas text-dim'}"
								>
									{st.enabled ? 'AKTIF' : 'NONAKTIF'}
								</button>
							</div>
						</div>
					{/each}
				</div>
				{#if backtestMsg}
					<div class="font-mono text-11 text-accent">{backtestMsg}</div>
				{/if}
			</section>
		{/if}
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
