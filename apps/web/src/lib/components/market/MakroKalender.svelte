<script lang="ts">
	// Agenda ekonomi pekan ini dari feed publik ForexFactory (lewat API War Room).
	// Dampak dan angka perkiraan ditampilkan apa adanya; tidak ada tanggal karangan.
	import { onMount } from 'svelte';
	import { urlApi } from '$lib/api/client';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import Skeleton from '$lib/components/Skeleton.svelte';

	interface Agenda {
		judul?: string; mata_uang?: string; waktu?: string;
		dampak?: string; perkiraan?: string | null; sebelumnya?: string | null;
	}
	interface Balasan {
		tersedia?: boolean; sumber?: string; jumlah?: number; agenda?: Agenda[]; pesan?: string;
	}

	let d = $state<Balasan | null>(null);
	let memuat = $state(true);
	let saring = $state<'utama' | 'tinggi' | 'semua'>('utama');

	async function muat() {
		memuat = true;
		try {
			const r = await fetch(urlApi(`/api/v1/kalender/makro?dampak=${saring}&batas=60`), {
				credentials: 'include'
			});
			const isi = await r.json().catch(() => null);
			d = r.ok ? isi : { tersedia: false, pesan: `HTTP ${r.status}`, agenda: [] };
		} catch (e) {
			d = { tersedia: false, pesan: e instanceof Error ? e.message : 'gagal', agenda: [] };
		}
		memuat = false;
	}

	$effect(() => {
		void saring;
		void muat();
	});

	function waktu(iso?: string) {
		if (!iso) return '—';
		const t = new Date(iso);
		return t.toLocaleString('id-ID', {
			weekday: 'short', day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit'
		});
	}

	const PILIH = [
		{ nilai: 'utama', label: 'Mata uang utama' },
		{ nilai: 'tinggi', label: 'Dampak tinggi' },
		{ nilai: 'semua', label: 'Semua' }
	] as const;
</script>

<div class="space-y-3">
	<div class="flex flex-wrap gap-1" role="tablist" aria-label="Saring dampak">
		{#each PILIH as p (p.nilai)}
			<button
				type="button"
				role="tab"
				aria-selected={saring === p.nilai}
				class="label-mikro transisi min-h-[44px] rounded-control border px-2.5"
				class:border-accent={saring === p.nilai}
				class:text-accent={saring === p.nilai}
				class:border-line={saring !== p.nilai}
				class:text-text-3={saring !== p.nilai}
				onclick={() => (saring = p.nilai)}
			>
				{p.label}
			</button>
		{/each}
	</div>

	{#if memuat}
		<Skeleton baris={4} tinggi={34} />
	{:else if !d?.tersedia}
		<EmptyState
			judul="Kalender tidak tersedia"
			pesan={d?.pesan ?? 'Feed tidak mengembalikan data.'}
			langkah="Periksa koneksi server ke nfs.faireconomy.media."
			onulang={() => void muat()}
		/>
	{:else}
		<div class="rounded-card border border-line bg-surface p-4">
			<div class="flex flex-wrap items-center justify-between gap-2">
				<h2 class="text-13 font-bold text-text">Agenda pekan ini</h2>
				<span class="font-mono text-11 text-text-3">{d.jumlah ?? 0} acara</span>
			</div>
			<div class="mt-2 overflow-x-auto">
				<table class="w-full text-11 text-left">
					<thead class="border-b border-line text-10 text-text-3">
						<tr>
							<th class="px-2 py-1.5">Waktu</th>
							<th class="px-2 py-1.5">Mata uang</th>
							<th class="px-2 py-1.5">Acara</th>
							<th class="px-2 py-1.5">Dampak</th>
							<th class="px-2 py-1.5 text-right">Perkiraan</th>
							<th class="px-2 py-1.5 text-right">Sebelumnya</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-line-soft">
						{#each d.agenda ?? [] as a, i (i)}
							<tr class="hover:bg-surface-2/60">
								<td class="px-2 py-1.5 font-mono text-text-3">{waktu(a.waktu)}</td>
								<td class="px-2 py-1.5 font-mono text-text">{a.mata_uang ?? '—'}</td>
								<td class="px-2 py-1.5 text-text">{a.judul ?? '—'}</td>
								<td
									class="px-2 py-1.5 font-mono"
									class:text-neg={String(a.dampak).toLowerCase() === 'high'}
									class:text-text-2={String(a.dampak).toLowerCase() !== 'high'}
								>
									{a.dampak ?? '—'}
								</td>
								<td class="px-2 py-1.5 text-right font-mono text-text-2">{a.perkiraan ?? '—'}</td>
								<td class="px-2 py-1.5 text-right font-mono text-text-3">{a.sebelumnya ?? '—'}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
			<p class="mt-2 text-11 text-text-3">
				Sumber: {d.sumber}. Diambil ulang paling sering tiap 30 menit.
			</p>
		</div>
	{/if}
</div>
