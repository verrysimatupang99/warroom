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
		const menang = terfilter.filter((t) => (t.market === 'crypto' ? (t.r ?? 0) > 0 : parseFloat(t.pnl_pct ?? '') > 0)).length;
		const rugi = terfilter.filter((t) => (t.market === 'crypto' ? (t.r ?? 0) < 0 : parseFloat(t.pnl_pct ?? '') < 0)).length;
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
<div class="mb-4">
	<PaperVsRealCard />
</div>

<div class="space-y-4">
	<div class="flex flex-wrap gap-1" role="tablist" aria-label="Filter market">
		{#each PILIHAN as p (p.nilai)}
			<button
				type="button"
				class="min-h-[44px] rounded-control border px-3 py-1.5 text-12 font-mono transition-colors cursor-pointer {filter === p.nilai ? 'border-accent text-accent bg-surface-2' : 'border-line text-text-3 hover:text-text'}"
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
			<div class="rounded-card border border-line bg-surface p-3">
				<span class="text-11 text-text-3 block mb-0.5">Total eksekusi</span>
				<span class="text-lg font-bold text-text font-mono">{ringkasan.total}</span>
			</div>
			<div class="rounded-card border border-line bg-surface p-3">
				<span class="text-11 text-text-3 block mb-0.5">Menang / Rugi</span>
				<span class="text-lg font-bold font-mono"><span class="text-pos">{ringkasan.menang}</span> / <span class="text-neg">{ringkasan.rugi}</span></span>
			</div>
			<div class="rounded-card border border-line bg-surface p-3">
				<span class="text-11 text-text-3 block mb-0.5">Win rate</span>
				<span class="text-lg font-bold text-text font-mono">{ringkasan.wr != null ? `${ringkasan.wr.toFixed(0)}%` : '—'}</span>
			</div>
			<div class="rounded-card border border-line bg-surface p-3">
				<span class="text-11 text-text-3 block mb-0.5">Total R (crypto)</span>
				<span class="text-lg font-bold font-mono {ringkasan.totalR >= 0 ? 'text-pos' : 'text-neg'}">{ringkasan.totalR > 0 ? '+' : ''}{ringkasan.totalR.toFixed(1)}R</span>
			</div>
		</div>

		<section class="rounded-card border border-line bg-surface p-4">
			<div class="flex items-center justify-between mb-2">
				<h2 class="text-13 font-bold text-text">Catatan eksekusi</h2>
				<span class="font-mono text-11 text-text-3">Halaman {halaman + 1} / {totalHalaman} · {terfilter.length} baris</span>
			</div>
			<div class="overflow-x-auto">
				<table class="w-full text-11 text-left">
					<thead class="border-b border-line text-10 text-text-3">
						<tr>
							<th class="px-2 py-1.5">Waktu</th>
							<th class="px-2 py-1.5">Market</th>
							<th class="px-2 py-1.5">Simbol</th>
							<th class="px-2 py-1.5">Sisi</th>
							<th class="px-2 py-1.5 text-right">Harga</th>
							<th class="px-2 py-1.5 text-right">Hasil</th>
							{#if filter === 'forex'}<th class="px-2 py-1.5 text-right">Slip</th>{/if}
						</tr>
					</thead>
					<tbody class="divide-y divide-line-soft">
						{#each terpaginasi as t, i (i)}
							<tr class="hover:bg-surface-2/60">
								<td class="px-2 py-1.5 font-mono text-text-3 whitespace-nowrap">{fmtWaktu(t.iso)}</td>
								<td class="px-2 py-1.5 uppercase text-text-3">{t.market ?? '—'}</td>
								<td class="px-2 py-1.5 font-mono text-text">{t.symbol ?? '—'}</td>
								<td class="px-2 py-1.5 text-text">{t.side ?? '—'}</td>
								<td class="px-2 py-1.5 text-right font-mono text-text">{t.price_filled ?? '—'}</td>
								<td class="px-2 py-1.5 text-right font-mono text-text">{hasil(t)}</td>
								{#if filter === 'forex'}<td class="px-2 py-1.5 text-right font-mono text-text-3">{t.slippage_pts || '—'}</td>{/if}
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
			{#if totalHalaman > 1}
				<div class="flex items-center justify-between mt-3 pt-3 border-t border-line-soft">
					<button type="button" class="min-h-[36px] rounded-control border border-line px-3 py-1.5 text-12 font-mono cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed {halaman === 0 ? 'text-text-3' : 'text-text hover:text-accent'}" disabled={halaman === 0} onclick={() => (halaman = Math.max(0, halaman - 1))}>← Sebelumnya</button>
					<span class="font-mono text-11 text-text-3">{halaman * PER_HALAMAN + 1}–{Math.min((halaman + 1) * PER_HALAMAN, terfilter.length)} dari {terfilter.length}</span>
					<button type="button" class="min-h-[36px] rounded-control border border-line px-3 py-1.5 text-12 font-mono cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed {halaman >= totalHalaman - 1 ? 'text-text-3' : 'text-text hover:text-accent'}" disabled={halaman >= totalHalaman - 1} onclick={() => (halaman = Math.min(totalHalaman - 1, halaman + 1))}>Berikutnya →</button>
				</div>
			{/if}
		</section>
	{/if}
</div>
