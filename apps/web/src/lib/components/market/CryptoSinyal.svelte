<script lang="ts">
	// Tab Sinyal crypto: universe MEXC, ticker, dan candle. Semua dari sumber lokal.
	import { onMount } from 'svelte';
	import { urlApi } from '$lib/api/client';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import Skeleton from '$lib/components/Skeleton.svelte';

	interface Candle { t: number; o: number; h: number; l: number; c: number; v: number }
	interface Ticker { symbol?: string; last_price?: number; high_?: number; low_?: number; change_pct_?: number }

	let universe = $state<string[]>([]);
	let simbol = $state('BTCUSDT');
	let ticker = $state<Ticker | null>(null);
	let candles = $state<Candle[]>([]);
	let memuat = $state(true);
	let galat = $state<string | null>(null);

	async function j<T>(jalur: string): Promise<T | null> {
		try {
			const r = await fetch(urlApi(jalur), { credentials: 'include' });
			const isi = await r.json().catch(() => null);
			if (!r.ok) {
				galat = isi?.error?.message ?? isi?.detail?.message ?? `HTTP ${r.status}`;
				return null;
			}
			return isi as T;
		} catch (e) {
			galat = e instanceof Error ? e.message : 'gagal menghubungi API';
			return null;
		}
	}

	async function muatSimbol(s: string) {
		simbol = s;
		memuat = true;
		const [t, k] = await Promise.all([
			j<Ticker>(`/api/v1/tencent/ticker?symbol=${s}`),
			j<{ candles: Candle[] }>(`/api/v1/tencent/klines?market=crypto&symbol=${s}&interval=1h&limit=15`)
		]);
		ticker = t;
		candles = k?.candles ?? [];
		memuat = false;
	}

	onMount(async () => {
		const u = await j<{ symbols: string[] }>('/api/v1/tencent/universe');
		universe = u?.symbols ?? [];
		await muatSimbol(universe[0] ?? 'BTCUSDT');
	});

	function waktu(t: number) {
		return new Date(t).toISOString().slice(5, 16).replace('T', ' ');
	}

	// Level struktur dihitung dari candle yang sedang tampil. Ini BUKAN analisis SMC:
	// engine SMC aslinya ada di node lama. Yang dihitung sini hanya swing high/low,
	// ATR kasar, dan posisi harga dalam rentang, semuanya bisa diperiksa ulang.
	const struktur = $derived.by(() => {
		if (candles.length < 3) return null;
		const tinggi = Math.max(...candles.map((c) => c.h));
		const rendah = Math.min(...candles.map((c) => c.l));
		const atr = candles.reduce((a, c) => a + (c.h - c.l), 0) / candles.length;
		const akhir = candles[candles.length - 1].c;
		const lebar = tinggi - rendah;
		return {
			tinggi,
			rendah,
			atr,
			akhir,
			posisi: lebar > 0 ? ((akhir - rendah) / lebar) * 100 : 0,
			lebar
		};
	});
</script>

