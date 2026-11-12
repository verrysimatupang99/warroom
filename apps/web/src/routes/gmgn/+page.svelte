<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { AREAS, SLUG_LAMA } from '$lib/nav';
	import { getAreaFakta } from '$lib/api/client';
	import type { AreaPayload, Fact } from '$lib/api/types';
	import MarketShell from '$lib/components/MarketShell.svelte';
	import Skeleton from '$lib/components/Skeleton.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import BatasPasar from '$lib/components/BatasPasar.svelte';

	const area = AREAS.find((a) => a.kunci === 'gmgn')!;
	const sub = $derived.by(() => {
		const s = page.url.searchParams.get('sub') ?? 'ringkas';
		return SLUG_LAMA[s] ?? s;
	});

	let payload = $state<AreaPayload | null>(null);
	let memuat = $state(true);
	let galat = $state<string | null>(null);

	async function muat() {
		memuat = true;
		galat = null;
		try {
			payload = await getAreaFakta('gmgn');
		} catch (e) {
			galat = e instanceof Error ? e.message : 'Gagal memuat fakta GMGN / DEX';
		}
		memuat = false;
	}

	onMount(() => {
		void muat();
	});

	function cariFakta(kind: string, key: string): Fact | null {
		if (!payload?.facts) return null;
		return payload.facts.find((f) => f.kind === kind && f.key === key) ?? null;
	}

	const radar = $derived(
		(cariFakta('gmgn', 'radar')?.value ?? payload?.data?.radar ?? null) as Record<string, any> | null
	);
	const gmgnPaper = $derived(
		(cariFakta('gmgn', 'paper')?.value ?? payload?.data?.paper ?? null) as Record<string, any> | null
	);
	const lpPaper = $derived(
		(cariFakta('snapshot', 'lp_paper')?.value ?? payload?.data?.lp_paper ?? null) as Record<string, any> | null
	);
	const lpMark = $derived(
		(cariFakta('snapshot', 'lp_mark')?.value ?? payload?.data?.lp_mark ?? null) as Record<string, any> | null
	);

	const chains = $derived(((radar?.chains ?? []) as Record<string, any>[]));
	const totalPools = $derived(chains.reduce((s, c) => s + Number(c.pools ?? 0), 0));
	const totalViable = $derived(chains.reduce((s, c) => s + Number(c.viable ?? 0), 0));
	const runCfg = $derived((gmgnPaper?.isi?.['run_config.json'] ?? null) as Record<string, any> | null);
	const lpBasis = $derived((lpPaper?.basis ?? null) as Record<string, any> | null);
	const lpGeometri = $derived(
		Object.entries((lpPaper?.per_geometri ?? {}) as Record<string, Record<string, any>>)
	);
	const lpKelompok = $derived(
		Object.entries((lpPaper?.per_kelompok ?? {}) as Record<string, Record<string, any>>)
	);

	function angka(v: number | null | undefined, digit = 2): string {
		if (v == null || !Number.isFinite(v)) return '—';
		return v.toLocaleString('id-ID', { minimumFractionDigits: digit, maximumFractionDigits: digit });
	}
	function usdRingkas(v: number | null | undefined): string {
		if (v == null || !Number.isFinite(v)) return '—';
		if (Math.abs(v) >= 1e9) return `$${(v / 1e9).toFixed(2)}B`;
		if (Math.abs(v) >= 1e6) return `$${(v / 1e6).toFixed(2)}M`;
		if (Math.abs(v) >= 1e3) return `$${(v / 1e3).toFixed(1)}K`;
		return `$${v.toFixed(2)}`;
	}
</script>

<svelte:head><title>GMGN | War Room</title></svelte:head>

<MarketShell
	{area}
	aktif={sub}
	judul="GMGN & DEX Radar"
	tag="PAPER"
	deskripsi="Radar likuiditas multi-chain (Solana, Base, BSC, Robinhood, Arc, HyperEVM) dan simulasi LP / memecoin paper. Eksekusi sniper on-chain dinonaktifkan sementara."
	sumber="radar_state.json + gmgn-paper/sim_ledger.jsonl"
	terverifikasi={true}
