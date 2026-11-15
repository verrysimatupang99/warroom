<script lang="ts">
	// Ringkas paper trading crypto: dompet, posisi terbuka, trade terakhir.
	// Data dari endpoint momentum yang sudah memakai state paper trader.
	import { urlApi } from '$lib/api/client';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import Skeleton from '$lib/components/Skeleton.svelte';

	interface Posisi {
		koin: string; entry: number; harga: number; qty: number; puncak: number; pl_pct: number;
	}
	interface Ringkas {
		aktif?: boolean;
		jumlah_koin?: number;
		modal?: number;
		ekuitas_perkiraan?: number;
		return_pct?: number;
		posisi_terbuka?: number;
		posisi?: Posisi[];
		trade_terakhir?: Record<string, string>[];
		catatan?: string;
	}

	let d = $state<Ringkas | null>(null);
	let galat = $state<string | null>(null);
	let memuat = $state(true);

	async function muat() {
		memuat = true;
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
	}

	$effect(() => {
		void muat();
	});

	function usd(v: number | undefined) {
		return v == null ? '—' : `$${v.toLocaleString('en-US', { maximumFractionDigits: 2 })}`;
	}
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
		<section class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
			<div class="rounded-card border border-line bg-surface p-4">
				<div class="label-mikro font-mono text-text-3">MODAL</div>
				<div class="mt-1 font-mono text-17 font-bold text-text">{usd(d.modal)}</div>
				<div class="mt-1 text-11 text-text-3">{d.jumlah_koin ?? 0} koin</div>
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
					{d.return_pct == null ? '—' : `${d.return_pct > 0 ? '+' : ''}${d.return_pct} %`}
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
						<thead class="border-b border-line text-10 text-text-3">
							<tr>
								<th class="px-2 py-1.5">Koin</th>
								<th class="px-2 py-1.5 text-right">Entry</th>
								<th class="px-2 py-1.5 text-right">Harga</th>
								<th class="px-2 py-1.5 text-right">Puncak</th>
								<th class="px-2 py-1.5 text-right">P/L</th>
							</tr>
						</thead>
						<tbody class="divide-y divide-line-soft">
							{#each d.posisi as p (p.koin)}
								<tr class="hover:bg-surface-2/60">
									<td class="px-2 py-1.5 font-mono text-text">{p.koin}</td>
									<td class="px-2 py-1.5 text-right font-mono text-text-2">{p.entry}</td>
									<td class="px-2 py-1.5 text-right font-mono text-text">{p.harga}</td>
									<td class="px-2 py-1.5 text-right font-mono text-text-3">{p.puncak}</td>
									<td
										class="px-2 py-1.5 text-right font-mono"
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
			{@const kolom = Object.keys(d.trade_terakhir[0] ?? {})}
			<section class="rounded-card border border-line bg-surface p-4">
				<div class="flex flex-wrap items-center justify-between gap-2">
					<h2 class="text-13 font-bold text-text">Trade paper terakhir</h2>
					<span class="font-mono text-10 text-text-3">{d.trade_terakhir.length} baris terbaru</span>
				</div>
				<div class="mt-2 overflow-x-auto">
					<table class="w-full text-11 text-left font-mono">
						<thead class="border-b border-line text-10 text-text-3">
							<tr>
								{#each kolom as k (k)}
									<th class="px-2 py-1.5 uppercase">{k}</th>
								{/each}
							</tr>
						</thead>
						<tbody class="divide-y divide-line-soft">
							{#each d.trade_terakhir as tr, idx (idx)}
								<tr class="hover:bg-surface-2/60">
									{#each kolom as k (k)}
										<td class="px-2 py-1.5 text-text-2">{tr[k] ?? '—'}</td>
									{/each}
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</section>
		{/if}
	</div>
{/if}
