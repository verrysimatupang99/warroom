<script lang="ts">
	// Ledger — konsolidasi seluruh catatan eksekusi lintas market + ekspor CSV.
	// Sumber: /api/v1/journal/trades (forex dari telemetri MT5, crypto dari paper trader).
	import { urlApi } from '$lib/api/client';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import Skeleton from '$lib/components/Skeleton.svelte';
	import ExportLedgerCsv from '$lib/components/ExportLedgerCsv.svelte';
	import PaperVsRealCard from '$lib/components/market/PaperVsRealCard.svelte';

	type Angka = number | null;
	interface Trade {
		iso?: string; symbol?: string; side?: string; market?: string;
		price_filled?: string; pnl_pct?: string; r?: Angka; slippage_pts?: string;
		currency?: string; cent_factor?: number; net_usc?: number; pnl_usd?: string | number;
		account?: string; ticket?: string;
	}
	let trades = $state<Trade[]>([]);
	let memuat = $state(true);
	let galat = $state<string | null>(null);
	let filter = $state<'all' | 'forex' | 'crypto'>('all');

	const PILIHAN = [
		{ nilai: 'all', label: 'Semua' },
		{ nilai: 'forex', label: 'Forex' },
		{ nilai: 'crypto', label: 'Crypto' }
	] as const;

	const terfilter = $derived(filter === 'all' ? trades : trades.filter((t) => t.market === filter));

	// Paginasi: 25 baris per halaman supaya halaman tak terlalu panjang.
	const PER_HALAMAN = 25;
	let halaman = $state(0);
	const totalHalaman = $derived(Math.max(1, Math.ceil(terfilter.length / PER_HALAMAN)));
	const terpaginasi = $derived(terfilter.slice(halaman * PER_HALAMAN, (halaman + 1) * PER_HALAMAN));
	// Ringkasan dari seluruh baris terfilter (bukan cuma halaman aktif).
	const ringkasan = $derived.by(() => {
		const menang = terfilter.filter((t) => {
			if (t.market === 'crypto') return (t.r ?? 0) > 0;
			if ((t.currency === 'USC' || t.account === '452009427') && t.net_usc != null) return Number(t.net_usc) > 0;
			if (t.pnl_usd != null && t.pnl_usd !== '') return Number(t.pnl_usd) > 0;
			return parseFloat(t.pnl_pct ?? '') > 0;
		}).length;
		const rugi = terfilter.filter((t) => {
			if (t.market === 'crypto') return (t.r ?? 0) < 0;
			if ((t.currency === 'USC' || t.account === '452009427') && t.net_usc != null) return Number(t.net_usc) < 0;
			if (t.pnl_usd != null && t.pnl_usd !== '') return Number(t.pnl_usd) < 0;
			return parseFloat(t.pnl_pct ?? '') < 0;
		}).length;
		const totalR = terfilter.reduce((a, t) => a + (t.market === 'crypto' && t.r != null ? t.r : 0), 0);
		const tuntas = menang + rugi;
		const wr = tuntas > 0 ? (menang / tuntas) * 100 : null;
		return { total: terfilter.length, menang, rugi, totalR, wr };
	});
	// Reset ke halaman 0 saat filter berubah.
	$effect(() => { void filter; halaman = 0; });

	async function muat() {
		memuat = true;
		galat = null;
		try {
			const r = await fetch(urlApi('/api/v1/journal/trades?market=all'), { credentials: 'include' });
			const isi = await r.json().catch(() => null);
			if (!r.ok) {
				galat = isi?.error?.message ?? isi?.detail ?? `HTTP ${r.status}`;
				return;
			}
			trades = isi?.closed ?? [];
		} catch (e) {
			galat = e instanceof Error ? e.message : 'gagal menghubungi API';
		} finally {
			memuat = false;
		}
	}

	function fmtWaktu(iso: string | undefined) {
		if (!iso) return '—';
		const d = new Date(iso);
		if (isNaN(d.getTime())) return iso;
		const bulan = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des'];
		const pad = (x: number) => String(x).padStart(2, '0');
		return `${pad(d.getDate())} ${bulan[d.getMonth()]} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
	}
	function hasil(t: Trade) {
		if (t.market === 'crypto') return t.r != null ? `${t.r > 0 ? '+' : ''}${t.r}R` : '—';
		const isCent = t.currency === 'USC' || t.account === '452009427';
		if (isCent) {
			const val = t.net_usc != null && String(t.net_usc) !== ''
				? Number(t.net_usc)
				: (t.pnl_usd != null && t.pnl_usd !== '' ? Number(t.pnl_usd) * 100 : null);
			if (val != null && !isNaN(val)) {
				const sign = val > 0 ? '+' : val < 0 ? '-' : '';
				const absVal = Math.abs(val);
				const usdNum = absVal / 100.0;
				const usdStr = usdNum.toFixed(2);
				const usdPart = usdStr === '0.00' && absVal > 0 ? '< $0.01' : `$${usdStr}`;
				return `${sign}${absVal.toFixed(2)} USC (${sign}${usdPart})`;
			}
		}
		if (t.pnl_usd != null && t.pnl_usd !== '') {
			const num = Number(t.pnl_usd);
			if (!isNaN(num)) {
				const sign = num > 0 ? '+' : num < 0 ? '-' : '';
				return `${sign}$${Math.abs(num).toFixed(2)}`;
			}
		}
		return t.pnl_pct || '—';
	}
	// Petakan trade ke bentuk yang diminta ExportLedgerCsv.
	const entriesCsv = $derived(
		terfilter.map((t) => ({
			closed_at: t.iso, pair: t.symbol, direction: t.side,
			entry: t.price_filled, r: t.r, note: t.market
		}))
	);

	void muat();
</script>

<svelte:head><title>Ledger | War Room</title></svelte:head>
<PageHeader
	eyebrow="War Room · Eksekusi"
	title="Ledger eksekusi"
	tag="LOKAL"
	description="Seluruh catatan eksekusi lintas market dalam satu buku besar: forex dari telemetri MT5, crypto dari paper trader. Bisa diekspor ke CSV untuk audit."
	terverifikasi={true}
	sumber="/api/v1/journal/trades"
>
	{#snippet action()}
		<ExportLedgerCsv pasar={filter} entries={entriesCsv} />
	{/snippet}
</PageHeader>

<!-- Paling atas: penjaga agar win-rate paper tidak dikira hasil uang nyata. -->
<div class="my-4">
	<PaperVsRealCard />
</div>

<div class="space-y-4">
	<div
		class="inline-flex flex-wrap gap-1 rounded-card border border-line bg-surface p-1"
		role="tablist"
		aria-label="Filter market"
	>
		{#each PILIHAN as p (p.nilai)}
			<button
				type="button"
				class="label-mikro transisi min-h-[34px] rounded-control border px-3 py-1 cursor-pointer {filter === p.nilai
					? 'border-accent/60 bg-surface-2 text-accent'
					: 'border-transparent text-text-3 hover:border-line hover:bg-surface-2/60 hover:text-text'}"
				aria-pressed={filter === p.nilai}
				onclick={() => (filter = p.nilai)}
			>{p.label}</button>
		{/each}
	</div>

	{#if memuat}
		<Skeleton baris={4} tinggi={44} />
	{:else if galat}
		<EmptyState judul="Gagal memuat ledger" pesan={galat} onulang={() => void muat()} />
	{:else if terfilter.length === 0}
		<EmptyState
			judul="Ledger kosong"
			pesan="Belum ada eksekusi tercatat untuk filter ini. Catatan muncul saat ada trade yang dilaporkan."
			onulang={() => void muat()}
		/>
	{:else}
		<div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
			<div class="kartu p-3.5">
				<span class="label-mikro block mb-1">Total eksekusi</span>
				<span class="text-20 font-bold text-text angka">{ringkasan.total}</span>
			</div>
			<div class="kartu p-3.5">
				<span class="label-mikro block mb-1">Menang / Rugi</span>
				<span class="text-20 font-bold angka"><span class="text-pos">{ringkasan.menang}</span> <span class="text-text-3">/</span> <span class="text-neg">{ringkasan.rugi}</span></span>
			</div>
			<div class="kartu p-3.5">
				<span class="label-mikro block mb-1">Win rate</span>
				<span class="text-20 font-bold text-text angka">{ringkasan.wr != null ? `${ringkasan.wr.toFixed(0)}%` : '—'}</span>
			</div>
			<div class="kartu p-3.5">
				<span class="label-mikro block mb-1">Total R (crypto)</span>
				<span class="text-20 font-bold angka {ringkasan.totalR >= 0 ? 'text-pos' : 'text-neg'}">{ringkasan.totalR > 0 ? '+' : ''}{ringkasan.totalR.toFixed(1)}R</span>
			</div>
		</div>

		<section class="kartu p-4">
			<div class="flex items-center justify-between mb-3 border-b border-line-soft pb-2.5">
				<h2 class="label-mikro text-text-2">Catatan eksekusi</h2>
				<span class="angka text-11 text-text-3">Halaman {halaman + 1} / {totalHalaman} · {terfilter.length} baris</span>
			</div>
			<div class="overflow-x-auto rounded-control border border-line bg-surface">
				<table class="w-full text-12 text-left border-collapse">
					<thead class="bg-surface-2 border-b border-line">
						<tr>
							<th class="px-2.5 py-2 label-mikro">Waktu</th>
							<th class="px-2.5 py-2 label-mikro">Market</th>
							<th class="px-2.5 py-2 label-mikro">Simbol</th>
							<th class="px-2.5 py-2 label-mikro">Sisi</th>
							<th class="px-2.5 py-2 label-mikro text-right">Harga</th>
							<th class="px-2.5 py-2 label-mikro text-right">Hasil</th>
							{#if filter === 'forex'}<th class="px-2.5 py-2 label-mikro text-right">Slip</th>{/if}
						</tr>
					</thead>
					<tbody class="divide-y divide-line-soft">
						{#each terpaginasi as t, i (t.ticket ?? (t.iso ? `${t.iso}-${t.symbol}-${i}` : i))}
							<tr class="hover:bg-surface-2/60">
								<td class="px-2.5 py-1.5 angka text-text-3 whitespace-nowrap">{fmtWaktu(t.iso)}</td>
								<td class="px-2.5 py-1.5 uppercase font-mono text-11 text-text-3">{t.market ?? '—'}</td>
								<td class="px-2.5 py-1.5 angka font-semibold text-text">{t.symbol ?? '—'}</td>
								<td class="px-2.5 py-1.5 font-mono text-11 text-text-2">{t.side ?? '—'}</td>
								<td class="px-2.5 py-1.5 text-right angka text-text">{t.price_filled ?? '—'}</td>
								<td class="px-2.5 py-1.5 text-right angka text-text">{hasil(t)}</td>
								{#if filter === 'forex'}<td class="px-2.5 py-1.5 text-right angka text-text-3">{t.slippage_pts || '—'}</td>{/if}
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
			{#if totalHalaman > 1}
				<div class="flex items-center justify-between mt-3 pt-3 border-t border-line-soft">
					<button type="button" class="h-8 rounded-control border border-line bg-surface-2 px-3 text-12 font-mono cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed {halaman === 0 ? 'text-text-3' : 'text-text hover:border-accent hover:text-accent'}" disabled={halaman === 0} onclick={() => (halaman = Math.max(0, halaman - 1))}>← Sebelumnya</button>
					<span class="angka text-11 text-text-3">{halaman * PER_HALAMAN + 1}–{Math.min((halaman + 1) * PER_HALAMAN, terfilter.length)} dari {terfilter.length}</span>
					<button type="button" class="h-8 rounded-control border border-line bg-surface-2 px-3 text-12 font-mono cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed {halaman >= totalHalaman - 1 ? 'text-text-3' : 'text-text hover:border-accent hover:text-accent'}" disabled={halaman >= totalHalaman - 1} onclick={() => (halaman = Math.min(totalHalaman - 1, halaman + 1))}>Berikutnya →</button>
				</div>
			{/if}
		</section>
	{/if}
</div>
