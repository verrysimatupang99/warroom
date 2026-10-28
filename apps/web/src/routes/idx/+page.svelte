<script lang="ts">
	// IDX sebagian hidup: IHSG dari sumber publik. Scanner per-emiten, foreign flow,
	// dan bandarmologi belum ada, dan itu dinyatakan terbuka, bukan disembunyikan.
	import { onMount } from 'svelte';
	import { urlApi } from '$lib/api/client';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import Skeleton from '$lib/components/Skeleton.svelte';

	interface Candle { t: number; o: number; h: number; l: number; c: number; v: number }
	interface Pasar {
		symbol?: string; last?: number; open?: number; high?: number; low?: number;
		change_pct?: number; volume?: number; sumber?: string; candles?: Candle[];
	}

	let d = $state<Pasar | null>(null);
	let galat = $state<string | null>(null);
	let memuat = $state(true);

	onMount(async () => {
		try {
			const r = await fetch(urlApi('/api/v1/idx/market'), { credentials: 'include' });
			const isi = await r.json().catch(() => null);
			if (!r.ok) galat = isi?.error?.message ?? `HTTP ${r.status}`;
			else d = isi;
		} catch (e) {
			galat = e instanceof Error ? e.message : 'gagal menghubungi API';
		}
		memuat = false;
	});

	function angka(v: number | undefined, digit = 2) {
		return v == null ? '—' : v.toLocaleString('id-ID', { maximumFractionDigits: digit });
	}
	function tanggal(t: number) {
		return new Date(t).toLocaleDateString('id-ID', { day: '2-digit', month: 'short' });
	}
</script>

<svelte:head><title>IDX | War Room</title></svelte:head>

<div class="space-y-4">
	<PageHeader
		eyebrow="War Room · IDX"
		title="IHSG ringkas"
		tag="SEBAGIAN"
		description="Indeks IHSG dari sumber publik. Scanner per emiten, foreign flow, dan bandarmologi belum aktif, jadi halaman ini sengaja hanya menampilkan indeks."
		terverifikasi={true}
		sumber="yahoo:jkse"
	/>

	{#if memuat}
		<Skeleton baris={4} tinggi={44} />
	{:else if !d}
		<EmptyState
			judul="IHSG tidak tersedia"
			pesan={galat ?? 'Sumber publik tidak mengembalikan data indeks.'}
			langkah="Periksa koneksi server ke query2.finance.yahoo.com."
		/>
	{:else}
		<section class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
			<div class="rounded-card border border-line bg-surface p-4">
				<div class="label-mikro font-mono text-text-3">IHSG</div>
				<div class="mt-1 font-mono text-17 font-bold text-text">{angka(d.last)}</div>
				<div class="mt-1 text-11 text-text-3">pembukaan {angka(d.open)}</div>
			</div>
			<div class="rounded-card border border-line bg-surface p-4">
				<div class="label-mikro font-mono text-text-3">PERUBAHAN</div>
				<div
					class="mt-1 font-mono text-17 font-bold"
					class:text-neg={(d.change_pct ?? 0) < 0}
					class:text-pos={(d.change_pct ?? 0) > 0}
				>
					{(d.change_pct ?? 0).toFixed(2)} %
				</div>
				<div class="mt-1 text-11 text-text-3">terhadap penutupan sebelumnya</div>
			</div>
			<div class="rounded-card border border-line bg-surface p-4">
				<div class="label-mikro font-mono text-text-3">RENTANG HARI INI</div>
				<div class="mt-1 font-mono text-14 font-bold text-text">
					{angka(d.low)} – {angka(d.high)}
				</div>
			</div>
			<div class="rounded-card border border-line bg-surface p-4">
				<div class="label-mikro font-mono text-text-3">VOLUME</div>
				<div class="mt-1 font-mono text-17 font-bold text-text">
					{angka((d.volume ?? 0) / 1_000_000, 1)} jt
				</div>
			</div>
		</section>

		<section class="rounded-card border border-line bg-surface p-4">
			<h2 class="text-13 font-bold text-text">Candle harian</h2>
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

		<section class="rounded-card border border-line bg-surface p-4">
			<h2 class="text-13 font-bold text-text">Batas jujur</h2>
			<ul class="mt-2 space-y-1.5 text-11 leading-relaxed text-text-2">
				<li>· Yang tampil hanya indeks IHSG, bukan saham per emiten.</li>
				<li>· Scanner BSJP, foreign flow, dan bandarmologi belum ada di server ini.</li>
				<li>· Data indeks dari Yahoo bisa tertunda; jangan dipakai sebagai harga eksekusi.</li>
				<li>· Tidak ada sinyal IDX yang dikirim ke mana pun.</li>
			</ul>
		</section>
	{/if}
</div>
