<script lang="ts">
	// Riwayat evaluasi EA forex. Sumbernya fakta `mt5_snapshot`, BUKAN verdicts.jsonl:
	// verdict crypto tidak boleh tercampur ke tab Sinyal forex.
	import { onMount } from 'svelte';
	import { urlApi } from '$lib/api/client';

	interface Evaluasi {
		ts?: string;
		pair?: string;
		eval_at?: number | null;
		sesi?: boolean;
		alasan?: string;
		atr?: number | null;
		spread?: number | null;
		rsi?: number | null;
		ema_fast?: number | null;
		ema_slow?: number | null;
		tren?: string | null;
	}

	let daftar = $state<Evaluasi[]>([]);
	let total = $state(0);
	let galat = $state<string | null>(null);
	let memuat = $state(true);

	onMount(async () => {
		try {
			const r = await fetch(urlApi('/api/v1/journal/scanlog?market=forex'), {
				credentials: 'include'
			});
			const isi = await r.json().catch(() => null);
			if (!r.ok) {
				const pesan = isi?.error?.message ?? isi?.detail?.message ?? isi?.detail;
				galat = typeof pesan === 'string' ? pesan : `HTTP ${r.status}`;
			} else {
				daftar = (isi?.terakhir ?? []) as Evaluasi[];
				total = isi?.n ?? daftar.length;
			}
		} catch (e) {
			galat = e instanceof Error ? e.message : 'gagal menghubungi API';
		}
		memuat = false;
	});

	function jam(ts?: string) {
		if (!ts) return '—';
		const d = new Date(ts);
		if (Number.isNaN(d.getTime())) return '—';
		return d.toLocaleString('id-ID', {
			day: '2-digit',
			month: 'short',
			hour: '2-digit',
			minute: '2-digit'
		});
	}

	function angka(v: number | null | undefined, digit = 2) {
		return v == null ? '—' : v.toFixed(digit);
	}
</script>

<section class="rounded-card border border-line bg-surface p-4" data-testid="riwayat-ea">
	<div class="flex flex-wrap items-center justify-between gap-2">
		<div>
			<h2 class="text-13 font-bold text-text">Riwayat evaluasi EA</h2>
			<p class="mt-0.5 text-11 text-text-3">
				XAUUSD · alasan entry/skip terakhir dari mesin Reaper. Keputusan crypto tidak
				dicampur ke sini.
			</p>
		</div>
		<span class="font-mono text-10 text-text-3">{total} evaluasi berbeda</span>
	</div>

	{#if memuat}
		<p class="mt-2 text-11 text-text-3">membaca telemetri…</p>
	{:else if galat}
		<p class="mt-2 text-11 text-text-3">Riwayat evaluasi tidak terbaca: {galat}</p>
	{:else if daftar.length === 0}
		<p class="mt-2 text-11 text-text-3">
			Belum ada evaluasi. EA v3.1 mengirim alasan setiap kali ia memutuskan entry atau skip.
		</p>
	{:else}
		<div class="mt-2 overflow-x-auto">
			<table class="w-full text-11 text-left">
				<thead class="border-b border-line text-10 text-text-3">
					<tr>
						<th class="px-2 py-1.5">Waktu</th>
						<th class="px-2 py-1.5">Sesi</th>
						<th class="px-2 py-1.5">Alasan</th>
						<th class="px-2 py-1.5 text-right">ATR</th>
						<th class="px-2 py-1.5 text-right">Spread</th>
						<th class="px-2 py-1.5 text-right">RSI</th>
						<th class="px-2 py-1.5">Tren</th>
					</tr>
				</thead>
				<tbody class="divide-y divide-line-soft">
					{#each daftar.slice(0, 12) as v, i (i)}
						<tr class="hover:bg-surface-2/60">
							<td class="whitespace-nowrap px-2 py-1.5 font-mono text-text-3">{jam(v.ts)}</td>
							<td class="px-2 py-1.5">
								<span
									class="rounded border px-1.5 py-0.5 font-mono text-10"
									class:border-pos={v.sesi}
									class:text-pos={v.sesi}
									class:border-line={!v.sesi}
									class:text-text-3={!v.sesi}
								>
									{v.sesi ? 'SESI' : 'LUAR'}
								</span>
							</td>
							<td class="px-2 py-1.5 text-text-2">{v.alasan ?? '—'}</td>
							<td class="px-2 py-1.5 text-right font-mono text-text-2">{angka(v.atr)}</td>
							<td class="px-2 py-1.5 text-right font-mono text-text-2">{angka(v.spread, 3)}</td>
							<td class="px-2 py-1.5 text-right font-mono text-text-2">{angka(v.rsi, 1)}</td>
							<td class="px-2 py-1.5 font-mono text-text-2">{v.tren ?? '—'}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
		<p class="mt-2 text-10 text-text-3">
			Menampilkan maksimal 12 evaluasi berbeda; duplikat per menit digabung.
		</p>
	{/if}
</section>
