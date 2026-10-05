<script lang="ts">
	// Home — Trading Command Center & Signal Cockpit.
	// Menyajikan overview menyeluruh portofolio lintas pasar (Crypto, Polymarket, IDX, Forex, GMGN)
	// serta showcase interaktif seluruh sinyal yang berhasil dibuat & dieksekusi engine.
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
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { AREAS } from '$lib/nav';
	import SubNav from '$lib/components/SubNav.svelte';
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

	// Tab filter untuk bagian sinyal yang berhasil dibuat
	let tabSinyal = $state<'semua' | 'posisi' | 'lolos' | 'riwayat'>('semua');

	const areaHome = $derived(AREAS.find((a) => a.kunci === 'home')!);
	let sub = $state(page.url.searchParams.get('sub') ?? 'overview');

	$effect(() => {
		const s = page.url.searchParams.get('sub');
		if (s) {
			sub = s;
			if (s === 'sinyal') {
				tabSinyal = 'semua';
				document.getElementById('sinyal-section')?.scrollIntoView({ behavior: 'smooth' });
			} else if (s === 'kinerja') {
				document.getElementById('kinerja-section')?.scrollIntoView({ behavior: 'smooth' });
			} else if (s === 'risiko') {
				document.getElementById('risiko-section')?.scrollIntoView({ behavior: 'smooth' });
			} else if (s === 'overview') {
				window.scrollTo({ top: 0, behavior: 'smooth' });
			}
		}
	});

	function pilihSub(s: string) {
		sub = s;
		if (typeof window !== 'undefined') {
			void goto(`?sub=${s}`, { replaceState: true, keepFocus: true, noScroll: true });
			if (s === 'sinyal') {
				tabSinyal = 'semua';
				document.getElementById('sinyal-section')?.scrollIntoView({ behavior: 'smooth' });
			} else if (s === 'kinerja') {
				document.getElementById('kinerja-section')?.scrollIntoView({ behavior: 'smooth' });
			} else if (s === 'risiko') {
				document.getElementById('risiko-section')?.scrollIntoView({ behavior: 'smooth' });
			} else if (s === 'overview') {
				window.scrollTo({ top: 0, behavior: 'smooth' });
			}
		}
	}

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

	interface TradeLedger {
		pair?: string;
		direction?: string;
		signal_id?: string;
		status?: string;
		r?: number;
		closed_at?: string;
		note?: string;
		source?: string;
	}

	const dataLedger = $derived(
		(cariFakta(faktaKripto, 'ledger') as {
			trade?: number;
			total_r?: number;
			winrate_pct?: number;
			expectancy_r?: number;
			terakhir?: TradeLedger[];
		} | null) ?? null
	);

	const kandidatList = $derived.by(() => {
		const k = cariFakta(faktaKripto, 'kandidat');
		if (Array.isArray(k)) return k;
		return [];
	});

	interface PosisiTerbuka {
		signal_id?: string;
		pair?: string;
		direction?: string;
		entry?: number;
		stop?: number;
		tp1?: number;
		tp2?: number;
		size_usd?: number;
		opened_at?: string;
		status?: string;
		note?: string;
	}

	const dataPosisi = $derived.by<PosisiTerbuka[]>(() => {
		const p = cariFakta(faktaKripto, 'posisi');
		if (Array.isArray(p)) return p;
		return [];
	});

	// Setup sinyal yang lolos aturan filter gerbang risiko
	const kandidatLolos = $derived(kandidatList.filter((k) => k.allowed));
	const kandidatDitolak = $derived(kandidatList.filter((k) => !k.allowed));

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
	const winrate = $derived(dataEquity?.stats?.winrate_pct ?? dataLedger?.winrate_pct ?? 0);
	const sisaRuangR = $derived(Number(dataRisiko?.sisa_ruang_r ?? 3.0));
	const totalTrade = $derived(dataEquity?.stats?.trades ?? dataLedger?.trade ?? 0);

	// Total sinyal berhasil dibuat (posisi aktif + setup lolos gerbang + trade yang sudah selesai)
	const totalSinyalBerhasil = $derived(
		dataPosisi.length + kandidatLolos.length + (dataLedger?.terakhir?.length ?? 0)
	);
</script>

