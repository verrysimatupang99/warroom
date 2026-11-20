<script lang="ts">
	import { onMount } from 'svelte';

	interface Props {
		market: 'forex' | 'crypto' | 'idx' | 'polymarket';
	}
	let { market }: Props = $props();

	type ModularStrategy = {
		id: string;
		name: string;
		market: string;
		version: string;
		description: string;
		enabled: boolean;
	};

	let strategies = $state<ModularStrategy[]>([]);
	let loading = $state(true);

	async function load() {
		loading = true;
		try {
			const res = await fetch(`/api/v1/strategies?market=${market}`, { credentials: 'include' });
			if (res.ok) {
				const j = (await res.json()) as { strategies?: ModularStrategy[] };
				strategies = Array.isArray(j.strategies) ? j.strategies : [];
			}
		} catch {
			strategies = [];
		} finally {
			loading = false;
		}
	}

	async function toggle(id: string, nextEnabled: boolean) {
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

	onMount(() => {
		void load();
	});
</script>

<section class="rounded-card border border-line bg-surface p-4 space-y-3">
	<div class="flex flex-wrap items-center justify-between gap-2">
		<div>
			<h3 class="font-mono text-12 font-bold text-text">Strategi Modular Aktif ({market.toUpperCase()})</h3>
			<p class="text-11 text-text-3">Kontrol strategi otomatis yang berjalan di market ini · Batas Daily Loss: <strong class="text-warn">-3.0%</strong></p>
		</div>
		<span class="rounded border border-pos/30 bg-pos/10 px-2 py-0.5 font-mono text-10 font-bold text-pos">
			MODE: {market === 'forex' ? 'LIVE UTAMA' : 'PAPER UTAMA'}
		</span>
	</div>

	{#if loading}
		<div class="font-mono text-11 text-dim">Memuat strategi…</div>
	{:else if strategies.length === 0}
		<div class="rounded-control border border-dashed border-line bg-surface-2 p-3 font-mono text-11 text-dim">
			Belum ada strategi modular terdaftar untuk market {market.toUpperCase()}.
		</div>
	{:else}
		<div class="grid gap-2.5 md:grid-cols-2">
			{#each strategies as st (st.id)}
				<div class="flex items-start justify-between gap-3 rounded-control border border-line bg-surface-2 p-3">
					<div class="min-w-0">
						<div class="font-mono text-12 font-bold text-text">{st.name}</div>
						<p class="mt-0.5 text-11 text-text-3">{st.description}</p>
					</div>
					<button
						type="button"
						onclick={() => void toggle(st.id, !st.enabled)}
						class="shrink-0 rounded-control border px-2.5 py-1 font-mono text-10 font-bold {st.enabled
							? 'border-pos bg-pos/15 text-pos'
							: 'border-line bg-canvas text-dim'}"
					>
						{st.enabled ? 'AKTIF' : 'NONAKTIF'}
					</button>
				</div>
			{/each}
		</div>
	{/if}
</section>
