<script lang="ts">
	// Riwayat keputusan: janji "kalau tidak lolos gerbang, ia diam dan diamnya tercatat"
	// hanya berarti kalau alasan diamnya bisa dibaca. Data dari verdicts.jsonl.
	import { onMount } from 'svelte';
	import { urlApi } from '$lib/api/client';

	interface Props {
		market?: 'crypto' | 'forex' | 'all';
	}
	let { market = 'crypto' }: Props = $props();

	interface Aturan { rule?: string; ok?: boolean; hard?: boolean; reason?: string }
	interface Verdict {
		ts?: string; pair?: string; direction?: string; strategy?: string; mode?: string;
		allowed?: boolean; tier?: string; entry?: number; sl?: number; tp1?: number; rules?: Aturan[];
	}

	let daftar = $state<Verdict[]>([]);
	let total = $state(0);
	let galat = $state<string | null>(null);
	let memuat = $state(true);
	let saring = $state<'semua' | 'ditolak' | 'lolos'>('semua');

	onMount(async () => {
		try {
			const r = await fetch(urlApi(`/api/v1/journal/scanlog?market=${market}`), {
				credentials: 'include'
			});
			const isi = await r.json().catch(() => null);
			if (!r.ok) galat = isi?.error?.message ?? `HTTP ${r.status}`;
			else {
				daftar = (isi?.terakhir ?? []) as Verdict[];
				total = isi?.n ?? daftar.length;
			}
		} catch (e) {
			galat = e instanceof Error ? e.message : 'gagal menghubungi API';
		}
		memuat = false;
	});

	// Alasan pertama yang menggagalkan, diutamakan yang wajib (hard).
	function alasan(v: Verdict) {
		const gagal = (v.rules ?? []).filter((r) => r.ok === false);
		if (!gagal.length) return v.allowed ? 'lolos semua gerbang' : 'tidak ada alasan tercatat';
		const keras = gagal.find((r) => r.hard) ?? gagal[0];
		return keras.reason ?? keras.rule ?? '—';
	}

	const tampil = $derived(
		daftar
			.filter((v) => (saring === 'semua' ? true : saring === 'lolos' ? v.allowed === true : v.allowed === false))
			.slice(0, 12)
	);

	// Ringkasan: aturan mana yang paling sering menahan. Dihitung dari 100 terakhir,
	// bukan dari seluruh riwayat, dan itu disebutkan supaya tidak terbaca sebagai total.
	const tersering = $derived.by(() => {
		const hitung = new Map<string, number>();
		for (const v of daftar) {
			const gagal = (v.rules ?? []).filter((r) => r.ok === false);
			if (!gagal.length) continue;
			const keras = gagal.find((r) => r.hard) ?? gagal[0];
			const kunci = (keras.rule ?? 'lain').replace(/_/g, ' ');
			hitung.set(kunci, (hitung.get(kunci) ?? 0) + 1);
		}
		return [...hitung.entries()].sort((a, b) => b[1] - a[1]).slice(0, 4);
	});
	const lolos = $derived(daftar.filter((v) => v.allowed).length);

	// Harga mengikuti presisi pair: koin receh butuh 6 desimal, koin besar 2.
	function harga(v?: number) {
		if (v == null) return '—';
		const digit = v >= 100 ? 2 : v >= 1 ? 4 : 6;
		return v.toFixed(digit);
	}

	function jam(ts?: string) {
		if (!ts) return '—';
		const d = new Date(ts);
		return d.toLocaleString('id-ID', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
	}
</script>

<section class="rounded-card border border-line bg-surface p-4">
	<div class="flex flex-wrap items-center justify-between gap-2">
		<h2 class="text-13 font-bold text-text">
			Riwayat keputusan{market === 'crypto' ? ' crypto' : market === 'forex' ? ' forex' : ''}
		</h2>
		<div class="flex items-center gap-1.5">
			{#each [['semua', 'Semua'], ['ditolak', 'Ditolak'], ['lolos', 'Lolos']] as [k, label] (k)}
				<button
					type="button"
					class="min-h-[36px] rounded-control border px-2 font-mono text-10"
					class:border-accent={saring === k}
					class:text-accent={saring === k}
					class:border-line={saring !== k}
					class:text-text-3={saring !== k}
					onclick={() => (saring = k as 'semua' | 'ditolak' | 'lolos')}
				>
					{label}
				</button>
			{/each}
		</div>
	</div>

	{#if memuat}
		<p class="mt-2 text-11 text-text-3">membaca catatan…</p>
	{:else if galat}
		<p class="mt-2 text-11 text-text-3">Catatan keputusan tidak terbaca: {galat}</p>
	{:else}
		<p class="mt-1 font-mono text-10 text-text-3">
			{total} keputusan tersimpan · dari 100 terakhir, {lolos} lolos
		</p>

		{#if tersering.length > 0}
			<p class="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-10 text-text-3">
				<span class="text-text-3">Paling sering menahan (dari 100 terakhir):</span>
				{#each tersering as [nama, n] (nama)}
					<span class="font-mono">{nama} <span class="text-text-2">{n}×</span></span>
				{/each}
			</p>
		{/if}

		{#if tampil.length === 0}
			<p class="mt-2 text-11 text-text-3">Tidak ada keputusan pada saringan ini.</p>
		{:else}
			<div class="mt-2 overflow-x-auto">
				<table class="w-full text-11 text-left">
					<thead class="border-b border-line text-10 text-text-3">
						<tr>
							<th class="px-2 py-1.5">Waktu</th>
							<th class="px-2 py-1.5">Pair</th>
							<th class="px-2 py-1.5">Arah</th>
							<th class="px-2 py-1.5">Putusan</th>
							<th class="px-2 py-1.5">Alasan</th>
							<th class="px-2 py-1.5 text-right">Entry</th>
							<th class="px-2 py-1.5 text-right">SL</th>
							<th class="px-2 py-1.5 text-right">TP1</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-line-soft">
						{#each tampil as v, i (i)}
							<tr class="hover:bg-surface-2/60">
								<td class="whitespace-nowrap px-2 py-1.5 font-mono text-text-3">{jam(v.ts)}</td>
								<td class="px-2 py-1.5 font-mono text-text">{v.pair ?? '—'}</td>
								<td class="px-2 py-1.5 font-mono" class:text-pos={v.direction === 'LONG'} class:text-neg={v.direction === 'SHORT'}>
									{v.direction ?? '—'}
								</td>
								<td class="px-2 py-1.5">
									<span
										class="rounded border px-1.5 py-0.5 font-mono text-10"
										class:border-pos={v.allowed}
										class:text-pos={v.allowed}
										class:border-line={!v.allowed}
										class:text-text-3={!v.allowed}
									>
										{v.allowed ? 'LOLOS' : (v.tier ?? 'SKIP')}
									</span>
								</td>
								<td class="px-2 py-1.5 text-text-2">{alasan(v)}</td>
								<td class="px-2 py-1.5 text-right font-mono text-text-2">{harga(v.entry)}</td>
								<td class="px-2 py-1.5 text-right font-mono text-neg">{harga(v.sl)}</td>
								<td class="px-2 py-1.5 text-right font-mono text-pos">{harga(v.tp1)}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	{/if}
</section>
