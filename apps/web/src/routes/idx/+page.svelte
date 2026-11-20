<script lang="ts">
	// IDX dengan sumber idx-edge (stock.arjum.com). Halaman ini menampilkan tiga hal
	// yang benar-benar tersedia: IHSG publik, ringkasan pasar (penggerak + blue chip),
	// dan pencarian saham. Yang belum ada tetap dinyatakan, bukan disembunyikan.
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { AREAS, SLUG_LAMA } from '$lib/nav';
	import { urlApi } from '$lib/api/client';
	import MarketShell from '$lib/components/MarketShell.svelte';
	import StrategyRunnerForm from '$lib/components/StrategyRunnerForm.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import Skeleton from '$lib/components/Skeleton.svelte';
	import BatasPasar from '$lib/components/BatasPasar.svelte';
	import RunningTrade from '$lib/components/market/RunningTrade.svelte';

	interface Candle { t: number; o: number; h: number; l: number; c: number; v: number }
	interface Pasar {
		symbol?: string; last?: number; open?: number; high?: number; low?: number;
		change_pct?: number; volume?: number; sumber?: string; candles?: Candle[];
	}
	interface Emiten {
		code?: string; last_price?: number; change?: number; change_pct?: number;
		freq?: number; lot?: number; value?: number; vwap?: number;
		data_ts?: string; market_label?: string; quote_age_ms?: number;
	}
	interface Ringkas {
		penggerak?: { gainers?: Emiten[]; losers?: Emiten[] };
		pemakaian?: { panggilan_hari_ini?: number; anggaran_harian?: number; sisa_perkiraan?: number };
		blue_chip?: { stocks?: Record<string, Emiten>; count?: number };
		sumber?: string; diambil?: string;
	}
	interface BrokerRow {
		broker_code?: string; broker_name?: string;
		bval?: number; bvol?: number; sval?: number; svol?: number;
		nval?: number; nvol?: number;
	}
	interface AkumSeries {
		broker_code?: string; broker_name?: string;
		points?: { date?: string; nval?: number; cum_nval?: number; bavg?: number; savg?: number }[];
	}
	interface ScreenerRow {
		stock_code?: string; stock_name?: string; bucket?: string;
		summary?: string; wr_event?: number; potential?: number; drawdown?: number; note?: string;
	}
	interface RiwayatRow {
		date?: string; open?: number; high?: number; low?: number; close?: number;
		change_pct?: number; volume?: number; value?: number; n_foreign?: number;
	}
	interface MusimanData {
		stock_code?: string; years?: string[];
		monthly_returns?: Record<string, Record<string, number | null>>;
	}

	let d = $state<Pasar | null>(null);
	let ringkas = $state<Ringkas | null>(null);
	let galat = $state<string | null>(null);
	let galatRingkas = $state<string | null>(null);
	let memuat = $state(true);

	let kueri = $state('');
	let hasilCari = $state<{ stock_code?: string; stock_name?: string }[]>([]);
	let detail = $state<Emiten | null>(null);
	let memuatCari = $state(false);

	// Sub-panel detail emiten (broker / akumulasi / analisa)
	let tabDetail = $state<'ringkasan' | 'broker' | 'akumulasi' | 'analisa'>('ringkasan');
	let memuatDetailExtra = $state(false);
	let galatDetailExtra = $state<string | null>(null);
	let brokerList = $state<BrokerRow[]>([]);
	let akumData = $state<{ start_date?: string; end_date?: string; series?: AkumSeries[] } | null>(null);
	let analisaTeks = $state<string | null>(null);

	// State tab Sinyal (Screener)
	let screenerData = $state<{ date?: string; rows?: ScreenerRow[] } | null>(null);
	let memuatScreener = $state(false);
	let galatScreener = $state<string | null>(null);

	// State tab Uji (Musiman & Riwayat Emiten)
	const KODE_POPULER = ['BBCA', 'BBRI', 'BMRI', 'TLKM', 'ASII'];
	let kodeUji = $state('BBCA');
	let musimanData = $state<MusimanData | null>(null);
	let riwayatRows = $state<RiwayatRow[]>([]);
	let memuatUji = $state(false);
	let galatUji = $state<string | null>(null);

	// Kalkulator Lot & Risiko Saham IDX (tab Eksekusi)
	let calcHargaBeli = $state(9500);
	let calcStopLoss = $state(9200);
	let calcTakeProfit = $state(10200);
	let calcLot = $state(10);
	const FEE_BELI = 0.0015; // 0.15%
	const FEE_JUAL = 0.0025; // 0.25%
	const calcHasil = $derived.by(() => {
		const lembar = Math.max(1, calcLot) * 100;
		const nilaiBeli = calcHargaBeli * lembar;
		const totalModal = nilaiBeli * (1 + FEE_BELI);
		const bePrice = calcHargaBeli * (1 + FEE_BELI) / (1 - FEE_JUAL);
		const nilaiSlNet = calcStopLoss * lembar * (1 - FEE_JUAL);
		const nilaiTpNet = calcTakeProfit * lembar * (1 - FEE_JUAL);
		const risikoRp = totalModal - nilaiSlNet;
		const profitRp = nilaiTpNet - totalModal;
		const rrr = risikoRp > 0 ? profitRp / risikoRp : 0;
		return { lembar, nilaiBeli, totalModal, bePrice, risikoRp, profitRp, rrr };
	});

	const area = AREAS.find((a) => a.kunci === 'idx')!;
	// Sub-nav standar (Ringkas/Sinyal/Uji/Eksekusi) — samakan ritme dgn crypto/forex.
	const sub = $derived.by(() => {
		const s = page.url.searchParams.get('sub') ?? 'ringkas';
		return SLUG_LAMA[s] ?? s;
	});

	onMount(async () => {
		const [p, r] = await Promise.allSettled([
			fetch(urlApi('/api/v1/idx/market'), { credentials: 'include' }),
			fetch(urlApi('/api/v1/idx-edge/ringkas'), { credentials: 'include' })
		]);
		if (p.status === 'fulfilled' && p.value.ok) d = await p.value.json();
		else galat = 'Sumber IHSG tidak mengembalikan data.';
		if (r.status === 'fulfilled' && r.value.ok) {
			const isi = await r.value.json();
			ringkas = isi?.hasil ?? null;
		} else if (r.status === 'fulfilled') {
			const isi = await r.value.json().catch(() => null);
			galatRingkas = isi?.error?.message ?? isi?.detail?.message ?? `HTTP ${r.value.status}`;
		} else {
			galatRingkas = 'Tidak bisa menghubungi API.';
		}
		memuat = false;
	});

	$effect(() => {
		if (sub === 'sinyal' && !screenerData && !memuatScreener && !galatScreener) {
			void muatScreener();
		} else if (sub === 'uji' && !musimanData && !memuatUji && !galatUji) {
			void muatUjiEmiten(kodeUji);
		}
	});

	async function muatScreener() {
		memuatScreener = true;
		galatScreener = null;
		try {
			const r = await fetch(urlApi('/api/v1/idx-edge/screener'), { credentials: 'include' });
			const isi = await r.json().catch(() => null);
			if (!r.ok) {
				galatScreener = isi?.detail?.message ?? isi?.error?.message ?? `HTTP ${r.status}`;
			} else {
				screenerData = isi?.hasil ?? null;
			}
		} catch (e) {
			galatScreener = e instanceof Error ? e.message : 'Gagal menghubungi API screener';
		}
		memuatScreener = false;
	}

	async function muatUjiEmiten(kode: string) {
		const bersih = kode.trim().toUpperCase();
		if (!bersih) return;
		kodeUji = bersih;
		memuatUji = true;
		galatUji = null;
		const [m, rw] = await Promise.allSettled([
			fetch(urlApi(`/api/v1/idx-edge/musiman/${encodeURIComponent(bersih)}`), { credentials: 'include' }),
			fetch(urlApi(`/api/v1/idx-edge/riwayat/${encodeURIComponent(bersih)}?limit=30`), { credentials: 'include' })
		]);
		if (m.status === 'fulfilled' && m.value.ok) {
			const isi = await m.value.json().catch(() => null);
			musimanData = isi?.hasil ?? null;
		} else if (m.status === 'fulfilled') {
			const isi = await m.value.json().catch(() => null);
			galatUji = isi?.detail?.message ?? isi?.error?.message ?? `HTTP ${m.value.status}`;
		}
		if (rw.status === 'fulfilled' && rw.value.ok) {
			const isi = await rw.value.json().catch(() => null);
			riwayatRows = isi?.hasil?.rows ?? [];
		}
		memuatUji = false;
	}

	async function cari() {
		const q = kueri.trim();
		if (q.length < 2) return;
		memuatCari = true;
		detail = null;
		try {
			const r = await fetch(urlApi(`/api/v1/idx-edge/cari?q=${encodeURIComponent(q)}`), {
				credentials: 'include'
			});
			const isi = await r.json().catch(() => null);
			hasilCari = r.ok ? (isi?.hasil ?? []) : [];
		} catch {
			hasilCari = [];
		}
		memuatCari = false;
	}

	async function buka(kode?: string) {
		if (!kode) return;
		tabDetail = 'ringkasan';
		brokerList = [];
		akumData = null;
		analisaTeks = null;
		galatDetailExtra = null;
		try {
			const r = await fetch(urlApi(`/api/v1/idx-edge/harga/${encodeURIComponent(kode)}`), { credentials: 'include' });
			const isi = await r.json().catch(() => null);
			detail = r.ok ? (isi?.hasil ?? null) : null;
		} catch {
			detail = null;
		}
	}

	async function pilihTabDetail(t: 'ringkasan' | 'broker' | 'akumulasi' | 'analisa') {
		tabDetail = t;
		const kode = detail?.code;
		if (!kode || t === 'ringkasan') return;
		if (t === 'broker' && brokerList.length > 0) return;
		if (t === 'akumulasi' && akumData) return;
		if (t === 'analisa' && analisaTeks) return;

		memuatDetailExtra = true;
		galatDetailExtra = null;
		try {
			const jalur =
				t === 'broker'
					? `/api/v1/idx-edge/broker/${encodeURIComponent(kode)}`
					: t === 'akumulasi'
						? `/api/v1/idx-edge/akumulasi/${encodeURIComponent(kode)}`
						: `/api/v1/idx-edge/analisa/${encodeURIComponent(kode)}`;
			const r = await fetch(urlApi(jalur), { credentials: 'include' });
			const isi = await r.json().catch(() => null);
			if (!r.ok) {
				galatDetailExtra = isi?.detail?.message ?? isi?.error?.message ?? `HTTP ${r.status}`;
			} else {
				const h = isi?.hasil;
				if (t === 'broker') brokerList = h?.brokers ?? [];
				else if (t === 'akumulasi') akumData = h ?? null;
				else if (t === 'analisa') analisaTeks = h?.output ?? JSON.stringify(h, null, 2);
			}
		} catch (e) {
			galatDetailExtra = e instanceof Error ? e.message : 'Gagal memuat data tambahan';
		}
		memuatDetailExtra = false;
	}

	function angka(v: number | undefined, digit = 2) {
		return v == null ? '—' : v.toLocaleString('id-ID', { maximumFractionDigits: digit });
	}
	function rupiah(v: number | undefined) {
		if (v == null) return '—';
		if (v >= 1e12) return `${(v / 1e12).toFixed(2)} T`;
		if (v >= 1e9) return `${(v / 1e9).toFixed(1)} M`;
		return `${(v / 1e6).toFixed(0)} jt`;
	}
	function tanggal(t: number) {
		return new Date(t).toLocaleDateString('id-ID', { day: '2-digit', month: 'short' });
	}
