<script lang="ts">
	// Transaksi real-time IDX dari WebSocket running-trade. Tidak memakan kuota request,
	// jadi aman untuk data yang bergerak cepat. Saat pasar tutup, tabel kosong dengan
	// alasan yang jelas — bukan "memuat" tanpa akhir.
	import { onMount } from 'svelte';
	import { urlApi } from '$lib/api/client';

	interface Trx {
		code?: string; price?: number; lot?: number; value?: number;
		side?: string; time?: string; freq?: number; change_pct?: number;
	}
	interface Snap {
		tersedia?: boolean;
		alasan?: string;
		umur_detik?: number;
		recent?: Trx[];
		top?: Trx[];
		market?: { status?: string; label?: string; next_open?: string };
		status_pendengar?: string;
	}

	let snap = $state<Snap | null>(null);
	let galat = $state<string | null>(null);

	async function ambil() {
		try {
			const r = await fetch(urlApi('/api/v1/idx-ws/running-trade'), { credentials: 'include' });
			const isi = await r.json().catch(() => null);
			if (!r.ok) galat = isi?.error?.message ?? `HTTP ${r.status}`;
			else {
				snap = isi;
				galat = null;
			}
		} catch (e) {
			galat = e instanceof Error ? e.message : 'gagal menghubungi API';
		}
	}

	onMount(() => {
		void ambil();
		const t = setInterval(ambil, 15000);
		return () => clearInterval(t);
	});

	function angka(v: number | undefined, digit = 0) {
		return v == null ? '—' : v.toLocaleString('id-ID', { maximumFractionDigits: digit });
	}
	function rupiah(v: number | undefined) {
		if (v == null) return '—';
		if (v >= 1e9) return `${(v / 1e9).toFixed(1)} M`;
		if (v >= 1e6) return `${(v / 1e6).toFixed(0)} jt`;
		return `${v}`;
	}
	const kosong = $derived((snap?.recent?.length ?? 0) === 0);
</script>

<section class="rounded-card border border-line bg-surface p-4">
	<div class="flex flex-wrap items-center justify-between gap-2">
		<h2 class="text-13 font-bold text-text">Transaksi berjalan</h2>
		<div class="flex items-center gap-2 font-mono text-10 text-text-3">
			<span>stream</span>
			<span class="font-mono text-10" class:text-pos={snap?.status_pendengar === 'hidup'} class:text-neg={snap?.status_pendengar !== 'hidup'}>
				{snap?.status_pendengar ?? '—'}
			</span>
			{#if snap?.umur_detik != null}
				<span>· {Math.round(snap.umur_detik)}s lalu</span>
			{/if}
		</div>
	</div>

	{#if galat}
		<p class="mt-2 text-11 text-neg">{galat}</p>
	{:else if snap?.market}
		<p class="mt-1 text-11 text-text-3">
			{snap.market.label ?? snap.market.status ?? '—'}
			{#if snap.market.next_open}· buka {snap.market.next_open}{/if}
		</p>
	{/if}

	{#if kosong}
		<p class="mt-2 text-11 leading-relaxed text-text-3">
			{snap?.tersedia === false
				? `Belum ada data: ${snap.alasan ?? 'pendengar belum menerima pesan.'}`
				: 'Tidak ada transaksi pada snapshot terakhir. Saat pasar tutup, stream memang kosong — bukan berarti fitur ini mati.'}
		</p>
	{:else}
		<div class="mt-2 overflow-x-auto">
			<table class="w-full text-11 text-left">
				<thead class="border-b border-line text-10 text-text-3">
					<tr>
						<th class="px-2 py-1.5">Waktu</th>
						<th class="px-2 py-1.5">Kode</th>
						<th class="px-2 py-1.5 text-right">Harga</th>
						<th class="px-2 py-1.5 text-right">Lot</th>
						<th class="px-2 py-1.5 text-right">Nilai</th>
						<th class="px-2 py-1.5">Sisi</th>
					</tr>
				</thead>
				<tbody class="divide-y divide-line-soft">
					{#each (snap?.recent ?? []).slice(0, 12) as t, i (i)}
						<tr class="hover:bg-surface-2/60">
							<td class="whitespace-nowrap px-2 py-1.5 font-mono text-text-3">{t.time ?? '—'}</td>
							<td class="px-2 py-1.5 font-mono text-text">{t.code ?? '—'}</td>
							<td class="px-2 py-1.5 text-right font-mono text-text">{angka(t.price)}</td>
							<td class="px-2 py-1.5 text-right font-mono text-text-2">{angka(t.lot)}</td>
							<td class="px-2 py-1.5 text-right font-mono text-text-2">{rupiah(t.value)}</td>
							<td class="px-2 py-1.5 font-mono text-10" class:text-pos={t.side === 'BUY'} class:text-neg={t.side === 'SELL'}>
								{t.side ?? '—'}
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}

	{#if (snap?.top?.length ?? 0) > 0}
		<div class="mt-3 border-t border-line pt-2">
			<div class="label-mikro font-mono text-text-3">TOP 5 TERAKTIF</div>
			<ul class="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-11">
				{#each (snap?.top ?? []).slice(0, 5) as s (s.code)}
					<li class="font-mono text-text-2">
						{s.code} <span class="text-text-3">{rupiah(s.value)}</span>
					</li>
				{/each}
			</ul>
		</div>
	{/if}

	<p class="mt-2 text-10 leading-relaxed text-text-3">
		Lewat WebSocket, bukan REST, jadi tidak memakan kuota request. Snapshot diperbarui
		setiap ada transaksi yang masuk; halaman membaca snapshot tiap 15 detik.
	</p>
</section>
