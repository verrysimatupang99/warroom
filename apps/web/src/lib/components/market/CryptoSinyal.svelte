<script lang="ts">
	// Tab Sinyal crypto: universe OKX, ticker, dan indikator lokal dari candle (tanpa angka palsu).
	import { onMount } from 'svelte';
	import { urlApi } from '$lib/api/client';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import Skeleton from '$lib/components/Skeleton.svelte';

	interface Candle { t: number; o: number; h: number; l: number; c: number; v: number }
	interface Ticker { symbol?: string; last_price?: number; high_?: number; low_?: number; change_pct_?: number; volume_?: number; source?: string }

	const INTERVALS = ['15m', '1h', '4h', '1d'] as const;
	let universe = $state<string[]>([]);
	let filterSimbol = $state('');
	let simbol = $state('BTCUSDT');
	let interval = $state<(typeof INTERVALS)[number]>('1h');
	let ticker = $state<Ticker | null>(null);
	let candles = $state<Candle[]>([]);
	let memuat = $state(true);
	let galat = $state<string | null>(null);

	const universeFiltered = $derived.by(() => {
		const q = filterSimbol.trim().toUpperCase();
		if (!q) return universe;
		const matches = universe.filter((s) => s.includes(q));
		return matches.includes(simbol) ? matches : [simbol, ...matches];
	});

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

	async function muatSimbol(s: string, tf: (typeof INTERVALS)[number] = interval) {
		simbol = s;
		interval = tf;
		memuat = true;
		const [t, k] = await Promise.all([
			j<Ticker>(`/api/v1/tencent/ticker?symbol=${s}`),
			j<{ candles: Candle[] }>(`/api/v1/tencent/klines?market=crypto&symbol=${s}&interval=${tf}&limit=48`)
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
	function fmtVol(v: number | undefined): string {
		if (v == null || !Number.isFinite(v)) return '—';
		if (v >= 1e9) return `$${(v / 1e9).toFixed(2)}B`;
		if (v >= 1e6) return `$${(v / 1e6).toFixed(2)}M`;
		if (v >= 1e3) return `$${(v / 1e3).toFixed(1)}K`;
		return `$${v.toFixed(0)}`;
	}
	function fmtHarga(v: number | undefined): string {
		if (v == null || !Number.isFinite(v)) return '—';
		if (v >= 100) return v.toLocaleString('en-US', { maximumFractionDigits: 2 });
		if (v >= 1) return v.toLocaleString('en-US', { maximumFractionDigits: 4 });
		return v.toLocaleString('en-US', { maximumFractionDigits: 6 });
	}

	// Indikator lokal murni dari 48 bar candle OKX (ATR-14, EMA-20, RSI-14, Swing Range).
	const struktur = $derived.by(() => {
		if (candles.length < 15) return null;
		const asc = [...candles].sort((a, b) => a.t - b.t);
		const closes = asc.map((c) => c.c);
		const tinggi = Math.max(...asc.map((c) => c.h));
		const rendah = Math.min(...asc.map((c) => c.l));
		const akhir = closes[closes.length - 1];
		const lebar = tinggi - rendah;

		const trs: number[] = [];
		for (let i = 1; i < asc.length; i++) {
			const h = asc[i].h, l = asc[i].l, pc = asc[i - 1].c;
			trs.push(Math.max(h - l, Math.abs(h - pc), Math.abs(l - pc)));
		}
		const atr14 = trs.slice(-14).reduce((a, b) => a + b, 0) / Math.min(14, trs.length);

		const k = 2 / (20 + 1);
		let ema20 = closes[0];
		for (let i = 1; i < closes.length; i++) ema20 = closes[i] * k + ema20 * (1 - k);

		let g = 0, ls = 0;
		const start = Math.max(1, closes.length - 14);
		for (let i = start; i < closes.length; i++) {
			const diff = closes[i] - closes[i - 1];
			if (diff > 0) g += diff;
			else ls -= diff;
		}
		const rsi14 = ls === 0 ? 100 : 100 - 100 / (1 + g / ls);

		return {
			tinggi,
			rendah,
			atr14,
			ema20,
			rsi14,
			bias: akhir >= ema20 ? 'BULLISH' : 'BEARISH',
			posisi: lebar > 0 ? ((akhir - rendah) / lebar) * 100 : 0
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
		<section class="flex flex-wrap items-center justify-between gap-2">
			<div class="flex flex-wrap items-center gap-2">
				<label class="label-mikro font-mono text-text-3" for="pilih-simbol">SIMBOL</label>
				<input
					type="text"
					bind:value={filterSimbol}
					placeholder="Filter (SOL, ETH…)"
					class="min-h-[40px] w-36 rounded-control border border-line bg-surface-2 px-2.5 font-mono text-11 uppercase text-text focus:border-accent focus:outline-hidden"
				/>
				<select
					id="pilih-simbol"
					class="min-h-[40px] rounded-control border border-line bg-surface px-2.5 font-mono text-12 text-text"
					value={simbol}
					onchange={(e) => void muatSimbol((e.currentTarget as HTMLSelectElement).value, interval)}
				>
					{#each universeFiltered as s (s)}
						<option value={s}>{s}</option>
					{/each}
				</select>
				<span class="text-11 text-text-3 font-mono">{universe.length} pair OKX</span>
			</div>
			<div class="flex flex-wrap items-center gap-1 font-mono text-11">
				<span class="label-mikro text-text-3 mr-1">TIMEFRAME</span>
				{#each INTERVALS as tf (tf)}
					<button
						type="button"
						class="rounded border px-2.5 py-1 cursor-pointer {interval === tf ? 'border-accent bg-accent/15 text-accent font-bold' : 'border-line text-text-3 hover:text-text'}"
						onclick={() => void muatSimbol(simbol, tf)}
					>
						{tf}
					</button>
				{/each}
				<button
					type="button"
					onclick={() => void muatSimbol(simbol, interval)}
					class="ml-1 rounded border border-line bg-surface px-2.5 py-1 text-text-2 hover:border-accent hover:text-accent cursor-pointer"
					title="Segarkan data koin"
				>
					⟳
				</button>
			</div>
		</section>

		<section class="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
			<div class="rounded-card border border-line bg-surface p-4">
				<div class="label-mikro font-mono text-text-3">HARGA ({simbol})</div>
				<div class="mt-1 font-mono text-17 font-bold text-text">${fmtHarga(ticker.last_price)}</div>
			</div>
			<div class="rounded-card border border-line bg-surface p-4">
				<div class="label-mikro font-mono text-text-3">PERUBAHAN 24 JAM</div>
				<div
					class="mt-1 font-mono text-17 font-bold"
					class:text-pos={(ticker.change_pct_ ?? 0) > 0}
					class:text-neg={(ticker.change_pct_ ?? 0) < 0}
					class:text-text={(ticker.change_pct_ ?? 0) === 0}
				>
					{ticker.change_pct_ == null ? '—' : `${ticker.change_pct_ > 0 ? '+' : ''}${Number(ticker.change_pct_).toFixed(2)}%`}
				</div>
			</div>
			<div class="rounded-card border border-line bg-surface p-4">
				<div class="label-mikro font-mono text-text-3">TERTINGGI 24H</div>
				<div class="mt-1 font-mono text-17 font-bold text-text">${fmtHarga(ticker.high_)}</div>
			</div>
			<div class="rounded-card border border-line bg-surface p-4">
				<div class="label-mikro font-mono text-text-3">TERENDAH 24H</div>
				<div class="mt-1 font-mono text-17 font-bold text-text">${fmtHarga(ticker.low_)}</div>
			</div>
			<div class="rounded-card border border-line bg-surface p-4">
				<div class="label-mikro font-mono text-text-3">VOLUME 24H (QUOTE)</div>
				<div class="mt-1 font-mono text-17 font-bold text-accent">{fmtVol(ticker.volume_)}</div>
			</div>
		</section>

		{#if struktur}
			<section class="rounded-card border border-line bg-surface p-4">
				<div class="flex flex-wrap items-center justify-between gap-2">
					<h2 class="text-13 font-bold text-text">Indikator lokal OKX · {interval} (48 bar)</h2>
					<span class="rounded border px-2 py-0.5 font-mono text-10 font-bold {struktur.bias === 'BULLISH' ? 'border-pos/35 bg-pos/10 text-pos' : 'border-neg/35 bg-neg/10 text-neg'}">
						BIAS EMA-20: {struktur.bias}
					</span>
				</div>
				<dl class="mt-3 grid gap-3 text-12 sm:grid-cols-3 lg:grid-cols-6">
					<div>
						<dt class="text-text-3">Swing tinggi</dt>
						<dd class="font-mono text-14 font-bold text-text">${fmtHarga(struktur.tinggi)}</dd>
					</div>
					<div>
						<dt class="text-text-3">Swing rendah</dt>
						<dd class="font-mono text-14 font-bold text-text">${fmtHarga(struktur.rendah)}</dd>
					</div>
					<div>
						<dt class="text-text-3">EMA-20</dt>
						<dd class="font-mono text-14 font-bold text-accent">${fmtHarga(struktur.ema20)}</dd>
					</div>
					<div>
						<dt class="text-text-3">RSI-14</dt>
						<dd class="font-mono text-14 font-bold {struktur.rsi14 >= 70 ? 'text-neg' : struktur.rsi14 <= 30 ? 'text-pos' : 'text-text'}">{struktur.rsi14.toFixed(1)}</dd>
					</div>
					<div>
						<dt class="text-text-3">ATR-14</dt>
						<dd class="font-mono text-14 font-bold text-text">${fmtHarga(struktur.atr14)}</dd>
					</div>
					<div>
						<dt class="text-text-3">Posisi rentang</dt>
						<dd class="font-mono text-14 font-bold text-text">{struktur.posisi.toFixed(1)}%</dd>
					</div>
				</dl>
				<div class="mt-3 h-2 w-full overflow-hidden rounded bg-surface-2 border border-line-soft">
					<div
						class="h-full bg-accent transition-all"
						style={`width: ${Math.max(0, Math.min(100, struktur.posisi)).toFixed(1)}%`}
					></div>
				</div>
				<p class="mt-2 text-11 text-text-3">
					Dihitung lokal di browser langsung dari 48 candle OKX ({interval}), bukan dari engine eksternal yang mati.
				</p>
			</section>
		{/if}

		<section class="rounded-card border border-line bg-surface p-4">
			<div class="flex flex-wrap items-center justify-between gap-2">
				<h2 class="text-13 font-bold text-text">15 Candle Terbaru ({interval})</h2>
				<span class="font-mono text-10 text-text-3">Sumber: OKX Public</span>
			</div>
			<div class="mt-2 overflow-x-auto">
				<table class="w-full text-11 text-left">
					<thead class="border-b border-line text-10 text-text-3 font-mono">
						<tr>
							<th class="px-2 py-1.5">Waktu</th>
							<th class="px-2 py-1.5 text-right">Open</th>
							<th class="px-2 py-1.5 text-right">High</th>
							<th class="px-2 py-1.5 text-right">Low</th>
							<th class="px-2 py-1.5 text-right">Close</th>
							<th class="px-2 py-1.5 text-right">Bar %</th>
							<th class="px-2 py-1.5 text-right">Volume</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-line-soft font-mono">
						{#each [...candles].slice(-15).reverse() as c (c.t)}
							{@const chg = c.o > 0 ? ((c.c - c.o) / c.o) * 100 : 0}
							<tr class="hover:bg-surface-2/60">
								<td class="px-2 py-1.5 text-text-3">{waktu(c.t)}</td>
								<td class="px-2 py-1.5 text-right text-text-2">{fmtHarga(c.o)}</td>
								<td class="px-2 py-1.5 text-right text-pos">{fmtHarga(c.h)}</td>
								<td class="px-2 py-1.5 text-right text-neg">{fmtHarga(c.l)}</td>
								<td class="px-2 py-1.5 text-right font-bold text-text">{fmtHarga(c.c)}</td>
								<td class="px-2 py-1.5 text-right {chg >= 0 ? 'text-pos' : 'text-neg'}">{chg >= 0 ? '+' : ''}{chg.toFixed(2)}%</td>
								<td class="px-2 py-1.5 text-right text-text-3">{Math.round(c.v).toLocaleString('en-US')}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</section>
	</div>
{/if}