>
	{#if memuat && !payload}
		<Skeleton baris={5} tinggi={44} />
	{:else if galat && !payload}
		<EmptyState judul="Data GMGN belum tersedia" pesan={galat} onulang={() => void muat()} />
	{:else if sub === 'ringkas'}
		<div class="space-y-4">
			<!-- 4 Kartu KPI Utama (seragam dgn Forex, Crypto, IDX, Polymarket) -->
			<section class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
				<div class="rounded-card border border-line bg-surface p-4">
					<div class="label-mikro font-mono text-text-3">RADAR MULTI-CHAIN</div>
					<div class="mt-1 font-mono text-17 font-bold text-text">
						{chains.length > 0 ? `${chains.length} Rantai` : '—'}
					</div>
					<div class="mt-1 font-mono text-11 text-text-3">
						{totalPools} pool terpantau · {totalViable} viable
					</div>
				</div>

				<div class="rounded-card border border-line bg-surface p-4">
					<div class="label-mikro font-mono text-text-3">SAMPEL SIMULASI LP / DEX</div>
					<div class="mt-1 font-mono text-17 font-bold text-text">
						{lpPaper?.sampel != null ? `${lpPaper.sampel.toLocaleString('id-ID')} posisi` : '—'}
					</div>
					<div class="mt-1 font-mono text-11 text-text-3">
						geometri basis: {lpPaper?.geometri ?? 'TP+100/SL-65'} · notional ${lpPaper?.notional_usd ?? 4}
					</div>
				</div>

				<div class="rounded-card border border-line bg-surface p-4">
					<div class="label-mikro font-mono text-text-3">WIN RATE & MEDIAN NET (PAPER)</div>
					<div class="mt-1 flex items-baseline gap-2">
						<span class="font-mono text-17 font-bold text-text">
							{lpBasis?.menang_pct != null ? `${angka(lpBasis.menang_pct, 1)}%` : '—'}
						</span>
						{#if lpBasis?.median_net_pct != null}
							<span class="font-mono text-12 font-bold {lpBasis.median_net_pct >= 0 ? 'text-pos' : 'text-neg'}">
								(med {angka(lpBasis.median_net_pct, 1)}%)
							</span>
						{/if}
					</div>
					<div class="mt-1 font-mono text-11 text-text-3">
						TP {angka(lpBasis?.tp_rate_pct, 1)}% · SL {angka(lpBasis?.sl_rate_pct, 1)}%
					</div>
				</div>

				<div class="rounded-card border border-line bg-surface p-4">
					<div class="label-mikro font-mono text-text-3">FRIKSI & STATUS ENGINE</div>
					<div class="mt-1 font-mono text-15 font-bold text-warn">
						{lpPaper?.gesekan?.friction_median_pct != null
							? `Friksi med ${angka(lpPaper.gesekan.friction_median_pct, 2)}%`
							: 'PAPER ONLY'}
					</div>
					<div class="mt-1 font-mono text-11 text-text-3">
						slippage med {angka(lpPaper?.gesekan?.slippage_median_pct, 2)}% · eksekusi live dinonaktifkan sementara
					</div>
				</div>
			</section>

			<!-- Tabel Radar Likuiditas Multi-Chain -->
			<section class="rounded-card border border-line bg-surface p-4">
				<div class="flex flex-wrap items-center justify-between gap-2">
					<div>
						<h2 class="text-13 font-bold text-text">Radar Likuiditas & Rasio V/L per Rantai</h2>
						<p class="mt-0.5 text-11 text-text-3">
							Pemindaian kepadatan pool, rasio Volume/Liquidity (V/L), dan deteksi honeypot dari <code class="font-mono">radar_state.json</code>.
						</p>
					</div>
					<span class="font-mono text-10 text-text-3">sumber: {radar?.sumber ?? 'lokal'}</span>
				</div>

				{#if chains.length === 0}
					<p class="mt-3 text-12 text-text-3">Data radar rantai belum tersedia.</p>
				{:else}
					<div class="mt-3 overflow-x-auto">
						<table class="w-full text-left font-mono text-11">
							<thead class="border-b border-line text-10 text-text-3">
								<tr>
									<th class="px-2 py-1.5">Chain</th>
									<th class="px-2 py-1.5 text-right">Umur</th>
									<th class="px-2 py-1.5 text-right">Pools (Viable)</th>
									<th class="px-2 py-1.5 text-right">Total Likuiditas</th>
									<th class="px-2 py-1.5 text-right">Volume 24j</th>
									<th class="px-2 py-1.5 text-right">Avg / Best V/L</th>
									<th class="px-2 py-1.5">Window</th>
									<th class="px-2 py-1.5">Catatan</th>
								</tr>
							</thead>
							<tbody class="divide-y divide-line-soft">
								{#each chains as c (c.chain)}
									<tr class="hover:bg-surface-2/60">
										<td class="px-2 py-1.5 font-bold uppercase text-text">{c.chain}</td>
										<td class="px-2 py-1.5 text-right text-text-3">{c.age_days ?? '—'}h</td>
										<td class="px-2 py-1.5 text-right text-text">
											{c.pools ?? 0} <span class="text-pos">({c.viable ?? 0})</span>
										</td>
										<td class="px-2 py-1.5 text-right text-text-2">{usdRingkas(c.total_liq)}</td>
										<td class="px-2 py-1.5 text-right text-text-2">{usdRingkas(c.total_vol_24h)}</td>
										<td class="px-2 py-1.5 text-right text-text">
											{angka(c.avg_vl, 2)} / <span class="text-accent">{angka(c.best_vl, 1)}</span>
										</td>
										<td class="px-2 py-1.5">
											<span class="rounded border px-1.5 py-0.5 text-10 {c.window === 'OPEN' ? 'border-pos/40 bg-pos/10 text-pos' : c.window === 'CLOSING' ? 'border-warn/40 bg-warn/10 text-warn' : 'border-line bg-surface-2 text-text-3'}">
												{c.window ?? '—'}
											</span>
										</td>
										<td class="px-2 py-1.5 font-sans text-11 text-text-3">{c.note ?? '—'}</td>
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				{/if}
			</section>

			<BatasPasar market="gmgn" />
		</div>

	{:else if sub === 'sinyal'}
		<div class="space-y-4">
			<section class="rounded-card border border-line bg-surface p-4">
				<h2 class="text-13 font-bold text-text">Filter Sinyal & Konfigurasi Mesin GMGN Paper</h2>
				<p class="mt-0.5 text-11 text-text-3">
					Parameter saringan masuk/keluar yang dipakai mesin <code class="font-mono">gmgn-paper</code> saat memindai token baru.
				</p>
				{#if runCfg && typeof runCfg === 'object'}
					<pre class="mt-3 overflow-x-auto rounded border border-line bg-surface-2 p-3 font-mono text-11 text-text-2">{JSON.stringify(runCfg, null, 2)}</pre>
				{:else}
					<p class="mt-2 text-12 text-text-3">Konfigurasi run_config.json belum tersedia.</p>
				{/if}
			</section>

			{#if lpKelompok.length > 0}
				<section class="rounded-card border border-line bg-surface p-4">
					<h2 class="text-13 font-bold text-text">Perbandingan Kelompok Sinyal vs Kontrol Acak</h2>
					<p class="mt-0.5 text-11 text-text-3">
						Menguji apakah sinyal aliran dana menghasilkan net return lebih baik daripada pemilihan pool acak (control).
					</p>
					<div class="mt-3 overflow-x-auto">
						<table class="w-full text-left font-mono text-11">
							<thead class="border-b border-line text-10 text-text-3">
								<tr>
									<th class="px-2 py-1.5">Kelompok</th>
									<th class="px-2 py-1.5 text-right">Sampel (n)</th>
									<th class="px-2 py-1.5 text-right">Win Rate</th>
									<th class="px-2 py-1.5 text-right">Median Net</th>
									<th class="px-2 py-1.5 text-right">Mean Net</th>
									<th class="px-2 py-1.5 text-right">Expectancy ($4)</th>
								</tr>
							</thead>
							<tbody class="divide-y divide-line-soft">
								{#each lpKelompok as [nama, st] (nama)}
									<tr>
										<td class="px-2 py-1.5 font-bold uppercase text-text">{nama}</td>
										<td class="px-2 py-1.5 text-right text-text">{st.n ?? 0}</td>
										<td class="px-2 py-1.5 text-right text-text">{angka(st.menang_pct, 1)}%</td>
										<td class="px-2 py-1.5 text-right {(st.median_net_pct ?? 0) >= 0 ? 'text-pos' : 'text-neg'}">{angka(st.median_net_pct, 2)}%</td>
										<td class="px-2 py-1.5 text-right {(st.mean_net_pct ?? 0) >= 0 ? 'text-pos' : 'text-neg'}">{angka(st.mean_net_pct, 2)}%</td>
										<td class="px-2 py-1.5 text-right font-bold {(st.expectancy_usd ?? 0) >= 0 ? 'text-pos' : 'text-neg'}">${angka(st.expectancy_usd, 3)}</td>
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				</section>
			{/if}
		</div>

	{:else if sub === 'uji'}
		<div class="space-y-4">
			<section class="rounded-card border border-line bg-surface p-4">
				<h2 class="text-13 font-bold text-text">Uji Kepekaan Geometri TP / SL (sim_ledger.jsonl)</h2>
				<p class="mt-0.5 text-11 text-text-3">
					Hasil simulasi lintas geometri Take Profit & Stop Loss setelah dikurangi slippage dan fee DEX.
				</p>
				{#if lpGeometri.length === 0}
					<p class="mt-3 text-12 text-text-3">Belum ada matriks geometri TP/SL yang terbaca.</p>
				{:else}
					<div class="mt-3 overflow-x-auto">
						<table class="w-full text-left font-mono text-11">
							<thead class="border-b border-line text-10 text-text-3">
								<tr>
									<th class="px-2 py-1.5">Geometri TP / SL</th>
									<th class="px-2 py-1.5 text-right">Sampel (n)</th>
									<th class="px-2 py-1.5 text-right">Mean Net (%)</th>
									<th class="px-2 py-1.5 text-right">Median Net (%)</th>
								</tr>
							</thead>
							<tbody class="divide-y divide-line-soft">
								{#each lpGeometri as [geo, g] (geo)}
									<tr>
										<td class="px-2 py-1.5 font-bold text-text">{geo}</td>
										<td class="px-2 py-1.5 text-right text-text-2">{g.n ?? 0}</td>
										<td class="px-2 py-1.5 text-right {(g.mean_net_pct ?? 0) >= 0 ? 'text-pos' : 'text-neg'}">{angka(g.mean_net_pct, 2)}%</td>
										<td class="px-2 py-1.5 text-right font-bold {(g.median_net_pct ?? 0) >= 0 ? 'text-pos' : 'text-neg'}">{angka(g.median_net_pct, 2)}%</td>
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				{/if}
			</section>
		</div>

	{:else if sub === 'eksekusi'}
		<div class="space-y-4">
			<section class="rounded-card border border-line bg-surface p-4">
				<h2 class="text-13 font-bold text-text">Status Eksekusi & Mark Posisi LP</h2>
				<p class="mt-1 text-12 text-text-2">
					Eksekusi sniper on-chain dinonaktifkan sementara karena hasil simulasi menunjukkan friksi slippage DEX menggerus edge bersih.
				</p>
				{#if lpMark?.mark?.length}
					<div class="mt-3 overflow-x-auto">
						<table class="w-full text-left font-mono text-11">
							<thead class="border-b border-line text-10 text-text-3">
								<tr>
									<th class="px-2 py-1.5">Pool</th>
									<th class="px-2 py-1.5 text-right">PnL USD</th>
									<th class="px-2 py-1.5 text-right">vs Hold USD</th>
								</tr>
							</thead>
							<tbody class="divide-y divide-line-soft">
								{#each lpMark.mark as m, i (i)}
									<tr>
										<td class="px-2 py-1.5 text-text">{m.pool ?? m.name ?? `pool-${i + 1}`}</td>
										<td class="px-2 py-1.5 text-right">{angka(m.pnl_usd, 2)}</td>
										<td class="px-2 py-1.5 text-right">{angka(m.vs_hold_usd, 2)}</td>
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				{/if}
			</section>
		</div>
	{/if}
</MarketShell>
