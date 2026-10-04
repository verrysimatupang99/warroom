<script lang="ts">
	// Ringkas — Command Center & Trading Cockpit.
	// Menyajikan gambaran menyeluruh portofolio, setup sinyal aktif, batas risiko,
	// dan validasi statistik dalam satu layar terstruktur.
	import {
		getAlerts,
		getArea,
		getAreas,
		getKesegaran,
		getKesehatan
	} from '$lib/api/client';
	import type {
		AlertsPayload,
		AreaPayload,
		Fakta,
		AreasPayload,
		Kesehatan,
		KesegaranPayload
	} from '$lib/api/types';
	import { live } from '$lib/api/live.svelte';
	import { angka, waktuWIB } from '$lib/format';
	import Block from '$lib/components/Block.svelte';
	import EventFeed from '$lib/components/EventFeed.svelte';
	import EquityCurve from '$lib/components/EquityCurve.svelte';
	import RiskMeter from '$lib/components/RiskMeter.svelte';
	import SignalCard from '$lib/components/SignalCard.svelte';
	import StatisticalEdgeCard from '$lib/components/StatisticalEdgeCard.svelte';
	import StrategyLeaderboard from '$lib/components/StrategyLeaderboard.svelte';
	import DecisionFeed from '$lib/components/DecisionFeed.svelte';

	let areas = $state<AreasPayload | null>(null);
	let kesegaran = $state<KesegaranPayload | null>(null);
	let sehat = $state<Kesehatan | null>(null);
	let alerts = $state<AlertsPayload | null>(null);
	let kripto = $state<AreaPayload | null>(null);
	let polymarket = $state<AreaPayload | null>(null);
	let galat = $state<string | null>(null);
	let memuat = $state(true);

	async function muat() {
		const [a, k, h, al, kr, pm] = await Promise.allSettled([
			getAreas(),
			getKesegaran(),
			getKesehatan(),
			getAlerts(),
			getArea('crypto'),
			getArea('polymarket')
		]);
		if (a.status === 'fulfilled') areas = a.value;
		if (k.status === 'fulfilled') kesegaran = k.value;
		if (h.status === 'fulfilled') sehat = h.value;
		if (al.status === 'fulfilled') alerts = al.value;
		if (kr.status === 'fulfilled') kripto = kr.value;
		if (pm.status === 'fulfilled') polymarket = pm.value;
		memuat = false;
	}

	$effect(() => {
		void muat();
		const t = setInterval(() => void muat(), 15000);
		return () => clearInterval(t);
	});

	// Ekstrak Fakta Kripto
	const faktaKripto = $derived(kripto?.facts ?? []);

	function cariFakta(koleksi: Fakta[], kunci: string) {
		return koleksi.find((f) => f.key === kunci)?.value ?? null;
	}

	const dataEquity = $derived(
		(cariFakta(faktaKripto, 'equity') as {
			points?: { i: number; r: number }[];
			stats?: Record<string, number>;
		} | null) ?? null
	);

	const dataRisiko = $derived(
		(cariFakta(faktaKripto, 'risiko') as Record<string, unknown> | null) ?? null
	);

	const dataLedger = $derived(
		(cariFakta(faktaKripto, 'ledger') as {
			trade?: number;
			total_r?: number;
			terakhir?: { r: number; note: string }[];
		} | null) ?? null
	);

	const kandidatList = $derived.by(() => {
		const k = cariFakta(faktaKripto, 'kandidat');
		if (Array.isArray(k)) return k;
		return [];
	});

	const dataPosisi = $derived.by(() => {
		const p = cariFakta(faktaKripto, 'posisi');
		if (Array.isArray(p)) return p;
		return [];
	});

	// Ekstrak Fakta Polymarket
	const faktaPoly = $derived(polymarket?.facts ?? []);
	const dataVerdict = $derived(
		(cariFakta(faktaPoly, 'verdict') as {
			n?: number;
			win?: number;
			be?: number;
			ci?: number;
			ci95?: [number, number];
		} | null) ?? null
	);

	const totalR = $derived(dataEquity?.stats?.total_r ?? dataLedger?.total_r ?? 0);
	const winrate = $derived(dataEquity?.stats?.winrate_pct ?? 0);
	const sisaRuangR = $derived(Number(dataRisiko?.sisa_ruang_r ?? 3.0));
	const totalTrade = $derived(dataEquity?.stats?.trades ?? dataLedger?.trade ?? 0);
</script>

