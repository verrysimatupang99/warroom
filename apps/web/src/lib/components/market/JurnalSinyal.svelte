<script lang="ts">
	// Jurnal sinyal: alert yang benar-benar dikirim + hasil dari candle sejak jam
	// setelah kirim. Bukan cache outcomes (yang mulai dari waktu verdict).
	import { onMount } from 'svelte';
	import { urlApi } from '$lib/api/client';

	interface TierRingkas {
		n_terkirim?: number;
		n_terisi?: number;
		tp1?: number;
		sl?: number;
		winrate?: number | null;
		total_r?: number;
		expectancy_r?: number | null;
	}
	interface Ringkas {
		n_terkirim?: number;
		n_terisi?: number;
		tp1?: number;
		sl?: number;
		winrate?: number | null;
		total_r?: number;
		expectancy_r?: number | null;
		expectancy_0r?: number | null;
		beda_cache?: number;
		per_tier?: Record<string, TierRingkas>;
	}
	interface Baris {
		dikirim?: string;
		pair?: string;
		side?: string;
		tier?: string;
		entry?: number | null;
		hasil?: string;
		r?: number | null;
		hasil_cache?: string;
		r_cache?: number | null;
	}

	let ringkas = $state<Ringkas | null>(null);
	let rows = $state<Baris[]>([]);
	let dihitung = $state<string | null>(null);
	let galat = $state<string | null>(null);
	let memuat = $state(true);

	onMount(async () => {
		try {
			const r = await fetch(urlApi('/api/v1/journal/signals'), { credentials: 'include' });
			const isi = await r.json().catch(() => null);
			if (!r.ok) {
				const p = isi?.detail?.message ?? isi?.error?.message ?? isi?.detail;
				galat = typeof p === 'string' ? p : `HTTP ${r.status}`;
			} else {
				ringkas = isi?.ringkas ?? null;
				rows = (isi?.rows ?? []) as Baris[];
				dihitung = isi?.dihitung_at ?? null;
			}
		} catch (e) {
			galat = e instanceof Error ? e.message : 'gagal menghubungi API';
		}
		memuat = false;
	});

	function angka(v?: number | null, digit = 3) {
		return v == null ? '—' : v.toFixed(digit);
	}
	function jam(ts?: string) {
		if (!ts) return '—';
		const d = new Date(ts);
		return Number.isNaN(d.getTime())
			? '—'
			: d.toLocaleString('id-ID', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
	}
	const terakhir = $derived([...rows].slice(-15).reverse());
</script>

<section class="rounded-card border border-line bg-surface p-4" data-testid="jurnal-sinyal">
	<div class="flex flex-wrap items-start justify-between gap-2">
		<div>
			<h2 class="text-13 font-bold text-text">Jurnal sinyal terkirim</h2>
			<p class="mt-0.5 text-11 text-text-3">
				Hasil dihitung ulang dari candle Binance sejak jam setelah pesan dikirim — bukan
				dari waktu verdict. Ini yang dialami penerima sinyal.
			</p>
		</div>
		<span class="font-mono text-10 text-text-3">
			{dihitung ? `dihitung ${jam(dihitung)}` : ''}
		</span>
	</div>

	{#if memuat}
		<p class="mt-2 text-11 text-text-3">membaca jurnal…</p>
	{:else if galat}
		<p class="mt-2 text-11 text-text-3">Jurnal sinyal belum tersedia: {galat}</p>
	{:else if !ringkas || (ringkas.n_terkirim ?? 0) === 0}
		<p class="mt-2 text-11 text-text-3">Belum ada sinyal terkirim yang bisa dinilai.</p>
	{:else}
		<dl class="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
			<div>
				<dt class="label-mikro font-mono text-text-3">TERKIRIM</dt>
				<dd class="mt-0.5 font-mono text-14 font-bold text-text">{ringkas.n_terkirim}</dd>
			</div>
			<div>
				<dt class="label-mikro font-mono text-text-3">TERISI</dt>
				<dd class="mt-0.5 font-mono text-14 font-bold text-text">{ringkas.n_terisi}</dd>
			</div>
			<div>
				<dt class="label-mikro font-mono text-text-3">WIN RATE TP1</dt>
				<dd class="mt-0.5 font-mono text-14 font-bold text-text">{angka(ringkas.winrate, 1)}%</dd>
			</div>
			<div>
				<dt class="label-mikro font-mono text-text-3">EXPECTANCY</dt>
				<dd class="mt-0.5 font-mono text-14 font-bold" class:text-pos={(ringkas.expectancy_r ?? 0) > 0}>
					{angka(ringkas.expectancy_r)}R
				</dd>
			</div>
			<div>
				<dt class="label-mikro font-mono text-text-3">TOTAL</dt>
				<dd class="mt-0.5 font-mono text-14 font-bold text-text">{angka(ringkas.total_r, 2)}R</dd>
			</div>
		</dl>

		<div class="mt-3 grid gap-2 sm:grid-cols-2">
			{#each Object.entries(ringkas.per_tier ?? {}) as [tier, t] (tier)}
				<div class="rounded border border-line bg-surface-2 p-2.5">
					<div class="flex items-center justify-between">
						<span class="font-mono text-10 text-text-3">{tier}</span>
						<span class="font-mono text-10 text-text-3">{t.n_terisi ?? 0}/{t.n_terkirim ?? 0} terisi</span>
					</div>
					<div class="mt-1 flex flex-wrap gap-x-3 font-mono text-11">
						<span class="text-text">WR {angka(t.winrate, 1)}%</span>
						<span class:text-pos={(t.expectancy_r ?? 0) > 0} class:text-neg={(t.expectancy_r ?? 0) <= 0}>
							{angka(t.expectancy_r)}R/trade
						</span>
						<span class="text-text-3">TP1 {t.tp1 ?? 0} · SL {t.sl ?? 0}</span>
					</div>
				</div>
			{/each}
		</div>

		<p class="mt-2 text-10 text-text-3">
			{ringkas.beda_cache ?? 0} hasil berbeda dari cache berbasis waktu verdict. Selisih
			terjadi karena TP/fill sebelum pesan terkirim tidak dihitung di sini.
		</p>

		{#if terakhir.length > 0}
			<div class="mt-3 overflow-x-auto">
				<table class="w-full text-11 text-left">
					<thead class="border-b border-line text-10 text-text-3">
						<tr>
							<th class="px-2 py-1.5">Dikirim</th>
							<th class="px-2 py-1.5">Pair</th>
							<th class="px-2 py-1.5">Arah</th>
							<th class="px-2 py-1.5">Tier</th>
							<th class="px-2 py-1.5 text-right">Entry</th>
							<th class="px-2 py-1.5">Hasil</th>
							<th class="px-2 py-1.5 text-right">R</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-line-soft">
						{#each terakhir as v, i (i)}
							<tr class="hover:bg-surface-2/60">
								<td class="whitespace-nowrap px-2 py-1.5 font-mono text-text-3">{jam(v.dikirim)}</td>
								<td class="px-2 py-1.5 font-mono text-text">{v.pair ?? '—'}</td>
								<td class="px-2 py-1.5 font-mono" class:text-pos={v.side === 'LONG'} class:text-neg={v.side === 'SHORT'}>
									{v.side ?? '—'}
								</td>
								<td class="px-2 py-1.5 font-mono text-text-3">{v.tier ?? '—'}</td>
								<td class="px-2 py-1.5 text-right font-mono text-text-2">{v.entry ?? '—'}</td>
								<td class="px-2 py-1.5">
									<span
										class="rounded border px-1.5 py-0.5 font-mono text-10"
										class:border-pos={v.hasil === 'tp1'}
										class:text-pos={v.hasil === 'tp1'}
										class:border-neg={v.hasil === 'sl'}
										class:text-neg={v.hasil === 'sl'}
										class:border-line={v.hasil !== 'tp1' && v.hasil !== 'sl'}
										class:text-text-3={v.hasil !== 'tp1' && v.hasil !== 'sl'}
									>
										{v.hasil ?? '—'}
									</span>
								</td>
								<td class="px-2 py-1.5 text-right font-mono" class:text-pos={(v.r ?? 0) > 0} class:text-neg={(v.r ?? 0) < 0}>
									{angka(v.r, 2)}
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	{/if}
</section>
