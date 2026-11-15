<script lang="ts">
	/**
	 * ServerTencentView.svelte
	 * Eksplorasi feed data pasar langsung: OKX (crypto), Yahoo Finance (forex/IHSG),
	 * dan MT5 Bridge multi-akun.
	 */
	import { onMount } from 'svelte';

	interface LevelData {
		symbol: string;
		side: string;
		price: number;
		atr: number;
		status: string;
		reason?: string;
		source_mode?: string;
		rsi14?: number | null;
		ema20?: number | null;
		swing_high?: number | null;
		swing_low?: number | null;
		levels?: {
			entry: number;
			sl: number;
			tp1: number;
			tp2: number;
			risk: number;
			risk_pct: number;
			zone: string;
			zone_low: number;
			zone_high: number;
			order_type: string;
		};
	}

	interface Mt5Acc {
		account: string;
		broker?: string;
		currency?: string;
		cent_factor?: number;
		primary?: boolean;
		connected?: boolean;
		seconds_ago?: number | null;
		balance?: number | null;
		equity?: number | null;
		floating_pnl?: number | null;
		positions?: number;
		pending?: number;
	}

	let statusSumber = $state<'loading' | 'lokal' | 'node' | 'error'>('loading');
	let healthData = $state<any>(null);
	let dxyData = $state<any>(null);
	let universeList = $state<string[]>([]);
	let selectedSymbol = $state('BTCUSDT');
	let activeMarket = $state<'crypto' | 'forex'>('crypto');
	let mt5List = $state<Mt5Acc[]>([]);

	let levelResult = $state<LevelData | null>(null);
	let tickerResult = $state<any>(null);
	let klinesResult = $state<any[]>([]);
	let loadingData = $state(false);

	function fmtEpoch(t: unknown): string {
		if (t == null) return '—';
		const num = Number(t);
		if (!isFinite(num)) return String(t);
		const d = new Date(num < 1e12 ? num * 1000 : num);
		if (isNaN(d.getTime())) return String(t);
		const pad = (x: number) => String(x).padStart(2, '0');
		return `${pad(d.getDate())}/${pad(d.getMonth() + 1)} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
	}

	function fmtPrice(v: number | null | undefined): string {
		if (v == null || !isFinite(v)) return '—';
		if (v >= 100) return v.toLocaleString(undefined, { maximumFractionDigits: 2 });
		if (v >= 1) return v.toLocaleString(undefined, { maximumFractionDigits: 4 });
		return v.toLocaleString(undefined, { maximumFractionDigits: 6 });
	}

	function fmtVol(v: number | null | undefined): string {
		if (v == null || !isFinite(v)) return '—';
		if (v >= 1e9) return `$${(v / 1e9).toFixed(2)}B`;
		if (v >= 1e6) return `$${(v / 1e6).toFixed(2)}M`;
		if (v >= 1e3) return `$${(v / 1e3).toFixed(1)}K`;
		return `$${v.toFixed(0)}`;
	}

	function computeCryptoLevelsLocal(sym: string, candles: any[]): LevelData | null {
		if (!candles || candles.length < 15) return null;
		const asc = [...candles].sort((a, b) => Number(a.t) - Number(b.t));
		const closes = asc.map((c) => Number(c.c));
		const highs = asc.map((c) => Number(c.h));
		const lows = asc.map((c) => Number(c.l));
		const lastClose = closes[closes.length - 1];

		// ATR-14
		const trs: number[] = [];
		for (let i = 1; i < asc.length; i++) {
			const h = highs[i], l = lows[i], pc = closes[i - 1];
			trs.push(Math.max(h - l, Math.abs(h - pc), Math.abs(l - pc)));
		}
		const atrSlice = trs.slice(-14);
		const atr = atrSlice.reduce((a, b) => a + b, 0) / atrSlice.length;

		// EMA-20
		const k = 2 / (20 + 1);
		let ema = closes[0];
		for (let i = 1; i < closes.length; i++) ema = closes[i] * k + ema * (1 - k);

		// RSI-14
		let gains = 0, losses = 0;
		const startRsi = Math.max(1, closes.length - 14);
		for (let i = startRsi; i < closes.length; i++) {
			const diff = closes[i] - closes[i - 1];
			if (diff > 0) gains += diff;
			else losses -= diff;
		}
		const avgG = gains / 14;
		const avgL = losses / 14;
		const rsi14 = avgL === 0 ? 100 : 100 - 100 / (1 + avgG / avgL);

		const recentHigh = Math.max(...highs.slice(-24));
		const recentLow = Math.min(...lows.slice(-24));
		const side = lastClose >= ema ? 'LONG' : 'SHORT';
		const sl = side === 'LONG' ? lastClose - 1.5 * atr : lastClose + 1.5 * atr;
		const risk = Math.abs(lastClose - sl);
		const tp1 = side === 'LONG' ? lastClose + 2.0 * risk : lastClose - 2.0 * risk;
		const tp2 = side === 'LONG' ? lastClose + 3.0 * risk : lastClose - 3.0 * risk;
		const riskPct = lastClose > 0 ? (risk / lastClose) * 100 : 0;

		return {
			symbol: sym,
			side,
			price: lastClose,
			atr,
			status: 'OK',
			source_mode: 'KALKULASI LOKAL OKX (48 BAR)',
			rsi14,
			ema20: ema,
			swing_high: recentHigh,
			swing_low: recentLow,
			levels: {
				entry: lastClose,
				sl,
				tp1,
				tp2,
				risk,
				risk_pct: Number(riskPct.toFixed(2)),
				zone: side === 'LONG' ? 'EMA-20 Support' : 'EMA-20 Resistance',
				zone_low: recentLow,
				zone_high: recentHigh,
				order_type: 'LIMIT / RETEST'
			}
		};
	}

	async function loadHealthAndDxy() {
		try {
			const [resH, resDxy, resUniv, resMt5] = await Promise.all([
				fetch('/api/v1/tencent/health', { credentials: 'include' }),
				fetch('/api/v1/tencent/forex/dxy', { credentials: 'include' }),
				fetch('/api/v1/tencent/universe', { credentials: 'include' }),
				fetch('/api/v1/tencent/mt5/accounts', { credentials: 'include' })
			]);
			if (resH.ok) {
				healthData = await resH.json();
				statusSumber = healthData?.mode === 'lokal' ? 'lokal' : 'node';
			} else {
				statusSumber = 'error';
			}
			if (resDxy.ok) dxyData = await resDxy.json();
			if (resUniv.ok) {
				const u = await resUniv.json();
				universeList = u.symbols || [];
			}
			if (resMt5.ok) {
				const m = await resMt5.json();
				mt5List = m.accounts || [];
			}
		} catch {
			statusSumber = 'error';
		}
	}

	async function queryTencentData() {
		loadingData = true;
		try {
			if (activeMarket === 'crypto') {
				const [resT, resK] = await Promise.all([
					fetch(`/api/v1/tencent/ticker?symbol=${selectedSymbol}`, { credentials: 'include' }),
					fetch(`/api/v1/tencent/klines?market=crypto&symbol=${selectedSymbol}&interval=1h&limit=48`, { credentials: 'include' })
				]);
				if (resT.ok) {
					const tj = await resT.json();
					tickerResult = tj?.error ? null : tj;
				} else {
					tickerResult = null;
				}
				if (resK.ok) {
					const k = await resK.json();
					const candles = k.candles || [];
					klinesResult = candles.slice(-15).reverse();
					levelResult = computeCryptoLevelsLocal(selectedSymbol, candles);
				} else {
					klinesResult = [];
					levelResult = null;
				}
			} else {
				const [resL, resK] = await Promise.all([
					fetch(`/api/v1/tencent/forex/levels?symbol=XAUUSD`, { credentials: 'include' }),
					fetch(`/api/v1/tencent/klines?market=forex&symbol=XAUUSD&interval=60&limit=24`, { credentials: 'include' })
				]);
				if (resL.ok) {
					const lj = await resL.json();
					levelResult = lj?.error ? null : lj;
				} else {
					levelResult = null;
				}
				if (resK.ok) {
					const k = await resK.json();
					klinesResult = (k.candles || []).slice(-15).reverse();
				}
				tickerResult = null;
			}
		} catch (e) {
			console.error(e);
		} finally {
			loadingData = false;
		}
	}

	onMount(() => {
		void loadHealthAndDxy();
		void queryTencentData();
	});
</script>

<div class="space-y-5">
	<!-- HEADER SUMBER DATA -->
	<div class="rounded-card border border-line bg-surface p-4 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
		<div>
			<div class="flex items-center gap-2.5">
				<h1 class="text-16 font-bold text-text">Sumber Data Pasar</h1>
				<span class="rounded px-2 py-0.5 text-10 font-mono font-bold border {statusSumber === 'error' ? 'bg-neg/15 text-neg border-neg/30' : 'bg-pos/15 text-pos border-pos/30'}">
					{statusSumber === 'lokal'
						? 'OKX · YAHOO · MT5 BRIDGE'
						: statusSumber === 'node'
							? 'NODE UPSTREAM'
							: statusSumber === 'loading'
								? 'MEMUAT'
								: 'TERPUTUS'}
				</span>
			</div>
			<p class="text-12 text-text-3 mt-1 font-mono">
				{#if statusSumber === 'lokal'}
					Feed aktif: <span class="text-accent">OKX Publik</span> (crypto) · <span class="text-text-2">Yahoo Finance</span> (forex &amp; IHSG) · <span class="text-pos">MT5 Bridge</span>
				{:else if statusSumber === 'node'}
					Upstream: <span class="text-accent">{healthData?.base ?? 'node data'}</span>
				{:else}
					<span class="text-neg">API tidak menjawab</span>
				{/if}
			</p>
		</div>

		<div class="flex items-center gap-3 font-mono text-11">
			<div class="p-2 rounded bg-surface-2 border border-line">
				<span class="text-text-3 block text-10">DXY TICKER</span>
				<span class="font-bold {(dxyData?.change_pct ?? 0) >= 0 ? 'text-pos' : 'text-neg'}">
					{dxyData?.change_pct != null ? `${dxyData.change_pct > 0 ? '+' : ''}${Number(dxyData.change_pct).toFixed(3)}%` : '—'}
				</span>
			</div>
			<div class="p-2 rounded bg-surface-2 border border-line">
				<span class="text-text-3 block text-10">CRYPTO UNIVERSE</span>
				<span class="font-bold text-accent">{universeList.length} Top Liquid</span>
			</div>
			<div class="p-2 rounded bg-surface-2 border border-line">
				<span class="text-text-3 block text-10">MT5 TERMINALS</span>
				<span class="font-bold text-pos">{mt5List.filter((a) => a.connected).length}/{mt5List.length} Live</span>
			</div>
		</div>
	</div>

	<!-- MT5 BRIDGE 3 AKUN -->
	{#if mt5List.length > 0}
		<div class="rounded-card border border-line bg-surface p-4 space-y-2.5 font-mono">
			<div class="flex items-center justify-between border-b border-line pb-2">
				<span class="text-13 font-bold text-text">Telemetri MT5 Bridge ({mt5List.length} Akun)</span>
				<span class="text-10 text-text-3">HEARTBEAT REAL-TIME</span>
			</div>
			<div class="overflow-x-auto">
				<table class="w-full text-11 text-left">
					<thead class="text-10 text-text-3 border-b border-line">
						<tr>
							<th class="py-1.5 px-2">Akun</th>
							<th class="py-1.5 px-2">Broker</th>
							<th class="py-1.5 px-2">Status</th>
							<th class="py-1.5 px-2 text-right">Saldo</th>
							<th class="py-1.5 px-2 text-right">Ekuitas</th>
							<th class="py-1.5 px-2 text-right">Floating</th>
							<th class="py-1.5 px-2 text-right">Pos / Pending</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-line-soft">
						{#each mt5List as acc (acc.account)}
							<tr class="hover:bg-surface-2/60">
								<td class="py-1.5 px-2 font-bold text-text">
									{acc.account}
									{#if acc.primary}<span class="ml-1 text-9 px-1 rounded bg-accent/15 text-accent">PRIMARY</span>{/if}
								</td>
								<td class="py-1.5 px-2 text-text-2">{acc.broker ?? '—'} · {acc.currency ?? 'USD'}</td>
								<td class="py-1.5 px-2">
									<span class="px-1.5 py-0.5 rounded text-10 font-bold {acc.connected ? 'bg-pos/15 text-pos' : 'bg-neg/15 text-neg'}">
										{acc.connected ? `LIVE (${acc.seconds_ago ?? 0}s)` : 'OFFLINE'}
									</span>
								</td>
								<td class="py-1.5 px-2 text-right text-text">{acc.balance != null ? acc.balance.toFixed(2) : '—'}</td>
								<td class="py-1.5 px-2 text-right font-bold text-text">{acc.equity != null ? acc.equity.toFixed(2) : '—'}</td>
								<td class="py-1.5 px-2 text-right {(acc.floating_pnl ?? 0) >= 0 ? 'text-pos' : 'text-neg'}">
									{acc.floating_pnl != null ? `${acc.floating_pnl >= 0 ? '+' : ''}${acc.floating_pnl.toFixed(2)}` : '—'}
								</td>
								<td class="py-1.5 px-2 text-right text-text-2">{acc.positions ?? 0} / {acc.pending ?? 0}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</div>
	{/if}

	<!-- KONTROL PEMILIHAN MARKET & SIMBOL -->
	<div class="p-3 rounded-card border border-line bg-surface-2 flex flex-wrap items-center justify-between gap-3 font-mono text-12">
		<div class="flex items-center gap-2">
			<button
				type="button"
				class="px-3 py-1.5 rounded cursor-pointer transition-colors {activeMarket === 'crypto' ? 'bg-accent text-canvas font-bold' : 'bg-surface text-text-3 border border-line hover:text-text'}"
				onclick={() => { activeMarket = 'crypto'; selectedSymbol = 'BTCUSDT'; void queryTencentData(); }}
			>
				Crypto Universe
			</button>
			<button
				type="button"
				class="px-3 py-1.5 rounded cursor-pointer transition-colors {activeMarket === 'forex' ? 'bg-accent text-canvas font-bold' : 'bg-surface text-text-3 border border-line hover:text-text'}"
				onclick={() => { activeMarket = 'forex'; selectedSymbol = 'XAUUSD'; void queryTencentData(); }}
			>
				Gold / Forex (XAUUSD)
			</button>
		</div>

		{#if activeMarket === 'crypto'}
			<div class="flex items-center gap-2">
				<label for="symbol-select" class="text-text-3">Simbol:</label>
				<select
					id="symbol-select"
					bind:value={selectedSymbol}
					onchange={() => void queryTencentData()}
					class="bg-surface border border-line rounded px-2.5 py-1 text-text focus:outline-hidden focus:border-accent"
				>
					{#each universeList as sym}
						<option value={sym}>{sym}</option>
					{/each}
				</select>
			</div>
		{/if}

		<button
			type="button"
			onclick={() => { void loadHealthAndDxy(); void queryTencentData(); }}
			class="px-3 py-1 rounded bg-surface border border-line hover:border-accent text-accent cursor-pointer ml-auto"
		>
			{loadingData ? 'Tarik Data...' : 'Segarkan Data ⟳'}
		</button>
	</div>

	<!-- HASIL FEED REAL-TIME -->
	<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
		<!-- KARTU 1: KALKULASI LEVEL TEKNIKAL -->
		<div class="rounded-card border border-line bg-surface p-4 space-y-3 font-mono">
			<div class="flex items-center justify-between border-b border-line pb-2">
				<span class="text-13 font-bold text-text flex items-center gap-2">
					<span class="w-2 h-2 rounded-full {levelResult?.status === 'OK' ? 'bg-pos' : 'bg-warn'}"></span>
					Level Kalkulasi: {levelResult?.symbol ?? selectedSymbol}
				</span>
				<span class="px-2 py-0.5 rounded text-10 font-bold border bg-surface-2 text-text-2 border-line">
					{levelResult?.source_mode ?? 'KALKULASI TEKNIKAL'}
				</span>
			</div>

			{#if !levelResult}
				<div class="py-6 text-center text-11 text-text-3 font-sans">Memuat kalkulasi level...</div>
			{:else}
				<div class="space-y-2 text-12">
					<div class="grid grid-cols-3 gap-2 bg-surface-2 p-2.5 rounded border border-line">
						<div>
							<span class="text-text-3 block text-10">HARGA TERAKHIR</span>
							<span class="font-bold text-text text-13">${fmtPrice(levelResult.price)}</span>
						</div>
						<div>
							<span class="text-text-3 block text-10">BIAS EMA-20</span>
							<span class="font-bold {levelResult.side === 'LONG' ? 'text-pos' : 'text-neg'} text-13">{levelResult.side}</span>
						</div>
						<div>
							<span class="text-text-3 block text-10">ATR-14 (1H)</span>
							<span class="font-bold text-accent text-13">{fmtPrice(levelResult.atr)}</span>
						</div>
					</div>

					{#if levelResult.rsi14 != null || levelResult.ema20 != null}
						<div class="grid grid-cols-3 gap-2 bg-surface-2 p-2 rounded border border-line text-11">
							<div><span class="text-text-3 block text-9">RSI-14</span><b class="text-text">{levelResult.rsi14?.toFixed(1) ?? '—'}</b></div>
							<div><span class="text-text-3 block text-9">EMA-20</span><b class="text-text">${fmtPrice(levelResult.ema20)}</b></div>
							<div><span class="text-text-3 block text-9">SWING 24H</span><b class="text-text-2">${fmtPrice(levelResult.swing_low)}–${fmtPrice(levelResult.swing_high)}</b></div>
						</div>
					{/if}

					{#if levelResult.levels}
						<div class="p-3 rounded bg-pos/10 border border-pos/25 space-y-2 mt-2">
							<div class="text-11 font-bold text-pos">REFERENSI ATR (1.5x SL · 2R/3R TP):</div>
							<div class="grid grid-cols-3 gap-2 font-mono">
								<div><span class="text-10 text-text-3">ENTRY:</span> <b class="text-text">${fmtPrice(levelResult.levels.entry)}</b></div>
								<div><span class="text-10 text-text-3">SL:</span> <b class="text-neg">${fmtPrice(levelResult.levels.sl)}</b></div>
								<div><span class="text-10 text-text-3">TP1:</span> <b class="text-pos">${fmtPrice(levelResult.levels.tp1)}</b></div>
							</div>
							<div class="text-10 text-text-3 pt-1 border-t border-pos/20">
								Zona: {levelResult.levels.zone} · Jarak SL: {levelResult.levels.risk_pct}% · TP2: ${fmtPrice(levelResult.levels.tp2)}
							</div>
						</div>
					{/if}
				</div>
			{/if}
		</div>

		<!-- KARTU 2: TICKER & DATA PASAR 24 JAM (FIXED SCHEMA) -->
		<div class="rounded-card border border-line bg-surface p-4 space-y-3 font-mono">
			<div class="flex items-center justify-between border-b border-line pb-2">
				<span class="text-13 font-bold text-text">Live Ticker Stats</span>
				<span class="text-10 text-text-3">FEED: {tickerResult?.source?.toUpperCase() ?? (activeMarket === 'forex' ? 'YAHOO FINANCE' : 'OKX-LOKAL')}</span>
			</div>

			{#if tickerResult}
				<div class="grid grid-cols-2 gap-2 text-11">
					<div class="p-2.5 rounded bg-surface-2 border border-line">
						<span class="text-text-3 block text-10">LAST PRICE</span>
						<span class="font-bold text-text text-14">${fmtPrice(tickerResult.last_price)}</span>
					</div>
					<div class="p-2.5 rounded bg-surface-2 border border-line">
						<span class="text-text-3 block text-10">24H CHANGE</span>
						<span class="font-bold text-14 {(tickerResult.change_pct_ ?? 0) >= 0 ? 'text-pos' : 'text-neg'}">
							{tickerResult.change_pct_ != null ? `${tickerResult.change_pct_ > 0 ? '+' : ''}${Number(tickerResult.change_pct_).toFixed(2)}%` : '—'}
						</span>
					</div>
					<div class="p-2.5 rounded bg-surface-2 border border-line">
						<span class="text-text-3 block text-10">24H HIGH / LOW</span>
						<span class="text-text">${fmtPrice(tickerResult.high_)} / ${fmtPrice(tickerResult.low_)}</span>
					</div>
					<div class="p-2.5 rounded bg-surface-2 border border-line">
						<span class="text-text-3 block text-10">24H VOLUME (QUOTE)</span>
						<span class="text-accent font-bold">{fmtVol(tickerResult.volume_)}</span>
					</div>
				</div>
			{:else}
				<div class="py-6 text-center text-11 text-text-3 font-sans">
					{activeMarket === 'forex'
						? 'Ticker 24h khusus universe crypto OKX; untuk XAUUSD gunakan panel Level Kalkulasi & OHLCV di samping/bawah.'
						: 'Pilih pair crypto di atas untuk melihat statistik ticker 24 jam OKX.'}
				</div>
			{/if}
		</div>
	</div>

	<!-- TABEL CANDLES OHLCV TERAKHIR -->
	<div class="rounded-card border border-line bg-surface p-4 space-y-3 font-mono">
		<div class="flex items-center justify-between border-b border-line pb-2">
			<div>
				<h3 class="text-13 font-bold text-text">Candles OHLCV Feed ({activeMarket.toUpperCase()})</h3>
				<span class="text-11 text-text-3">15 Lilin Candle Terbaru · {activeMarket === 'crypto' ? 'OKX Publik (1h)' : 'Yahoo Finance (1h)'}</span>
			</div>
			<span class="text-11 text-accent">{selectedSymbol}</span>
		</div>

		{#if klinesResult.length === 0}
			<div class="py-6 text-center text-11 text-text-3 font-sans">Memuat data candle...</div>
		{:else}
			<div class="overflow-x-auto">
				<table class="w-full text-11 text-left">
					<thead class="text-10 text-text-3 border-b border-line">
						<tr>
							<th class="py-1.5 px-2">Waktu</th>
							<th class="py-1.5 px-2">Open</th>
							<th class="py-1.5 px-2">High</th>
							<th class="py-1.5 px-2">Low</th>
							<th class="py-1.5 px-2">Close</th>
							<th class="py-1.5 px-2 text-right">Volume</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-line-soft">
						{#each klinesResult as c}
							<tr class="hover:bg-surface-2/60">
								<td class="py-1.5 px-2 text-text-3 whitespace-nowrap">{fmtEpoch(c.t)}</td>
								<td class="py-1.5 px-2 text-text">{fmtPrice(Number(c.o))}</td>
								<td class="py-1.5 px-2 text-pos">{fmtPrice(Number(c.h))}</td>
								<td class="py-1.5 px-2 text-neg">{fmtPrice(Number(c.l))}</td>
								<td class="py-1.5 px-2 font-bold text-text">{fmtPrice(Number(c.c))}</td>
								<td class="py-1.5 px-2 text-right text-text-3">{c.v != null ? Number(c.v).toLocaleString() : '—'}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	</div>
</div>