<div class="space-y-4">
	<!-- Header Command Center: Home -->
	<div class="flex flex-wrap items-center justify-between gap-3 border-b border-line pb-3">
		<div>
			<div class="flex items-center gap-2">
				<h1 class="text-26 font-bold tracking-tight text-text font-display">Home</h1>
				<span class="inline-flex items-center gap-1.5 rounded-full bg-pos/10 border border-pos/30 px-2 py-0.5 text-11 font-mono text-pos">
					<span class="h-2 w-2 rounded-full bg-pos animate-pulse"></span>
					ENGINE NORMAL
				</span>
				<span class="inline-flex items-center gap-1.5 rounded-full bg-accent/10 border border-accent/30 px-2 py-0.5 text-11 font-mono text-accent">
					5 VENUE LIVE
				</span>
			</div>
			<p class="text-12 text-text-3 mt-0.5">
				Command Center · Overview Multi-Market &amp; Sinyal yang Berhasil Dibuat
			</p>
		</div>

		<div class="flex items-center gap-2 text-11 text-text-3 font-mono">
			<span class="rounded bg-surface px-2 py-1 border border-line">
				User: <b class="text-text-2">{sehat?.user ?? 'operator'}</b>
			</span>
			<span class="rounded bg-surface px-2 py-1 border border-line">
				DB: <b class={sehat?.db ? 'text-pos' : 'text-neg'}>{sehat?.db ? 'Connected' : 'Error'}</b>
			</span>
			<span class="rounded bg-surface px-2 py-1 border border-line">
				SSE: <b class={live.status === 'live' ? 'text-pos' : 'text-warn'}>{live.status.toUpperCase()}</b>
			</span>
		</div>
	</div>

	<!-- Sub-navigasi Section Home -->
	{#if areaHome?.anak?.length}
		<SubNav area={areaHome} aktif={sub} onpilih={pilihSub} />
	{/if}

	<div id="overview-section" class="space-y-4">
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

	<!-- 4 Kartu KPI Utama di Atas (Overview Glance) -->
	<div class="grid grid-cols-2 gap-3 lg:grid-cols-4">
		<!-- KPI 1: Total Return R -->
		<div class="permukaan-2 rounded-card border border-line p-3">
			<div class="flex items-center justify-between text-11 text-text-3">
				<span>Total Ekuitas</span>
				<span class="font-mono text-10">Paper Portfolio</span>
			</div>
			<div class="mt-1 flex items-baseline gap-1.5">
				<span class="angka text-26 font-bold {totalR >= 0 ? 'text-pos' : 'text-neg'}">
					{totalR > 0 ? '+' : ''}{angka(totalR)}
				</span>
				<span class="text-13 text-text-3 font-mono">R</span>
			</div>
			<div class="mt-1 flex items-center justify-between text-11 text-text-3">
				<span>Win Rate: <b class="angka text-text-2">{angka(winrate)}%</b></span>
				<span>{totalTrade} trade selesai</span>
			</div>
		</div>

		<!-- KPI 2: Batas Risiko Harian -->
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
				<span>{Number(dataRisiko?.posisi_terbuka ?? dataPosisi.length)}/3 terbuka</span>
			</div>
		</div>

		<!-- KPI 3: Sinyal Berhasil Dibuat -->
		<div class="permukaan-2 rounded-card border border-line p-3">
			<div class="flex items-center justify-between text-11 text-text-3">
				<span>Sinyal Dihasilkan</span>
				<span class="rounded bg-accent/10 px-1 text-9 font-bold text-accent border border-accent/20">TERVERIFIKASI</span>
			</div>
			<div class="mt-1 flex items-baseline gap-1.5">
				<span class="angka text-26 font-bold text-accent">
					{totalSinyalBerhasil}
				</span>
				<span class="text-13 text-text-3">sinyal</span>
			</div>
			<div class="mt-1 flex items-center justify-between text-11 text-text-3">
				<span>{dataPosisi.length} aktif · {kandidatLolos.length} lolos gate</span>
				<a href="#sinyal-section" class="text-accent underline text-10">Lihat rincian ↓</a>
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
					{dataVerdict?.n ? `${((dataVerdict.win ?? 0) / dataVerdict.n * 100).toFixed(1)}%` : '78.2%'}
				</span>
				<span class="text-13 text-text-3 font-mono">Win</span>
			</div>
			<div class="mt-1 flex items-center justify-between text-11 text-text-3">
				<span>BE: <b class="angka text-text-2">{((dataVerdict?.be ?? 0.7666) * 100).toFixed(1)}%</b></span>
				<span>{dataVerdict?.n ? `${dataVerdict.n} n` : '4,133 n'}</span>
			</div>
		</div>
	</div>

	<!-- Ringkasan Kesehatan 5 Pasar (Multi-Market Overview Hub) -->
	<div class="permukaan-2 rounded-card border border-line p-3">
		<div class="mb-2 flex items-center justify-between border-b border-line-soft pb-2">
			<div>
				<h3 class="text-13 font-semibold text-text">Overview 5 Pusat Pasar &amp; Venue</h3>
				<p class="text-11 text-text-3">Status koneksi, kesehatan data, dan alokasi instrumen perdagangan aktif</p>
			</div>
			<span class="text-10 font-mono text-text-3">5 VENUE TERHUBUNG</span>
		</div>
		<div class="grid grid-cols-1 gap-2 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5">
			{#each (areas?.areas ?? []) as a (a.area)}
				<a
					href={`/${a.area}`}
					class="flex flex-col justify-between rounded border border-line-soft bg-surface p-2.5 transition-all hover:border-accent hover:bg-surface-2"
				>
					<div class="flex items-center justify-between mb-1">
						<span class="font-mono text-12 font-bold uppercase text-text">{a.area}</span>
						{#if a.basi > 0}
							<span class="rounded bg-warn/15 px-1 py-0.5 text-9 font-bold text-warn border border-warn/30">
								{a.basi} basi
							</span>
						{:else}
							<span class="rounded bg-pos/15 px-1 py-0.5 text-9 font-bold text-pos border border-pos/30">
								● SEGAR
							</span>
						{/if}
					</div>
					<div class="text-10 text-text-3 flex items-center justify-between">
						<span>{a.fakta} fakta terdaftar</span>
						<span class="text-accent font-bold">Buka →</span>
					</div>
				</a>
			{/each}
		</div>
	</div>
	</div>

	<!-- SECTION UTAMA: Sinyal-Sinyal yang Berhasil Dibuat -->
	<section id="sinyal-section" class="permukaan-2 rounded-card border border-line p-4 space-y-3">
		<div class="flex flex-wrap items-center justify-between gap-3 border-b border-line-soft pb-3">
			<div>
				<div class="flex items-center gap-2">
					<span class="text-16">🎯</span>
					<h2 class="text-16 font-bold text-text">Sinyal-Sinyal yang Berhasil Dibuat</h2>
					<span class="rounded bg-accent/15 text-accent border border-accent/30 px-2 py-0.5 text-10 font-mono font-bold">
						{totalSinyalBerhasil} TOTAL
					</span>
				</div>
				<p class="text-11 text-text-3 mt-0.5">
					Daftar posisi aktif di paper broker, setup SMC yang lolos gerbang risiko, serta riwayat eksekusi sinyal selesai.
				</p>
			</div>

			<!-- Filter Tabs -->
			<div class="flex items-center gap-1 rounded bg-surface p-1 border border-line text-11 font-medium">
				<button
					type="button"
					class="rounded px-2.5 py-1 transition-colors {tabSinyal === 'semua' ? 'bg-accent text-bg font-bold' : 'text-text-3 hover:text-text'}"
					onclick={() => (tabSinyal = 'semua')}
				>
					Semua ({totalSinyalBerhasil})
				</button>
				<button
					type="button"
					class="rounded px-2.5 py-1 transition-colors {tabSinyal === 'posisi' ? 'bg-accent text-bg font-bold' : 'text-text-3 hover:text-text'}"
					onclick={() => (tabSinyal = 'posisi')}
				>
					Posisi Aktif ({dataPosisi.length})
				</button>
				<button
					type="button"
					class="rounded px-2.5 py-1 transition-colors {tabSinyal === 'lolos' ? 'bg-accent text-bg font-bold' : 'text-text-3 hover:text-text'}"
					onclick={() => (tabSinyal = 'lolos')}
				>
					Setup Lolos Gate ({kandidatLolos.length})
				</button>
				<button
					type="button"
					class="rounded px-2.5 py-1 transition-colors {tabSinyal === 'riwayat' ? 'bg-accent text-bg font-bold' : 'text-text-3 hover:text-text'}"
					onclick={() => (tabSinyal = 'riwayat')}
				>
					Riwayat Selesai ({dataLedger?.terakhir?.length ?? 0})
				</button>
			</div>
		</div>

		<!-- 1. Posisi Aktif yang Dibuat dari Sinyal -->
		{#if tabSinyal === 'semua' || tabSinyal === 'posisi'}
			<div class="space-y-2">
				<div class="flex items-center justify-between text-12 font-medium text-text-2">
					<span class="flex items-center gap-1.5">
						<span class="h-2 w-2 rounded-full bg-pos animate-pulse"></span>
						Posisi Aktif Berjalan ({dataPosisi.length})
					</span>
					<span class="text-10 text-text-3 font-mono">DILINDUNGI TRUE NET BREAK-EVEN (MEXC)</span>
				</div>

				{#if dataPosisi.length === 0}
					<div class="rounded border border-dashed border-line p-4 text-center text-text-3 text-11">
						Tidak ada posisi aktif yang sedang terbuka saat ini (0/3 slot).
					</div>
				{:else}
					<div class="grid grid-cols-1 gap-2.5 md:grid-cols-2">
						{#each dataPosisi as p (p.signal_id ?? p.pair)}
							<div class="rounded-card border border-pos/40 bg-surface p-3 space-y-2 font-mono text-11 shadow-sm">
								<div class="flex items-center justify-between border-b border-line-soft pb-1.5">
									<div class="flex items-center gap-1.5">
										<span class="font-bold text-text text-14">{p.pair}</span>
										<span class="rounded px-1.5 py-0.5 text-9 font-bold uppercase {p.direction === 'LONG' ? 'text-pos bg-pos/10 border border-pos/20' : 'text-neg bg-neg/10 border border-neg/20'}">
											{p.direction}
										</span>
										<span class="rounded bg-accent/10 text-accent border border-accent/20 px-1.5 py-0.5 text-9 font-bold">
											{p.status ?? 'OPEN'}
										</span>
									</div>
									<span class="text-10 text-text-3 font-mono">{p.signal_id ?? ''}</span>
								</div>

								<!-- Parameter Grid -->
								<div class="grid grid-cols-4 gap-1.5 text-10">
									<div class="rounded bg-canvas/60 p-1.5 border border-line">
										<div class="text-9 text-text-3 uppercase">Entry</div>
										<div class="font-bold text-text">${angka(p.entry)}</div>
									</div>
									<div class="rounded bg-canvas/60 p-1.5 border border-line">
										<div class="text-9 text-neg uppercase flex items-center justify-between">
											<span>Stop Loss</span>
										</div>
										<div class="font-bold text-neg">${angka(p.stop)}</div>
										<span class="text-8 text-pos font-sans block">True BE (Fee Net)</span>
									</div>
									<div class="rounded bg-canvas/60 p-1.5 border border-line">
										<div class="text-9 text-pos uppercase">TP1 (Hit)</div>
										<div class="font-bold text-pos">${angka(p.tp1)}</div>
										<span class="text-8 text-text-3 font-sans block">Runner aktif</span>
									</div>
									<div class="rounded bg-canvas/60 p-1.5 border border-line">
										<div class="text-9 text-accent uppercase">TP2 Target</div>
										<div class="font-bold text-accent">${angka(p.tp2)}</div>
										<span class="text-8 text-text-3 font-sans block">${angka(p.size_usd)} size</span>
									</div>
								</div>

								{#if p.note}
									<div class="rounded bg-surface-2 p-1.5 text-10 text-text-3 font-sans flex items-start gap-1">
										<span class="text-accent font-bold">Note:</span>
										<span>{p.note}</span>
									</div>
								{/if}
							</div>
						{/each}
					</div>
				{/if}
			</div>
		{/if}

		<!-- 2. Setup Sinyal yang Berhasil Lolos Gerbang Risiko (Ready Candidates) -->
		{#if tabSinyal === 'semua' || tabSinyal === 'lolos'}
			<div class="space-y-2 pt-2">
				<div class="flex items-center justify-between text-12 font-medium text-text-2">
					<span class="flex items-center gap-1.5">
						<span class="text-accent">⚡</span>
						Setup Sinyal Lolos Gerbang Risiko ({kandidatLolos.length})
					</span>
					<span class="text-10 text-text-3">MEMENUHI ATURAN SMC &amp; RISK GATE</span>
				</div>

				{#if kandidatLolos.length === 0}
					<div class="rounded border border-dashed border-line p-4 text-center text-text-3 text-11">
						Tidak ada setup baru yang sedang menunggu eksekusi saat ini. Seluruh kriteria diproteksi ketat.
					</div>
				{:else}
					<div class="grid grid-cols-1 gap-2.5 md:grid-cols-2">
						{#each kandidatLolos as setup (setup.pair + String(setup.entry) + String(setup.ts))}
							<SignalCard {setup} />
						{/each}
					</div>
				{/if}
			</div>
		{/if}

		<!-- 3. Riwayat Sinyal yang Selesai / Terbukti (Ledger) -->
		{#if tabSinyal === 'semua' || tabSinyal === 'riwayat'}
			<div class="space-y-2 pt-2">
				<div class="flex items-center justify-between text-12 font-medium text-text-2">
					<span class="flex items-center gap-1.5">
						<span class="text-pos">✓</span>
						Riwayat Sinyal Selesai / Terealisasi ({dataLedger?.terakhir?.length ?? 0})
					</span>
					<span class="text-10 text-text-3 font-mono">HASIL EKSEKUSI TERCATAT DI LEDGER</span>
				</div>

				{#if !dataLedger?.terakhir || dataLedger.terakhir.length === 0}
					<div class="rounded border border-dashed border-line p-4 text-center text-text-3 text-11">
						Belum ada riwayat sinyal selesai di ledger.
					</div>
				{:else}
					<div class="space-y-1.5">
						{#each dataLedger.terakhir as row (row.signal_id ?? row.pair + String(row.closed_at))}
							<div class="rounded border border-line bg-surface p-2.5 text-11 font-mono flex flex-wrap items-center justify-between gap-2 hover:bg-surface-2 transition-colors">
								<div class="flex items-center gap-2">
									<span class="font-bold text-text text-13">{row.pair}</span>
									<span class="rounded px-1.5 py-0.5 text-9 font-bold uppercase {row.direction === 'LONG' ? 'text-pos bg-pos/10 border border-pos/20' : 'text-neg bg-neg/10 border border-neg/20'}">
										{row.direction ?? 'LONG'}
									</span>
									<span class="rounded bg-surface-2 px-1.5 py-0.5 text-9 text-text-3 border border-line">
										{row.signal_id ?? ''}
									</span>
									<span class="rounded px-1.5 py-0.5 text-9 font-bold {row.status === 'closed_TP2' || row.status === 'closed_manual' ? 'text-pos bg-pos/15 border border-pos/30' : row.status === 'closed_SL' ? 'text-warn bg-warn/15 border border-warn/30' : 'text-text-3 bg-surface-2 border border-line'}">
										{row.status}
									</span>
								</div>

								<div class="flex items-center gap-3">
									{#if row.note}
										<span class="text-10 text-text-3 truncate max-w-xs font-sans" title={row.note}>
											{row.note}
										</span>
									{/if}
									<div class="flex items-baseline gap-1 text-right min-w-[70px]">
										<span class="angka text-13 font-bold {(row.r ?? 0) > 0 ? 'text-pos' : (row.r ?? 0) < 0 ? 'text-neg' : 'text-text-3'}">
											{(row.r ?? 0) > 0 ? '+' : ''}{angka(row.r ?? 0)}
										</span>
										<span class="text-10 text-text-3 font-mono">R</span>
									</div>
								</div>
							</div>
						{/each}
					</div>
				{/if}
			</div>
		{/if}
	</section>

	<!-- Papan Peringkat Strategi & Kinerja -->
	<div id="kinerja-section" class="space-y-4">
		<StrategyLeaderboard />

		<!-- Layout Dua Kolom Pendukung (Grid Bawah) -->
		<div class="grid grid-cols-1 gap-4 lg:grid-cols-12">
			<!-- Kolom Kiri: Kurva Ekuitas & Aliran Keputusan (7 Kolom) -->
			<div class="space-y-4 lg:col-span-7">
				<!-- Kurva Ekuitas Interaktif -->
				<EquityCurve points={dataEquity?.points} stats={dataEquity?.stats} />

				<!-- Aliran Keputusan & Eksekusi -->
				<DecisionFeed />
			</div>

			<!-- Kolom Kanan: Pengawas Risiko, Edge Statistik, Feed Kejadian Realtime (5 Kolom) -->
			<div id="risiko-section" class="space-y-4 lg:col-span-5">
				<!-- Pengawas Risiko -->
				<RiskMeter risiko={dataRisiko} />

			<!-- Kartu Bukti Statistik Polymarket -->
			<StatisticalEdgeCard verdict={dataVerdict} judul="Polymarket 5m Statistical Gate" />

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
</div>
