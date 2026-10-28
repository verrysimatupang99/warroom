<script lang="ts">
	// Papan peringkat strategi dari /api/v1/leaderboard/strategi.
	// Kolom jumlah trade dan biaya wajib tampil: PF tanpa denominator adalah iklan.
	import { onMount } from 'svelte';
	import { urlApi } from '$lib/api/client';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import Skeleton from '$lib/components/Skeleton.svelte';

	interface Strategi {
		id?: string; nama?: string; venue?: string; pasar?: string; tipe?: string;
		n?: number; n_hari?: number; winrate_pct?: number; expectancy_r?: number;
		total_r?: number; max_drawdown_r?: number; status?: string; rank?: number;
		biaya?: { tercatat?: boolean; keterangan?: string };
	}

	let daftar = $state<Strategi[]>([]);
	let galat = $state<string | null>(null);
	let memuat = $state(true);

	onMount(async () => {
		try {
			const r = await fetch(urlApi('/api/v1/leaderboard/strategi'), { credentials: 'include' });
			const isi = await r.json().catch(() => null);
			if (!r.ok) {
				galat = isi?.error?.message ?? `HTTP ${r.status}`;
			} else {
				daftar = isi?.strategi ?? [];
			}
		} catch (e) {
			galat = e instanceof Error ? e.message : 'gagal menghubungi API';
		}
		memuat = false;
	});

	function angka(v: number | null | undefined, satuan = '') {
		return v == null ? '—' : `${v}${satuan}`;
	}
</script>

{#if memuat}
	<Skeleton baris={4} tinggi={34} />
{:else if galat}
	<EmptyState judul="Papan peringkat tidak terbaca" pesan={galat} />
{:else if daftar.length === 0}
	<EmptyState
		judul="Belum ada strategi terdaftar"
		pesan="Papan peringkat kosong karena belum ada strategi yang mencatat trade."
	/>
{:else}
	<div class="rounded-card border border-line bg-surface p-4">
		<div class="flex flex-wrap items-center justify-between gap-2">
			<h2 class="text-13 font-bold text-text">Papan peringkat</h2>
			<span class="font-mono text-11 text-text-3">{daftar.length} strategi</span>
		</div>
		<div class="mt-2 overflow-x-auto">
			<table class="w-full text-11 text-left">
				<thead class="border-b border-line text-10 text-text-3">
					<tr>
						<th class="px-2 py-1.5">#</th>
						<th class="px-2 py-1.5">Strategi</th>
						<th class="px-2 py-1.5">Venue</th>
						<th class="px-2 py-1.5 text-right">Trade</th>
						<th class="px-2 py-1.5 text-right">Hari</th>
						<th class="px-2 py-1.5 text-right">Win rate</th>
						<th class="px-2 py-1.5 text-right">Expectancy</th>
						<th class="px-2 py-1.5 text-right">Total R</th>
						<th class="px-2 py-1.5 text-right">DD (R)</th>
						<th class="px-2 py-1.5">Status</th>
					</tr>
				</thead>
				<tbody class="divide-y divide-line-soft">
					{#each daftar as s, i (s.id ?? i)}
						<tr class="hover:bg-surface-2/60">
							<td class="px-2 py-1.5 font-mono text-text-3">{s.rank ?? i + 1}</td>
							<td class="px-2 py-1.5 text-text">{s.nama ?? '—'}</td>
							<td class="px-2 py-1.5 text-text-3">{s.venue ?? '—'}</td>
							<td class="px-2 py-1.5 text-right font-mono text-text">{s.n ?? 0}</td>
							<td class="px-2 py-1.5 text-right font-mono text-text-3">{s.n_hari ?? '—'}</td>
							<td class="px-2 py-1.5 text-right font-mono text-text">{angka(s.winrate_pct, ' %')}</td>
							<td class="px-2 py-1.5 text-right font-mono text-text">{angka(s.expectancy_r, ' R')}</td>
							<td class="px-2 py-1.5 text-right font-mono text-text">{angka(s.total_r, ' R')}</td>
							<td class="px-2 py-1.5 text-right font-mono text-neg">{angka(s.max_drawdown_r, ' R')}</td>
							<td class="px-2 py-1.5 font-mono text-text-3">{s.status ?? '—'}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
		{#if daftar[0]?.biaya}
			<p class="mt-2 text-11 text-text-3">
				Biaya: {daftar[0].biaya.tercatat ? 'tercatat per trade' : 'belum tercatat'}.
				{daftar[0].biaya.keterangan ?? ''}
			</p>
		{/if}
		<p class="mt-1 text-11 text-text-3">
			Peringkat dihitung dari total R, bukan dari PnL dolar, supaya strategi dengan ukuran
			posisi berbeda bisa dibandingkan.
		</p>
	</div>
{/if}
