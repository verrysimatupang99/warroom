<script lang="ts">
	/**
	 * TradingPanel.svelte — status live trading memecoin & MT5 di War Room.
	 *
	 * Sumber data (hanya endpoint yang BENAR-BENAR ada di warroom-api):
	 * - GET /api/v1/infra/health  → status MT5 paper-1/paper-2, Memoh, watchdog
	 */
	import { onMount } from 'svelte';
	import { urlApi } from '$lib/api/client';

	interface Infra {
		tersedia?: boolean;
		umur_s?: number | null;
		memoh_runtime?: { active?: string; outbound_conn?: number; restarts?: number };
		mt5?: Record<string, string>;
		instabox_watchdog?: { timer?: string; last_status?: string };
		cyber1?: { disk_pct?: number; mem_available_mb?: number };
		warroom?: { root_http?: string; api_health_http?: string };
	}

	let infra = $state<Infra | null>(null);
	let mt5 = $state<Record<string, string>>({});
	let galat = $state<string | null>(null);
	let memuat = $state(true);

	onMount(() => {
		let hidup = true;
		fetch(urlApi('/api/v1/infra/health'), { credentials: 'include' })
			.then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
			.then((d: Infra) => {
				if (!hidup) return;
				infra = d;
				mt5 = d.mt5 ?? {};
			})
			.catch((e) => {
				if (hidup) galat = e.message;
			})
			.finally(() => {
				if (hidup) memuat = false;
			});
		return () => {
			hidup = false;
		};
	});

	const semuaUp = $derived(Object.values(mt5).length > 0 && Object.values(mt5).every((v) => v === 'up'));
	const umurTeks = (s: number | null) =>
		s == null ? 'tidak diketahui' : s < 90 ? `${s} dtk lalu` : `${Math.round(s / 60)} mnt lalu`;
</script>

<section class="rounded-card border border-line bg-surface p-4" data-testid="trading-panel">
	<div class="flex flex-wrap items-center justify-between gap-2">
		<div>
			<h2 class="text-13 font-bold text-text">Live Trading — MT5 & Infra</h2>
			<p class="mt-0.5 text-11 text-text-3">
				Status terminal MT5 & infra lintas mesin · snapshot {umurTeks(infra?.umur_s ?? null)}
			</p>
		</div>
		{#if semuaUp}
			<span class="rounded-control border border-pos/40 bg-pos/10 px-2 py-1 font-mono text-10 text-pos">SEMUA UP</span>
		{:else if Object.keys(mt5).length}
			<span class="rounded-control border border-neg/40 bg-neg/10 px-2 py-1 font-mono text-10 text-neg">ADA YANG MATI</span>
		{/if}
	</div>

	{#if memuat && !infra}
		<p class="mt-3 text-11 text-text-3">Memuat status trading…</p>
	{:else if galat}
		<p class="mt-3 text-11 text-neg">Gagal ambil status: {galat}</p>
	{:else if !infra || infra.tersedia === false}
		<p class="mt-3 text-11 text-text-3">Belum ada snapshot infra dari cyber1.</p>
	{:else}
		<div class="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
			{#each Object.entries(mt5) as [nama, nilai] (nama)}
				<div class="rounded-control border px-3 py-2 {nilai === 'up' ? 'border-pos/40 bg-pos/10' : 'border-neg/40 bg-neg/10'}">
					<div class="label-mikro font-mono">MT5 {nama}</div>
					<div class="mt-0.5 font-mono text-14 font-bold {nilai === 'up' ? 'text-pos' : 'text-neg'}">{nilai}</div>
				</div>
			{/each}
		</div>

		<div class="mt-2 grid gap-2 sm:grid-cols-3">
			<div class="rounded-control border border-line bg-surface-2 px-3 py-2">
				<div class="label-mikro font-mono text-text-3">MEMOH RUNTIME</div>
				<div class="mt-0.5 font-mono text-12 text-text">{infra.memoh_runtime?.active ?? '—'}</div>
			</div>
			<div class="rounded-control border border-line bg-surface-2 px-3 py-2">
				<div class="label-mikro font-mono text-text-3">WATCHDOG</div>
				<div class="mt-0.5 font-mono text-12 text-text">{infra.instabox_watchdog?.timer ?? '—'}</div>
			</div>
			<div class="rounded-control border border-line bg-surface-2 px-3 py-2">
				<div class="label-mikro font-mono text-text-3">CYBER1 DISK</div>
				<div class="mt-0.5 font-mono text-12 text-text">{infra.cyber1?.disk_pct ?? '—'}%</div>
			</div>
		</div>
	{/if}
</section>
