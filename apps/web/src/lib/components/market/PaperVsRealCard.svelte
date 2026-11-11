<script lang="ts">
	// Perbandingan PAPER vs REAL — penjaga agar angka simulasi tidak dikira uang nyata.
	// Sumber: /api/v1/journal/paper-vs-real (real = forex EA MT5, paper = crypto simulasi).
	import { urlApi } from '$lib/api/client';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import Skeleton from '$lib/components/Skeleton.svelte';

	type Angka = number | null;
	interface BlokReal {
		n?: number; menang?: number; rugi?: number; seri?: number;
		winrate_pct?: Angka; net_usd?: Angka;
		rentang_tanggal?: { awal?: string; akhir?: string } | null;
		simbol?: string[];
	}
	interface BlokPaper {
		n?: number; menang?: number; rugi?: number;
		winrate_pct?: Angka; total_r?: Angka;
	}
	interface Banding {
		real?: BlokReal; paper?: BlokPaper;
		peringatan?: string; catatan?: string;
	}

	let d = $state<Banding | null>(null);
	let galat = $state<string | null>(null);
	let memuat = $state(true);

	async function muat() {
		memuat = true;
		galat = null;
		try {
			const r = await fetch(urlApi('/api/v1/journal/paper-vs-real'), { credentials: 'include' });
			const isi = await r.json().catch(() => null);
			if (!r.ok) {
				galat = isi?.error?.message ?? isi?.detail?.message ?? isi?.detail ?? `HTTP ${r.status}`;
				d = null;
			} else {
				d = isi;
			}
		} catch (e) {
			galat = e instanceof Error ? e.message : 'gagal menghubungi API';
			d = null;
		} finally {
			memuat = false;
		}
	}

	$effect(() => {
		void muat();
	});

	function pct(v: Angka | undefined) {
		return v == null ? '—' : `${v.toLocaleString('id-ID', { maximumFractionDigits: 1 })}%`;
	}
	function usd(v: Angka | undefined) {
		if (v == null) return '—';
		const tanda = v > 0 ? '+' : '';
		return `${tanda}$${v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
	}
	function rTotal(v: Angka | undefined) {
		if (v == null) return '—';
		return `${v > 0 ? '+' : ''}${v.toLocaleString('id-ID', { maximumFractionDigits: 2 })}R`;
	}
	function fmtTanggal(iso: string | undefined) {
		if (!iso) return '—';
		const tgl = iso.slice(0, 10);
		const [y, m, dd] = tgl.split('-');
		if (!y || !m || !dd) return tgl;
		return `${dd}/${m}/${y.slice(2)}`;
	}

	const kosong = $derived(!!d && (d.real?.n ?? 0) === 0 && (d.paper?.n ?? 0) === 0);
</script>

{#if memuat}
	<Skeleton baris={2} tinggi={96} />
{:else if galat}
	<EmptyState judul="Gagal memuat perbandingan" pesan={galat} onulang={() => void muat()} />
{:else if kosong}
	<EmptyState
		judul="Belum ada trade untuk dibandingkan"
		pesan="Laporan muncul setelah ada deal forex nyata atau trade paper crypto tercatat."
		onulang={() => void muat()}
	/>
{:else if d}
	<section class="rounded-card border border-line bg-surface p-4" aria-label="Perbandingan paper vs real">
		<div class="flex flex-wrap items-start justify-between gap-2 mb-3">
			<div>
				<h2 class="text-13 font-bold text-text">Paper vs Real</h2>
				<p class="text-11 text-text-3">
					Dua jenis catatan di ledger ini tidak setara: satu uang nyata, satu simulasi.
				</p>
			</div>
			<span class="rounded-control border border-line px-2 py-1 font-mono text-10 text-text-3">LOKAL</span>
		</div>

		<div class="grid gap-3 sm:grid-cols-2">
			<!-- REAL -->
			<div class="rounded-card border border-pos/40 bg-surface-2 p-3">
				<div class="flex items-center justify-between mb-2">
					<span class="label-mikro font-mono text-text">REAL · FOREX</span>
					<span class="rounded-control border border-pos px-2 py-0.5 font-mono text-10 font-bold text-pos">NYATA</span>
				</div>
				<div class="font-mono text-17 font-bold text-text">{d.real?.n ?? 0} trade</div>
				<dl class="mt-2 grid grid-cols-2 gap-y-1 text-11">
					<dt class="text-text-3">Menang / rugi</dt>
					<dd class="text-right font-mono">
						<span class="text-pos">{d.real?.menang ?? 0}</span> /
						<span class="text-neg">{d.real?.rugi ?? 0}</span>
					</dd>
					<dt class="text-text-3">Win rate</dt>
					<dd class="text-right font-mono font-bold text-text">{pct(d.real?.winrate_pct)}</dd>
					<dt class="text-text-3">Net</dt>
					<dd class="text-right font-mono font-bold {d.real?.net_usd != null && d.real.net_usd < 0 ? 'text-neg' : d.real?.net_usd != null ? 'text-pos' : 'text-text'}">
						{usd(d.real?.net_usd)}
					</dd>
					<dt class="text-text-3">Seri</dt>
					<dd class="text-right font-mono text-text-3">{d.real?.seri ?? 0}</dd>
					<dt class="text-text-3">Periode</dt>
					<dd class="text-right font-mono text-text-3">
						{#if d.real?.rentang_tanggal}
							{fmtTanggal(d.real.rentang_tanggal.awal)}–{fmtTanggal(d.real.rentang_tanggal.akhir)}
						{:else}—{/if}
					</dd>
				</dl>
				{#if d.real?.simbol?.length}
					<p class="mt-2 font-mono text-10 text-text-3 break-words">
						{d.real.simbol.slice(0, 6).join(' · ')}{d.real.simbol.length > 6 ? ` +${d.real.simbol.length - 6}` : ''}
					</p>
				{/if}
			</div>

			<!-- PAPER -->
			<div class="rounded-card border border-warn/40 bg-surface-2 p-3">
				<div class="flex items-center justify-between mb-2">
					<span class="label-mikro font-mono text-text">PAPER · CRYPTO</span>
					<span class="rounded-control border border-warn px-2 py-0.5 font-mono text-10 font-bold text-warn">PAPER/SIMULASI</span>
				</div>
				<div class="font-mono text-17 font-bold text-text">{d.paper?.n ?? 0} trade</div>
				<dl class="mt-2 grid grid-cols-2 gap-y-1 text-11">
					<dt class="text-text-3">Menang / rugi</dt>
					<dd class="text-right font-mono">
						<span class="text-pos">{d.paper?.menang ?? 0}</span> /
						<span class="text-neg">{d.paper?.rugi ?? 0}</span>
					</dd>
					<dt class="text-text-3">Win rate</dt>
					<dd class="text-right font-mono font-bold text-warn">{pct(d.paper?.winrate_pct)}</dd>
					<dt class="text-text-3">Total R</dt>
					<dd class="text-right font-mono font-bold {d.paper?.total_r != null && d.paper.total_r < 0 ? 'text-neg' : 'text-text'}">
						{rTotal(d.paper?.total_r)}
					</dd>
					<dt class="text-text-3">Nilai</dt>
					<dd class="text-right font-mono text-text-3">simulasi, bukan USD</dd>
				</dl>
			</div>
		</div>

		<p class="mt-3 rounded-control border border-warn/40 bg-warn/10 px-3 py-2 text-11 text-text">
			<span class="font-mono font-bold text-warn">PERINGATAN:</span>
			{d.peringatan ?? 'paper != uang nyata; real sampel kecil'}
		</p>
		{#if d.catatan}
			<p class="mt-2 text-10 text-text-3">{d.catatan}</p>
		{/if}
	</section>
{/if}