</script>

<svelte:head><title>IDX | War Room</title></svelte:head>

<MarketShell
	{area}
	aktif={sub}
	judul="Saham IDX"
	tag="AKTIF"
	deskripsi="IHSG dari sumber publik, plus data per emiten dari idx-edge: harga, penggerak, ringkasan broker, dan laporan keuangan."
	terverifikasi={true}
	sumber="yahoo:jkse + idx-edge:stock.arjum.com"
>
<div class="space-y-4">
	{#if sub === 'ringkas'}
	{#if memuat}
		<Skeleton baris={5} tinggi={44} />
	{:else}
		<!-- IHSG -->
		{#if d}
			<section class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
				<div class="rounded-card border border-line bg-surface p-4">
					<div class="label-mikro font-mono text-text-3">IHSG</div>
					<div class="mt-1 font-mono text-17 font-bold text-text">{angka(d.last)}</div>
					<div class="mt-1 text-11 text-text-3">pembukaan {angka(d.open)}</div>
				</div>
				<div class="rounded-card border border-line bg-surface p-4">
					<div class="label-mikro font-mono text-text-3">PERUBAHAN</div>
					<div class="mt-1 font-mono text-17 font-bold"
						class:text-neg={(d.change_pct ?? 0) < 0} class:text-pos={(d.change_pct ?? 0) > 0}>
						{(d.change_pct ?? 0).toFixed(2)} %
					</div>
					<div class="mt-1 text-11 text-text-3">terhadap penutupan sebelumnya</div>
				</div>
				<div class="rounded-card border border-line bg-surface p-4">
					<div class="label-mikro font-mono text-text-3">RENTANG HARI INI</div>
					<div class="mt-1 font-mono text-14 font-bold text-text">{angka(d.low)} – {angka(d.high)}</div>
				</div>
				<div class="rounded-card border border-line bg-surface p-4">
					<div class="label-mikro font-mono text-text-3">VOLUME</div>
					<div class="mt-1 font-mono text-17 font-bold text-text">
						{d.volume ? `${angka(d.volume / 1_000_000, 1)} jt` : '—'}
					</div>
					{#if !d.volume}
						<div class="mt-1 text-11 text-text-3">sumber tidak mengirim volume</div>
					{/if}
				</div>
			</section>
		{:else if galat}
			<EmptyState judul="IHSG tidak tersedia" pesan={galat} ringkas={true} />
		{/if}

		<!-- Cari emiten -->
		<section class="rounded-card border border-line bg-surface p-4">
			<h2 class="text-13 font-bold text-text">Cari emiten</h2>
			<form class="mt-2 flex gap-2" onsubmit={(e) => { e.preventDefault(); void cari(); }}>
				<input
					type="text" bind:value={kueri} placeholder="BBCA, BBRI, TLKM…" maxlength="12"
					class="min-h-[44px] flex-1 rounded-control border border-line bg-surface-2 px-3 font-mono text-12 uppercase text-text"
				/>
				<button
					type="submit" disabled={memuatCari || kueri.trim().length < 2}
					class="min-h-[44px] rounded-control border border-line px-3 font-mono text-11 text-text-2 hover:border-accent hover:text-accent disabled:opacity-40"
				>
					{memuatCari ? 'mencari…' : 'cari'}
				</button>
			</form>

			{#if hasilCari.length > 0}
				<ul class="mt-2 divide-y divide-line-soft">
					{#each hasilCari as s (s.stock_code)}
						<li>
							<button
								type="button"
								class="flex w-full items-center justify-between gap-2 py-2 text-left hover:text-accent"
								onclick={() => buka(s.stock_code)}
							>
								<span class="font-mono text-12 font-bold text-text">{s.stock_code}</span>
								<span class="truncate text-11 text-text-3">{s.stock_name}</span>
							</button>
						</li>
					{/each}
				</ul>
			{/if}

			{#if detail}
				<div class="mt-3 rounded border border-line bg-surface-2 p-3">
					<div class="flex flex-wrap items-center justify-between gap-2">
						<div class="flex flex-wrap items-baseline gap-2">
							<span class="font-mono text-14 font-bold text-text">{detail.code}</span>
							<span class="font-mono text-14" class:text-pos={(detail.change_pct ?? 0) > 0} class:text-neg={(detail.change_pct ?? 0) < 0}>
								{angka(detail.last_price)} ({detail.change_pct ?? 0} %)
							</span>
							<span class="font-mono text-10 text-text-3">{detail.market_label ?? ''}</span>
						</div>
						<div class="flex flex-wrap gap-1 font-mono text-10">
							{#each (['ringkasan', 'broker', 'akumulasi', 'analisa'] as const) as t}
								<button
									type="button"
									class="rounded border px-2 py-1 uppercase {tabDetail === t ? 'border-accent bg-accent/15 text-accent font-bold' : 'border-line text-text-3 hover:text-text'}"
									onclick={() => void pilihTabDetail(t)}
								>
									{t}
								</button>
							{/each}
						</div>
					</div>

					<dl class="mt-2 grid gap-2 text-11 sm:grid-cols-4">
						<div><dt class="text-text-3">Frekuensi</dt><dd class="font-mono text-text">{angka(detail.freq, 0)}</dd></div>
						<div><dt class="text-text-3">Lot</dt><dd class="font-mono text-text">{angka(detail.lot, 0)}</dd></div>
						<div><dt class="text-text-3">Nilai</dt><dd class="font-mono text-text">{rupiah(detail.value)}</dd></div>
						<div><dt class="text-text-3">VWAP</dt><dd class="font-mono text-text">{angka(detail.vwap)}</dd></div>
					</dl>

					{#if tabDetail !== 'ringkasan'}
						<div class="mt-3 border-t border-line-soft pt-3">
							{#if memuatDetailExtra}
								<p class="text-11 text-text-3 font-mono">memuat {tabDetail} {detail.code}…</p>
							{:else if galatDetailExtra}
								<p class="text-11 text-neg">{galatDetailExtra}</p>
							{:else if tabDetail === 'broker'}
								{#if brokerList.length === 0}
									<p class="text-11 text-text-3">Data ringkasan broker belum tersedia untuk {detail.code}.</p>
								{:else}
									<div class="overflow-x-auto">
										<table class="w-full text-11 text-left">
											<thead class="border-b border-line text-10 text-text-3">
												<tr>
													<th class="px-2 py-1">Broker</th>
													<th class="px-2 py-1 text-right">Beli</th>
													<th class="px-2 py-1 text-right">Jual</th>
													<th class="px-2 py-1 text-right">Net</th>
												</tr>
											</thead>
											<tbody class="divide-y divide-line-soft">
												{#each brokerList.slice(0, 8) as b (b.broker_code)}
													<tr>
														<td class="px-2 py-1 font-mono text-text">
															<span class="font-bold">{b.broker_code}</span>
															<span class="text-10 text-text-3 ml-1">{b.broker_name ?? ''}</span>
														</td>
														<td class="px-2 py-1 text-right font-mono text-pos">{rupiah(b.bval)}</td>
														<td class="px-2 py-1 text-right font-mono text-neg">{rupiah(b.sval)}</td>
														<td class="px-2 py-1 text-right font-mono font-bold {(b.nval ?? 0) >= 0 ? 'text-pos' : 'text-neg'}">
															{(b.nval ?? 0) >= 0 ? '+' : '−'}{rupiah(Math.abs(b.nval ?? 0))}
														</td>
													</tr>
												{/each}
											</tbody>
										</table>
									</div>
								{/if}
							{:else if tabDetail === 'akumulasi'}
								{#if !akumData?.series?.length}
									<p class="text-11 text-text-3">Data akumulasi broker belum tersedia untuk {detail.code}.</p>
								{:else}
									<p class="text-10 text-text-3 font-mono mb-2">
										Periode: {akumData.start_date ?? '—'} s/d {akumData.end_date ?? '—'}
									</p>
									<div class="grid gap-2 sm:grid-cols-2">
										{#each akumData.series.slice(0, 6) as sr (sr.broker_code)}
											{@const titikAkhir = sr.points?.[sr.points.length - 1]}
											<div class="rounded border border-line bg-surface p-2 text-11">
												<div class="flex items-center justify-between font-mono">
													<span class="font-bold text-text">{sr.broker_code} <span class="font-normal text-10 text-text-3">{sr.broker_name ?? ''}</span></span>
													<span class="font-bold {(titikAkhir?.cum_nval ?? 0) >= 0 ? 'text-pos' : 'text-neg'}">
														{(titikAkhir?.cum_nval ?? 0) >= 0 ? '+' : '−'}{rupiah(Math.abs(titikAkhir?.cum_nval ?? 0))}
													</span>
												</div>
												{#if titikAkhir}
													<div class="mt-1 flex justify-between font-mono text-10 text-text-3">
														<span>Avg Beli: {angka(titikAkhir.bavg, 0)}</span>
														<span>Avg Jual: {angka(titikAkhir.savg, 0)}</span>
													</div>
												{/if}
											</div>
										{/each}
									</div>
								{/if}
							{:else if tabDetail === 'analisa'}
								{#if !analisaTeks}
									<p class="text-11 text-text-3">Analisa belum tersedia untuk {detail.code}.</p>
								{:else}
									<pre class="whitespace-pre-wrap font-mono text-11 leading-relaxed text-text-2 bg-surface p-3 rounded border border-line max-h-72 overflow-y-auto">{analisaTeks}</pre>
								{/if}
							{/if}
						</div>
					{/if}
				</div>
			{/if}
		</section>

		<RunningTrade />

		<!-- Penggerak -->
		{#if ringkas?.penggerak?.gainers?.length}
			<section class="rounded-card border border-line bg-surface p-4">
				<div class="flex flex-wrap items-center justify-between gap-2">
					<h2 class="text-13 font-bold text-text">Penggerak hari ini</h2>
					<span class="font-mono text-10 text-text-3">idx-edge · {ringkas.diambil?.slice(11, 16) ?? ''} WIB</span>
				</div>
				<div class="mt-2 grid gap-3 sm:grid-cols-2">
					<div>
						<div class="label-mikro font-mono text-pos">NAIK</div>
						<ul class="mt-1 divide-y divide-line-soft">
							{#each (ringkas.penggerak.gainers ?? []).slice(0, 5) as g (g.code)}
								<li class="flex items-center justify-between py-1 text-11">
									<button type="button" class="font-mono text-text hover:text-accent" onclick={() => buka(g.code)}>{g.code}</button>
									<span class="font-mono text-pos">{angka(g.last_price)} · +{angka(g.change_pct)}%</span>
								</li>
							{/each}
						</ul>
					</div>
					<div>
						<div class="label-mikro font-mono text-neg">TURUN</div>
						<ul class="mt-1 divide-y divide-line-soft">
							{#each (ringkas.penggerak.losers ?? []).slice(0, 5) as g (g.code)}
								<li class="flex items-center justify-between py-1 text-11">
									<button type="button" class="font-mono text-text hover:text-accent" onclick={() => buka(g.code)}>{g.code}</button>
									<span class="font-mono text-neg">{angka(g.last_price)} · {angka(g.change_pct)}%</span>
								</li>
							{/each}
						</ul>
					</div>
				</div>
			</section>
		{:else if galatRingkas}
			<section class="rounded-card border border-line bg-surface p-4">
				<h2 class="text-13 font-bold text-text">Penggerak hari ini</h2>
				<p class="mt-1 text-11 text-text-3">Sumber idx-edge belum bisa dipakai: {galatRingkas}</p>
			</section>
		{/if}

		<!-- Blue chip -->
		{#if ringkas?.blue_chip?.stocks}
			<section class="rounded-card border border-line bg-surface p-4">
				<div class="flex flex-wrap items-center justify-between gap-2">
					<h2 class="text-13 font-bold text-text">Blue chip</h2>
					<span class="text-10 text-text-3">Klik kode untuk membuka broker & analisa</span>
				</div>
				<div class="mt-2 overflow-x-auto">
					<table class="w-full text-11 text-left">
						<thead class="border-b border-line text-10 text-text-3">
							<tr>
								<th class="px-2 py-1.5">Kode</th>
								<th class="px-2 py-1.5 text-right">Harga</th>
								<th class="px-2 py-1.5 text-right">Perubahan</th>
								<th class="px-2 py-1.5 text-right">Nilai</th>
								<th class="px-2 py-1.5 text-right">VWAP</th>
							</tr>
						</thead>
						<tbody class="divide-y divide-line-soft">
							{#each Object.values(ringkas.blue_chip.stocks) as s (s.code)}
								<tr class="hover:bg-surface-2/60 cursor-pointer" onclick={() => void buka(s.code)}>
									<td class="px-2 py-1.5 font-mono font-bold text-accent underline">{s.code}</td>
									<td class="px-2 py-1.5 text-right font-mono text-text">{angka(s.last_price)}</td>
									<td class="px-2 py-1.5 text-right font-mono" class:text-pos={(s.change_pct ?? 0) > 0} class:text-neg={(s.change_pct ?? 0) < 0}>
										{angka(s.change_pct)} %
									</td>
									<td class="px-2 py-1.5 text-right font-mono text-text-2">{rupiah(s.value)}</td>
									<td class="px-2 py-1.5 text-right font-mono text-text-3">{angka(s.vwap)}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</section>
		{/if}

		<!-- Candle -->
		{#if d?.candles?.length}
			<section class="rounded-card border border-line bg-surface p-4">
				<h2 class="text-13 font-bold text-text">Candle harian IHSG</h2>
				<div class="mt-2 overflow-x-auto">
					<table class="w-full text-11 text-left">
						<thead class="border-b border-line text-10 text-text-3">
							<tr>
								<th class="px-2 py-1.5">Tanggal</th>
								<th class="px-2 py-1.5 text-right">Open</th>
								<th class="px-2 py-1.5 text-right">High</th>
								<th class="px-2 py-1.5 text-right">Low</th>
								<th class="px-2 py-1.5 text-right">Close</th>
							</tr>
						</thead>
						<tbody class="divide-y divide-line-soft">
							{#each (d.candles ?? []).slice(-15).reverse() as c (c.t)}
								<tr class="hover:bg-surface-2/60">
									<td class="px-2 py-1.5 font-mono text-text-3">{tanggal(c.t)}</td>
									<td class="px-2 py-1.5 text-right font-mono text-text-2">{angka(c.o)}</td>
									<td class="px-2 py-1.5 text-right font-mono text-pos">{angka(c.h)}</td>
									<td class="px-2 py-1.5 text-right font-mono text-neg">{angka(c.l)}</td>
									<td class="px-2 py-1.5 text-right font-mono font-bold text-text">{angka(c.c)}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</section>
		{/if}

		<!-- Kuota & Batas jujur -->
		{#if ringkas?.pemakaian}
			<section class="rounded-card border border-line bg-surface p-4">
				<h2 class="text-13 font-bold text-text">Kuota API idx-edge</h2>
				<div class="mt-2 rounded border border-line bg-surface-2 p-2">
					<div class="flex flex-wrap items-baseline gap-x-3 gap-y-1 font-mono text-11">
						<span class="text-text-3">Panggilan keluar hari ini</span>
						<span class="text-text font-bold">{ringkas.pemakaian.panggilan_hari_ini ?? 0}</span>
						<span class="text-text-3">/ anggaran {ringkas.pemakaian.anggaran_harian ?? 0}</span>
						<span class="text-text-3">· sisa ± {ringkas.pemakaian.sisa_perkiraan ?? 0}</span>
					</div>
					<p class="mt-1 text-10 leading-relaxed text-text-3">
						Dihitung sendiri dari panggilan keluar. Sisa kuota resmi hanya terlihat di dashboard
						arjum karena endpoint usage menolak API key.
					</p>
				</div>
			</section>
		{/if}
		<BatasPasar market="idx" />
	{/if}

	{:else if sub === 'sinyal'}
		<div class="space-y-4">
			<section class="rounded-card border border-line bg-surface p-4">
				<div class="flex flex-wrap items-center justify-between gap-2">
					<div>
						<h2 class="text-13 font-bold text-text">Screener & Saringan Saham IDX</h2>
						<p class="mt-0.5 text-11 text-text-3">
							Saringan kandidat harian dari idx-edge (gabungan aliran broker, volume, dan teknikal). Ini adalah data saringan riset, bukan perintah beli otomatis.
						</p>
					</div>
					<span class="font-mono text-10 text-text-3">{screenerData?.date ?? 'idx-edge'}</span>
				</div>

				{#if memuatScreener}
					<div class="mt-3"><Skeleton baris={4} tinggi={36} /></div>
				{:else if galatScreener}
					<div class="mt-3">
						<EmptyState judul="Screener belum tersedia" pesan={galatScreener} onulang={() => void muatScreener()} ringkas={true} />
					</div>
				{:else if !screenerData?.rows?.length}
					<div class="mt-3">
						<EmptyState judul="Belum ada kandidat screener" pesan="Sumber idx-edge belum mengembalikan daftar saringan untuk hari ini." ringkas={true} />
					</div>
				{:else}
					<div class="mt-3 overflow-x-auto">
						<table class="w-full text-11 text-left">
							<thead class="border-b border-line text-10 text-text-3">
								<tr>
									<th class="px-2 py-1.5">Kode</th>
									<th class="px-2 py-1.5">Kategori</th>
									<th class="px-2 py-1.5 text-right">WR Event</th>
									<th class="px-2 py-1.5 text-right">Potensi</th>
									<th class="px-2 py-1.5 text-right">Risiko DD</th>
									<th class="px-2 py-1.5">Catatan & Ringkasan</th>
								</tr>
							</thead>
							<tbody class="divide-y divide-line-soft">
								{#each screenerData.rows as r (r.stock_code)}
									<tr class="hover:bg-surface-2/60">
										<td class="px-2 py-1.5 font-mono">
											<div class="font-bold text-text">{r.stock_code}</div>
											<div class="text-10 text-text-3 truncate max-w-[160px]">{r.stock_name ?? ''}</div>
										</td>
										<td class="px-2 py-1.5 font-mono text-10 text-text-2">{r.bucket ?? '—'}</td>
										<td class="px-2 py-1.5 text-right font-mono text-text">
											{r.wr_event != null ? `${r.wr_event}%` : '—'}
										</td>
										<td class="px-2 py-1.5 text-right font-mono text-pos">
											{r.potential != null ? `+${r.potential}%` : '—'}
										</td>
										<td class="px-2 py-1.5 text-right font-mono text-neg">
											{r.drawdown != null ? `${r.drawdown}%` : '—'}
										</td>
										<td class="px-2 py-1.5 text-11 text-text-2">
											<div>{r.summary ?? '—'}</div>
											{#if r.note}
												<div class="text-10 font-mono text-text-3 mt-0.5">{r.note}</div>
											{/if}
										</td>
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				{/if}
			</section>
		</div>
	{:else if sub === 'uji'}
		<StrategyRunnerForm market="idx" defaultSymbol="BBCA.JK" />
		<div class="space-y-4">
			<section class="rounded-card border border-line bg-surface p-4">
				<div class="flex flex-wrap items-center justify-between gap-2">
					<div>
						<h2 class="text-13 font-bold text-text">Uji Musiman (Seasonality) & Riwayat Emiten</h2>
						<p class="mt-0.5 text-11 text-text-3">
							Statistik imbal hasil bulanan historis dan riwayat harian emiten dari idx-edge.
						</p>
					</div>
					<div class="flex flex-wrap items-center gap-1.5 font-mono text-11">
						{#each KODE_POPULER as kp (kp)}
							<button
								type="button"
								class="rounded border px-2.5 py-1 {kodeUji === kp ? 'border-accent bg-accent/15 text-accent font-bold' : 'border-line text-text-3 hover:text-text'}"
								onclick={() => void muatUjiEmiten(kp)}
							>
								{kp}
							</button>
						{/each}
					</div>
				</div>

				{#if memuatUji}
					<div class="mt-3"><Skeleton baris={4} tinggi={36} /></div>
				{:else if galatUji}
					<div class="mt-3">
						<EmptyState judul="Data uji emiten belum tersedia" pesan={galatUji} onulang={() => void muatUjiEmiten(kodeUji)} ringkas={true} />
					</div>
				{:else}
					{#if musimanData?.monthly_returns && musimanData.years}
						<div class="mt-3 overflow-x-auto">
							<h3 class="text-12 font-bold text-text mb-2">Return Bulanan {musimanData.stock_code ?? kodeUji} (%)</h3>
							<table class="w-full text-11 text-left font-mono">
								<thead class="border-b border-line text-10 text-text-3">
									<tr>
										<th class="px-2 py-1">Bulan</th>
										{#each musimanData.years as th (th)}
											<th class="px-2 py-1 text-right">{th}</th>
										{/each}
									</tr>
								</thead>
								<tbody class="divide-y divide-line-soft">
									{#each Object.entries(musimanData.monthly_returns) as [bln, perTahun] (bln)}
										<tr>
											<td class="px-2 py-1 font-bold text-text">{bln}</td>
											{#each musimanData.years as th (th)}
												{@const val = perTahun?.[th]}
												<td
													class="px-2 py-1 text-right"
													class:text-pos={(val ?? 0) > 0}
													class:text-neg={(val ?? 0) < 0}
													class:text-text-3={val == null || val === 0}
												>
													{val == null ? '—' : `${val > 0 ? '+' : ''}${val.toFixed(1)}%`}
												</td>
											{/each}
										</tr>
									{/each}
								</tbody>
							</table>
						</div>
					{/if}

					{#if riwayatRows.length > 0}
						<div class="mt-4 border-t border-line-soft pt-3 overflow-x-auto">
							<h3 class="text-12 font-bold text-text mb-2">Riwayat Harian & Aliran Asing ({kodeUji})</h3>
							<table class="w-full text-11 text-left font-mono">
								<thead class="border-b border-line text-10 text-text-3">
									<tr>
										<th class="px-2 py-1">Tanggal</th>
										<th class="px-2 py-1 text-right">Close</th>
										<th class="px-2 py-1 text-right">Perubahan</th>
										<th class="px-2 py-1 text-right">Nilai</th>
										<th class="px-2 py-1 text-right">Net Asing</th>
									</tr>
								</thead>
								<tbody class="divide-y divide-line-soft">
									{#each riwayatRows.slice(0, 15) as rw (rw.date)}
										<tr>
											<td class="px-2 py-1 text-text-3">{rw.date}</td>
											<td class="px-2 py-1 text-right font-bold text-text">{angka(rw.close, 0)}</td>
											<td class="px-2 py-1 text-right" class:text-pos={(rw.change_pct ?? 0) > 0} class:text-neg={(rw.change_pct ?? 0) < 0}>
												{(rw.change_pct ?? 0) > 0 ? '+' : ''}{angka(rw.change_pct)}%
											</td>
											<td class="px-2 py-1 text-right text-text-2">{rupiah(rw.value)}</td>
											<td class="px-2 py-1 text-right {(rw.n_foreign ?? 0) >= 0 ? 'text-pos' : 'text-neg'}">
												{rw.n_foreign == null ? '—' : `${rw.n_foreign >= 0 ? '+' : '−'}${rupiah(Math.abs(rw.n_foreign))}`}
											</td>
										</tr>
									{/each}
								</tbody>
							</table>
						</div>
					{/if}
				{/if}
			</section>
		</div>
	{:else if sub === 'eksekusi'}
		<div class="space-y-4">
			<div class="rounded-card border border-warn/30 bg-warn/10 p-3 text-11 text-text-2">
				<strong class="text-warn">Mode Riset &amp; Kalkulasi Manual:</strong> Routing order otomatis ke sekuritas IDX belum diaktifkan. Gunakan kalkulator di bawah untuk menghitung ukuran lot, fee transaksi (0,15% beli / 0,25% jual), dan Risk-to-Reward sebelum eksekusi manual di aplikasi sekuritas.
			</div>

			<section class="rounded-card border border-line bg-surface p-4 space-y-4">
				<div class="flex flex-wrap items-center justify-between gap-2">
					<h2 class="text-13 font-bold text-text">Kalkulator Lot, Risiko &amp; Biaya Saham IDX</h2>
					<span class="font-mono text-10 text-text-3">1 Lot = 100 Lembar · Fee 0,15% / 0,25%</span>
				</div>

				<div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 font-mono text-12">
					<label class="block space-y-1">
						<span class="text-10 text-text-3">HARGA BELI (Rp)</span>
						<input type="number" min="50" step="25" bind:value={calcHargaBeli} class="w-full rounded-control border border-line bg-surface-2 px-3 py-2 text-text" />
					</label>
					<label class="block space-y-1">
						<span class="text-10 text-text-3">STOP LOSS (Rp)</span>
						<input type="number" min="50" step="25" bind:value={calcStopLoss} class="w-full rounded-control border border-line bg-surface-2 px-3 py-2 text-neg" />
					</label>
					<label class="block space-y-1">
						<span class="text-10 text-text-3">TARGET TP (Rp)</span>
						<input type="number" min="50" step="25" bind:value={calcTakeProfit} class="w-full rounded-control border border-line bg-surface-2 px-3 py-2 text-pos" />
					</label>
					<label class="block space-y-1">
						<span class="text-10 text-text-3">JUMLAH LOT</span>
						<input type="number" min="1" step="1" bind:value={calcLot} class="w-full rounded-control border border-line bg-surface-2 px-3 py-2 text-text" />
					</label>
				</div>

				<div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 font-mono">
					<div class="rounded-lg border border-line-soft bg-surface-2 p-3">
						<span class="text-10 text-text-3 block">MODAL + FEE BELI</span>
						<span class="text-14 font-bold text-text">Rp {Math.round(calcHasil.totalModal).toLocaleString('id-ID')}</span>
						<span class="text-10 text-text-3 block">{calcHasil.lembar.toLocaleString('id-ID')} lembar</span>
					</div>
					<div class="rounded-lg border border-line-soft bg-surface-2 p-3">
						<span class="text-10 text-text-3 block">HARGA BREAK-EVEN</span>
						<span class="text-14 font-bold text-accent">Rp {Math.ceil(calcHasil.bePrice).toLocaleString('id-ID')}</span>
						<span class="text-10 text-text-3 block">+{(((calcHasil.bePrice / Math.max(1, calcHargaBeli)) - 1) * 100).toFixed(2)}% dari entry</span>
					</div>
					<div class="rounded-lg border border-line-soft bg-surface-2 p-3">
						<span class="text-10 text-text-3 block">RISIKO BERSIH (SL)</span>
						<span class="text-14 font-bold text-neg">-Rp {Math.round(calcHasil.risikoRp).toLocaleString('id-ID')}</span>
						<span class="text-10 text-text-3 block">Termasuk fee beli + jual</span>
					</div>
					<div class="rounded-lg border border-line-soft bg-surface-2 p-3">
						<span class="text-10 text-text-3 block">POTENSI PROFIT (TP)</span>
						<span class="text-14 font-bold text-pos">+Rp {Math.round(calcHasil.profitRp).toLocaleString('id-ID')}</span>
						<span class="text-10 text-text-3 block">RRR: {calcHasil.rrr.toFixed(2)} : 1</span>
					</div>
				</div>
			</section>
		</div>
	{/if}
</div>
</MarketShell>