{#if memuat}
	<Skeleton baris={4} tinggi={40} />
{:else if !ticker}
	<EmptyState
		judul="Data crypto belum tersedia"
		pesan={galat ?? 'Sumber lokal tidak mengembalikan data.'}
		onulang={() => void muatSimbol(simbol)}
	/>
{:else}
	<div class="space-y-4">
		<section class="flex flex-wrap items-center gap-2">
			<label class="label-mikro font-mono text-text-3" for="pilih-simbol">SIMBOL</label>
			<select
				id="pilih-simbol"
				class="min-h-[44px] rounded-control border border-line bg-surface px-2 font-mono text-12 text-text"
				value={simbol}
				onchange={(e) => void muatSimbol((e.currentTarget as HTMLSelectElement).value)}
			>
				{#each universe as s (s)}
					<option value={s}>{s}</option>
				{/each}
			</select>
			<span class="text-11 text-text-3">{universe.length} simbol USDT di MEXC</span>
		</section>

		<section class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
			<div class="rounded-card border border-line bg-surface p-4">
				<div class="label-mikro font-mono text-text-3">HARGA</div>
				<div class="mt-1 font-mono text-17 font-bold text-text">{ticker.last_price ?? '—'}</div>
			</div>
			<div class="rounded-card border border-line bg-surface p-4">
				<div class="label-mikro font-mono text-text-3">PERUBAHAN 24 JAM</div>
				<div class="mt-1 font-mono text-17 font-bold text-text">
					{ticker.change_pct_ == null ? '—' : `${ticker.change_pct_} %`}
				</div>
			</div>
			<div class="rounded-card border border-line bg-surface p-4">
				<div class="label-mikro font-mono text-text-3">TERTINGGI</div>
				<div class="mt-1 font-mono text-17 font-bold text-text">{ticker.high_ ?? '—'}</div>
			</div>
			<div class="rounded-card border border-line bg-surface p-4">
				<div class="label-mikro font-mono text-text-3">TERENDAH</div>
				<div class="mt-1 font-mono text-17 font-bold text-text">{ticker.low_ ?? '—'}</div>
			</div>
		</section>

		{#if struktur}
			<section class="rounded-card border border-line bg-surface p-4">
				<h2 class="text-13 font-bold text-text">Level struktur (dihitung lokal)</h2>
				<dl class="mt-2 grid gap-2 text-12 sm:grid-cols-2 lg:grid-cols-4">
					<div>
						<dt class="text-text-3">Swing tinggi</dt>
						<dd class="font-mono text-15 font-bold text-text">{struktur.tinggi}</dd>
					</div>
					<div>
						<dt class="text-text-3">Swing rendah</dt>
						<dd class="font-mono text-15 font-bold text-text">{struktur.rendah}</dd>
					</div>
					<div>
						<dt class="text-text-3">ATR kasar (rata-rata range)</dt>
						<dd class="font-mono text-15 font-bold text-text">{struktur.atr.toFixed(6)}</dd>
					</div>
					<div>
						<dt class="text-text-3">Posisi dalam rentang</dt>
						<dd class="font-mono text-15 font-bold text-text">{struktur.posisi.toFixed(1)} %</dd>
					</div>
				</dl>
				<p class="mt-2 text-11 text-text-3">
					Ini bukan analisis SMC. Engine SMC yang lama berjalan di node luar yang sudah
					tidak aktif, jadi halaman ini hanya menampilkan angka yang bisa dihitung ulang
					dari candle di atas.
				</p>
			</section>
		{/if}

		<section class="rounded-card border border-line bg-surface p-4">
			<h2 class="text-13 font-bold text-text">Candle 1 jam</h2>
			<div class="mt-2 overflow-x-auto">
				<table class="w-full text-11 text-left">
					<thead class="border-b border-line text-10 text-text-3">
						<tr>
							<th class="px-2 py-1.5">Waktu</th>
							<th class="px-2 py-1.5 text-right">Open</th>
							<th class="px-2 py-1.5 text-right">High</th>
							<th class="px-2 py-1.5 text-right">Low</th>
							<th class="px-2 py-1.5 text-right">Close</th>
							<th class="px-2 py-1.5 text-right">Volume</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-line-soft">
						{#each candles as c (c.t)}
							<tr class="hover:bg-surface-2/60">
								<td class="px-2 py-1.5 font-mono text-text-3">{waktu(c.t)}</td>
								<td class="px-2 py-1.5 text-right font-mono text-text-2">{c.o}</td>
								<td class="px-2 py-1.5 text-right font-mono text-pos">{c.h}</td>
								<td class="px-2 py-1.5 text-right font-mono text-neg">{c.l}</td>
								<td class="px-2 py-1.5 text-right font-mono font-bold text-text">{c.c}</td>
								<td class="px-2 py-1.5 text-right font-mono text-text-3">{Math.round(c.v).toLocaleString('en-US')}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
			<p class="mt-2 text-11 text-text-3">
				Sumber: MEXC public API. Level SMC belum punya padanan lokal, jadi tab ini
				sengaja tidak menampilkan level yang tidak bisa dihitung di server.
			</p>
		</section>
	</div>
{/if}