<div class="space-y-4">
	<!-- Header Command Center -->
	<div class="flex flex-wrap items-center justify-between gap-3 border-b border-line pb-3">
		<div>
			<div class="flex items-center gap-2">
				<h1 class="text-26 font-bold tracking-tight text-text font-display">Ringkas</h1>
				<span class="inline-flex items-center gap-1.5 rounded-full bg-pos/10 border border-pos/30 px-2 py-0.5 text-11 font-mono text-pos">
					<span class="h-2 w-2 rounded-full bg-pos animate-pulse"></span>
					ENGINE NORMAL
				</span>
			</div>
			<p class="text-12 text-text-3 mt-0.5">
				Command Center · Portofolio, Sinyal Aktif, Kapasitas Risiko &amp; Edge Statistik
			</p>
		</div>

		<div class="flex items-center gap-2 text-11 text-text-3 font-mono">
			<span class="rounded bg-surface px-2 py-1 border border-line">
				User: <b class="text-text-2">{sehat?.user ?? 'operator'}</b>
			</span>
			<span class="rounded bg-surface px-2 py-1 border border-line">
				DB: <b class={sehat?.db ? 'text-pos' : 'text-neg'}>{sehat?.db ? 'Connected' : 'Error'}</b>
			</span>
		</div>
	</div>

	<!-- Alert Banner jika ada alert terbuka -->
	{#if alerts && alerts.terbuka > 0}
		<div
			class="rounded-card border border-warn/40 bg-warn/10 px-4 py-3 text-12 text-text-2 shadow-sm flex items-center justify-between"
			data-testid="alert-banner"
		>
			<div class="flex items-center gap-2">
				<span class="text-16 font-bold text-warn">⚠</span>
				<div>
					<span class="angka font-bold text-warn">{alerts.terbuka} Alert</span> membutuhkan perhatian ·
					<span class="text-text-3">Transport: {alerts.transport.nama}</span>
				</div>
			</div>
			<a class="rounded bg-warn/20 border border-warn/40 px-2.5 py-1 text-11 font-medium text-warn hover:bg-warn/30 transition-colors" href="/sistem">
				Buka Sistem →
			</a>
		</div>
	{/if}

	<!-- 4 Kartu KPI Utama di Atas (Glance Cards) -->
	<div class="grid grid-cols-2 gap-3 lg:grid-cols-4">
		<!-- KPI 1: Total Return R -->
		<div class="permukaan-2 rounded-card border border-line p-3">
			<div class="flex items-center justify-between text-11 text-text-3">
				<span>Total Ekuitas</span>
				<span class="font-mono text-10">Paper</span>
			</div>
			<div class="mt-1 flex items-baseline gap-1.5">
				<span class="angka text-26 font-bold {totalR >= 0 ? 'text-pos' : 'text-neg'}">
					{totalR > 0 ? '+' : ''}{angka(totalR)}
				</span>
				<span class="text-13 text-text-3 font-mono">R</span>
			</div>
			<div class="mt-1 flex items-center justify-between text-11 text-text-3">
				<span>Win Rate: <b class="angka text-text-2">{angka(winrate)}%</b></span>
				<span>{totalTrade} trade</span>
			</div>
		</div>

		<!-- KPI 2: Batas Risiko -->
		<div class="permukaan-2 rounded-card border border-line p-3">
			<div class="flex items-center justify-between text-11 text-text-3">
				<span>Kapasitas Risiko</span>
				<span class="rounded bg-pos/10 px-1 text-9 font-bold text-pos border border-pos/20">AMAN</span>
			</div>
			<div class="mt-1 flex items-baseline gap-1.5">
				<span class="angka text-26 font-bold text-text">
					{angka(sisaRuangR)}
				</span>
				<span class="text-13 text-text-3 font-mono">R Sisa</span>
			</div>
			<div class="mt-1 flex items-center justify-between text-11 text-text-3">
				<span>Limit: <b class="angka text-text-2">{angka(Number(dataRisiko?.batas_rugi_r ?? 3))} R/hari</b></span>
				<span>{Number(dataRisiko?.posisi_terbuka ?? 0)} terbuka</span>
			</div>
		</div>

		<!-- KPI 3: Sinyal Aktif -->
		<div class="permukaan-2 rounded-card border border-line p-3">
			<div class="flex items-center justify-between text-11 text-text-3">
				<span>Sinyal &amp; Setup</span>
				<span class="font-mono text-10 text-accent">SMC</span>
			</div>
			<div class="mt-1 flex items-baseline gap-1.5">
				<span class="angka text-26 font-bold text-accent">
					{kandidatList.length}
				</span>
				<span class="text-13 text-text-3">setup</span>
			</div>
			<div class="mt-1 flex items-center justify-between text-11 text-text-3">
				<span>Kandidat pasar aktif</span>
				<a href="/crypto" class="text-accent underline text-10">Lihat crypto →</a>
			</div>
		</div>

		<!-- KPI 4: Polymarket Edge -->
		<div class="permukaan-2 rounded-card border border-line p-3">
			<div class="flex items-center justify-between text-11 text-text-3">
				<span>Polymarket Edge</span>
				<span class="font-mono text-10 text-paper">5m Window</span>
			</div>
			<div class="mt-1 flex items-baseline gap-1.5">
				<span class="angka text-26 font-bold text-pos">
					{dataVerdict?.n ? `${((dataVerdict.win ?? 0) / dataVerdict.n * 100).toFixed(1)}%` : '—'}
				</span>
				<span class="text-13 text-text-3 font-mono">Win</span>
			</div>
			<div class="mt-1 flex items-center justify-between text-11 text-text-3">
				<span>BE: <b class="angka text-text-2">{((dataVerdict?.be ?? 0.7666) * 100).toFixed(1)}%</b></span>
				<span>{dataVerdict?.n ? `${dataVerdict.n} n` : '0 n'}</span>
			</div>
		</div>
	</div>

	<!-- Papan Peringkat Strategi (Inspirasi Fomo Family Leaderboard) -->
	<StrategyLeaderboard />

	<!-- Layout Dua Kolom Utama (Grid) -->
	<div class="grid grid-cols-1 gap-4 lg:grid-cols-12">
		<!-- Kolom Kiri: Kurva Ekuitas, Setup Trading, Aliran Keputusan (7 Kolom) -->
		<div class="space-y-4 lg:col-span-7">
			<!-- Kurva Ekuitas Interaktif -->
			<EquityCurve points={dataEquity?.points} stats={dataEquity?.stats} />

			<!-- Board Sinyal & Setup Aktif -->
			<div class="permukaan-2 rounded-card border border-line p-3">
				<div class="mb-3 flex items-center justify-between border-b border-line-soft pb-2">
					<div>
						<h3 class="text-14 font-medium text-text">Setup Sinyal Aktif</h3>
						<p class="text-11 text-text-3">Setup SMC yang terdeteksi dan diuji terhadap aturan gate</p>
					</div>
					<span class="rounded bg-surface px-2 py-0.5 text-11 font-mono text-text-3 border border-line">
						{kandidatList.length} setup
					</span>
				</div>

				{#if kandidatList.length === 0}
					<div class="flex flex-col items-center justify-center rounded border border-dashed border-line p-6 text-center text-text-3">
						<span class="text-20 mb-1">🛡️</span>
						<p class="text-13 text-text-2 font-medium">Tidak ada setup yang lulus semua gate saat ini</p>
						<p class="text-11 mt-1 max-w-sm">
							Engine disiplin menolak trade yang tidak memiliki keunggulan statistik. Modal tetap aman.
						</p>
					</div>
				{:else}
					<div class="space-y-2.5">
						{#each kandidatList as setup (setup.pair + String(setup.entry))}
							<SignalCard {setup} />
						{/each}
					</div>
				{/if}
			</div>

			<!-- Aliran Keputusan & Eksekusi (Inspirasi Fomo Family Feed) -->
			<DecisionFeed />
		</div>

		<!-- Kolom Kanan: Pengawas Risiko, Edge Statistik, Feed Kejadian (5 Kolom) -->
		<div class="space-y-4 lg:col-span-5">
			<!-- Pengawas Risiko -->
			<RiskMeter risiko={dataRisiko} />

			<!-- Status Posisi Terbuka Aktif -->
			<div class="permukaan-2 rounded-card border border-line p-3">
				<div class="mb-2 flex items-center justify-between border-b border-line-soft pb-2">
					<div class="flex items-center gap-1.5">
						{#if dataPosisi.length > 0}
							<span class="h-2 w-2 rounded-full bg-pos animate-pulse"></span>
						{/if}
						<h3 class="text-13 font-medium text-text">Posisi Terbuka Aktif</h3>
					</div>
					<a href="/crypto" class="text-11 text-accent hover:underline font-mono">
						{dataPosisi.length} posisi →
					</a>
				</div>
				{#if dataPosisi.length === 0}
					<div class="py-4 px-2 text-center space-y-1">
						<div class="text-12 font-medium text-text-2">Tidak ada posisi terbuka saat ini (0/3).</div>
						<p class="text-11 text-text-3">
							Engine disiplin menahan diri saat tidak ada setup valid demi melindungi modal.
						</p>
					</div>
				{:else}
					<div class="space-y-2">
						{#each dataPosisi as p (p.signal_id ?? p.pair)}
							<div class="rounded border border-line bg-surface p-2.5 space-y-2 font-mono text-11">
								<div class="flex items-center justify-between">
									<div class="flex items-center gap-1.5">
										<span class="font-bold text-text text-13">{p.pair}</span>
										<span class="rounded px-1.5 py-0.5 text-9 font-bold uppercase {p.direction === 'LONG' ? 'text-pos bg-pos/10 border border-pos/20' : 'text-neg bg-neg/10 border border-neg/20'}">
											{p.direction}
										</span>
										<span class="rounded bg-accent/10 text-accent border border-accent/20 px-1.5 py-0.5 text-9 font-bold">
											{p.status ?? 'OPEN'}
										</span>
									</div>
									<span class="text-10 text-text-3">{p.signal_id ?? ''}</span>
								</div>
								<div class="grid grid-cols-4 gap-1.5 text-10">
									<div class="rounded bg-canvas/60 p-1 border border-line">
										<div class="text-9 text-text-3 uppercase">Entry</div>
										<div class="font-bold text-text">${angka(p.entry)}</div>
									</div>
									<div class="rounded bg-canvas/60 p-1 border border-line">
										<div class="text-9 text-text-3 uppercase">Stop</div>
										<div class="font-bold text-neg">${angka(p.stop)}</div>
									</div>
									<div class="rounded bg-canvas/60 p-1 border border-line">
										<div class="text-9 text-text-3 uppercase">TP1</div>
										<div class="font-bold text-pos">${angka(p.tp1)}</div>
									</div>
									<div class="rounded bg-canvas/60 p-1 border border-line">
										<div class="text-9 text-text-3 uppercase">Size</div>
										<div class="font-bold text-accent">${angka(p.size_usd)}</div>
									</div>
								</div>
								{#if p.note}
									<div class="text-10 text-text-3 truncate font-sans">
										{p.note}
									</div>
								{/if}
							</div>
						{/each}
					</div>
				{/if}
			</div>

			<!-- Kartu Bukti Statistik Polymarket -->
			<StatisticalEdgeCard verdict={dataVerdict} judul="Polymarket 5m Statistical Gate" />

			<!-- Ringkasan Kesehatan 5 Pasar -->
			<div class="permukaan-2 rounded-card border border-line p-3">
				<div class="mb-2 flex items-center justify-between border-b border-line-soft pb-2">
					<h3 class="text-13 font-medium text-text">Pusat Pasar &amp; Venue</h3>
					<span class="text-11 text-text-3 font-mono">5 venue</span>
				</div>
				<div class="space-y-1.5 text-12">
					{#each (areas?.areas ?? []) as a (a.area)}
						<a
							href={`/${a.area}`}
							class="flex items-center justify-between rounded border border-line-soft bg-surface p-2 transition-colors hover:border-accent-2"
						>
							<div class="flex items-center gap-2">
								<span class="font-mono uppercase font-bold text-text-2">{a.area}</span>
								<span class="text-11 text-text-3">({a.fakta} fakta)</span>
							</div>
							<div class="flex items-center gap-2 text-11">
								{#if a.basi > 0}
									<span class="text-warn font-mono">⚠ {a.basi} basi</span>
								{:else}
									<span class="text-pos font-mono">● Segar</span>
								{/if}
								<span class="text-text-3">→</span>
							</div>
						</a>
					{/each}
				</div>
			</div>

			<!-- Aliran Kejadian Realtime SSE -->
			<div class="permukaan-2 rounded-card border border-line p-3">
				<div class="mb-2 flex items-center justify-between border-b border-line-soft pb-2">
					<div class="flex items-center gap-2">
						<h3 class="text-13 font-medium text-text">Kejadian Real-Time</h3>
						<span class="h-2 w-2 rounded-full {live.status === 'live' ? 'bg-pos' : 'bg-warn'} animate-pulse"></span>
					</div>
					<span class="text-10 font-mono text-text-3 uppercase">{live.status}</span>
				</div>
				<EventFeed kejadian={live.kejadian} memuat={live.status === 'menyambung'} galat={live.pesan} />
			</div>
		</div>
	</div>
</div>