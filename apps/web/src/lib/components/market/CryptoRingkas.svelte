<script lang="ts">
	// Ringkas paper trading crypto: dompet, posisi terbuka, trade terakhir.
	// Data dari endpoint momentum yang sudah memakai state paper trader.
	import { urlApi } from '$lib/api/client';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import Skeleton from '$lib/components/Skeleton.svelte';

	interface Posisi {
		koin: string; entry: number; harga: number; qty: number; puncak: number; pl_pct: number;
	}
	interface TradeRow {
		waktu?: string; koin?: string; aksi?: string; harga?: number; qty?: number; pnl_pct?: number; alasan?: string;
		[key: string]: unknown;
	}
	interface Ringkas {
		aktif?: boolean;
		jumlah_koin?: number;
		modal?: number;
		ekuitas_perkiraan?: number;
		return_pct?: number;
		posisi_terbuka?: number;
		posisi?: Posisi[];
		trade_terakhir?: TradeRow[];
		catatan?: string;
	}

	let d = $state<Ringkas | null>(null);
	let galat = $state<string | null>(null);
	let memuat = $state(true);
	let menyegarkan = $state(false);
	let filterAksi = $state<'SEMUA' | 'BELI' | 'JUAL'>('SEMUA');

	async function muat(senyap = false) {
		if (senyap) menyegarkan = true;
		else memuat = true;
		try {
			const r = await fetch(urlApi('/api/v1/tencent/crypto/momentum'), { credentials: 'include' });
			const isi = await r.json().catch(() => null);
			if (!r.ok) {
				galat = isi?.error?.message ?? isi?.detail?.message ?? `HTTP ${r.status}`;
				d = null;
			} else {
				d = isi;
				galat = null;
			}
		} catch (e) {
			galat = e instanceof Error ? e.message : 'gagal menghubungi API';
		}
		memuat = false;
		menyegarkan = false;
	}

	$effect(() => {
		void muat();
		const t = setInterval(() => void muat(true), 30_000);
		return () => clearInterval(t);
	});

	function usd(v: number | undefined) {
		return v == null ? '—' : `$${v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
	}
	function fmtHarga(v: unknown): string {
		const n = Number(v);
		if (v == null || !Number.isFinite(n)) return '—';
		if (n >= 100) return `$${n.toLocaleString('en-US', { maximumFractionDigits: 2 })}`;
		if (n >= 1) return `$${n.toLocaleString('en-US', { maximumFractionDigits: 4 })}`;
		return `$${n.toLocaleString('en-US', { maximumFractionDigits: 6 })}`;
	}
	function fmtWaktu(w: unknown): string {
		if (!w) return '—';
		const s = String(w);
		return s.length > 16 ? s.slice(5, 16).replace('T', ' ') : s;
	}

	const tradesFiltered = $derived.by(() => {
		const list = d?.trade_terakhir ?? [];
		if (filterAksi === 'SEMUA') return list;
		return list.filter((t) => String(t.aksi ?? '').toUpperCase().includes(filterAksi));
	});
</script>

{#if memuat}
	<Skeleton baris={4} tinggi={46} />
{:else if !d?.aktif}
	<EmptyState
		judul="Paper trader belum berjalan"
		pesan={galat ?? 'State paper trader tidak ditemukan di server.'}
		onulang={() => void muat()}
	/>
{:else}
	<div class="space-y-4">
		<div class="flex flex-wrap items-center justify-between gap-2 font-mono text-10 text-text-3">
			<span>● PAPER ENGINE AKTIF · {d.jumlah_koin ?? 65} KOIN OKX · AUTO 30s</span>
			<button
				type="button"
				onclick={() => void muat(true)}
				class="rounded border border-line bg-surface px-2.5 py-1 text-text-2 hover:border-accent hover:text-accent cursor-pointer"
			>
				{menyegarkan ? 'Menyegarkan…' : 'Segarkan ⟳'}
			</button>
		</div>

		<section class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
			<div class="rounded-card border border-line bg-surface p-4">
				<div class="label-mikro font-mono text-text-3">MODAL</div>
				<div class="mt-1 font-mono text-17 font-bold text-text">{usd(d.modal)}</div>
				<div class="mt-1 text-11 text-text-3">{d.jumlah_koin ?? 0} koin ($500 / koin)</div>
			</div>
			<div class="rounded-card border border-line bg-surface p-4">
				<div class="label-mikro font-mono text-text-3">EKUITAS</div>
				<div class="mt-1 font-mono text-17 font-bold text-text">{usd(d.ekuitas_perkiraan)}</div>
				<div class="mt-1 text-11 text-text-3">perkiraan, harga candle terakhir</div>
			</div>
			<div class="rounded-card border border-line bg-surface p-4">
				<div class="label-mikro font-mono text-text-3">RETURN</div>
				<div
					class="mt-1 font-mono text-17 font-bold"
					class:text-pos={(d.return_pct ?? 0) > 0}
					class:text-neg={(d.return_pct ?? 0) < 0}
					class:text-text={(d.return_pct ?? 0) === 0}
				>
					{d.return_pct == null ? '—' : `${d.return_pct > 0 ? '+' : ''}${d.return_pct}%`}
				</div>
				<div class="mt-1 text-11 text-text-3">sejak modal awal</div>
			</div>
			<div class="rounded-card border border-line bg-surface p-4">
				<div class="label-mikro font-mono text-text-3">POSISI TERBUKA</div>
				<div class="mt-1 font-mono text-17 font-bold text-text">{d.posisi_terbuka ?? 0}</div>
				<div class="mt-1 text-11 text-text-3">dari {d.jumlah_koin ?? 0} koin dipantau</div>
			</div>
		</section>

		<section class="rounded-card border border-line bg-surface p-4">
			<h2 class="text-13 font-bold text-text">Posisi terbuka</h2>
			{#if !d.posisi || d.posisi.length === 0}
				<EmptyState
					judul="Tidak ada posisi"
					pesan="Strategi sedang menunggu breakout 55 bar. Belum ada koin yang memenuhi syarat masuk."
					ringkas={true}
				/>
			{:else}
				<div class="mt-2 overflow-x-auto">
					<table class="w-full text-11 text-left">
						<thead class="border-b border-line text-10 text-text-3 font-mono">
							<tr>
								<th class="px-2 py-1.5">Koin</th>
								<th class="px-2 py-1.5 text-right">Entry</th>
								<th class="px-2 py-1.5 text-right">Harga</th>
								<th class="px-2 py-1.5 text-right">Puncak</th>
								<th class="px-2 py-1.5 text-right">Nilai</th>
								<th class="px-2 py-1.5 text-right">P/L</th>
							</tr>
						</thead>
						<tbody class="divide-y divide-line-soft font-mono">
							{#each d.posisi as p (p.koin)}
								<tr class="hover:bg-surface-2/60">
									<td class="px-2 py-1.5 font-bold text-text">{p.koin}</td>
									<td class="px-2 py-1.5 text-right text-text-2">{fmtHarga(p.entry)}</td>
									<td class="px-2 py-1.5 text-right text-text">{fmtHarga(p.harga)}</td>
									<td class="px-2 py-1.5 text-right text-text-3">{fmtHarga(p.puncak)}</td>
									<td class="px-2 py-1.5 text-right text-text-2">{usd(p.harga * p.qty)}</td>
									<td
										class="px-2 py-1.5 text-right font-bold"
										class:text-pos={p.pl_pct > 0}
										class:text-neg={p.pl_pct < 0}
									>
										{p.pl_pct > 0 ? '+' : ''}{p.pl_pct}%
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{/if}
		</section>

		{#if d.trade_terakhir && d.trade_terakhir.length > 0}
			<section class="rounded-card border border-line bg-surface p-4">
				<div class="flex flex-wrap items-center justify-between gap-2">
					<h2 class="text-13 font-bold text-text">Trade paper terakhir</h2>
					<div class="flex items-center gap-1.5 font-mono text-10">
						{#each ['SEMUA', 'BELI', 'JUAL'] as ax (ax)}
							<button
								type="button"
								onclick={() => (filterAksi = ax as 'SEMUA' | 'BELI' | 'JUAL')}
								class="rounded border px-2 py-0.5 cursor-pointer {filterAksi === ax ? 'border-accent bg-accent/15 text-accent font-bold' : 'border-line bg-surface-2 text-text-3 hover:text-text'}"
							>
								{ax}
							</button>
						{/each}
						<span class="ml-1 text-text-3">{tradesFiltered.length}/{d.trade_terakhir.length}</span>
					</div>
				</div>
				<div class="mt-2 overflow-x-auto">
					<table class="w-full text-11 text-left font-mono">
						<thead class="border-b border-line text-10 text-text-3">
							<tr>
								<th class="px-2 py-1.5">Waktu</th>
								<th class="px-2 py-1.5">Koin</th>
								<th class="px-2 py-1.5">Aksi</th>
								<th class="px-2 py-1.5 text-right">Harga</th>
								<th class="px-2 py-1.5 text-right">PnL %</th>
								<th class="px-2 py-1.5">Alasan</th>
							</tr>
						</thead>
						<tbody class="divide-y divide-line-soft">
							{#each tradesFiltered as tr, idx (idx)}
								{@const aksi = String(tr.aksi ?? '—').toUpperCase()}
								{@const pnl = tr.pnl_pct != null ? Number(tr.pnl_pct) : null}
								<tr class="hover:bg-surface-2/60">
									<td class="px-2 py-1.5 text-text-3 whitespace-nowrap">{fmtWaktu(tr.waktu)}</td>
									<td class="px-2 py-1.5 font-bold text-text">{tr.koin ?? '—'}</td>
									<td class="px-2 py-1.5">
										<span class="rounded border px-1.5 py-0.5 text-10 font-bold {aksi === 'BELI' ? 'border-pos/35 bg-pos/10 text-pos' : aksi === 'JUAL' ? 'border-warn/35 bg-warn/10 text-warn' : 'border-line text-text-2'}">
											{aksi}
										</span>
									</td>
									<td class="px-2 py-1.5 text-right text-text-2">{fmtHarga(tr.harga)}</td>
									<td class="px-2 py-1.5 text-right font-bold {(pnl ?? 0) > 0 ? 'text-pos' : (pnl ?? 0) < 0 ? 'text-neg' : 'text-text-3'}">
										{pnl == null ? '—' : `${pnl > 0 ? '+' : ''}${pnl.toFixed(2)}%`}
									</td>
									<td class="px-2 py-1.5 text-text-3 font-sans">{tr.alasan ?? '—'}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</section>
		{/if}
	</div>
{/if}
