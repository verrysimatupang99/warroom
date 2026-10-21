<script lang="ts">
	/**
	 * ServerTencentView.svelte
	 * Dashboard interaktif untuk eksplorasi data tarikan dari Node Server Tencent via Tailscale WireGuard.
	 * URL Endpoint Asli: http://100.126.10.74:8790
	 */
	import { onMount } from 'svelte';

	interface LevelData {
		symbol: string;
		side: string;
		price: number;
		atr: number;
		status: string;
		reason?: string;
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

	let statusHealth = $state<'loading' | 'ok' | 'error'>('loading');
	let healthData = $state<any>(null);
	let dxyData = $state<any>(null);
	let universeList = $state<string[]>([]);
	let selectedSymbol = $state('BTCUSDT');
	let activeMarket = $state<'crypto' | 'forex'>('crypto');
	let selectedPlay = $state('scalping');

	let levelResult = $state<LevelData | null>(null);
	let tickerResult = $state<any>(null);
	let klinesResult = $state<any[]>([]);
	let loadingData = $state(false);

	async function loadHealthAndDxy() {
		try {
			const resH = await fetch('/api/v1/tencent/health');
			if (resH.ok) {
				healthData = await resH.json();
				statusHealth = 'ok';
			} else {
				statusHealth = 'error';
			}

			const resDxy = await fetch('/api/v1/tencent/forex/dxy');
			if (resDxy.ok) dxyData = await resDxy.json();

			const resUniv = await fetch('/api/v1/tencent/universe');
			if (resUniv.ok) {
				const u = await resUniv.json();
				universeList = u.symbols || [];
			}
		} catch (e) {
			statusHealth = 'error';
		}
	}

	async function queryTencentData() {
		loadingData = true;
		try {
			if (activeMarket === 'crypto') {
				const [resL, resT, resK] = await Promise.all([
					fetch(`/api/v1/tencent/crypto/levels?symbol=${selectedSymbol}&play=${selectedPlay}`),
					fetch(`/api/v1/tencent/ticker?symbol=${selectedSymbol}`),
					fetch(`/api/v1/tencent/klines?market=crypto&symbol=${selectedSymbol}&interval=1h&limit=15`)
				]);
				if (resL.ok) levelResult = await resL.json();
				if (resT.ok) tickerResult = await resT.json();
				if (resK.ok) {
					const k = await resK.json();
					klinesResult = k.candles || [];
				}
			} else {
				const [resL, resK] = await Promise.all([
					fetch(`/api/v1/tencent/forex/levels?symbol=XAUUSD`),
					fetch(`/api/v1/tencent/klines?market=forex&symbol=XAUUSD&interval=60&limit=15`)
				]);
				if (resL.ok) levelResult = await resL.json();
				if (resK.ok) {
					const k = await resK.json();
					klinesResult = k.candles || [];
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
		loadHealthAndDxy();
		queryTencentData();
	});
</script>

<div class="space-y-5">
	<!-- HEADER KONEKSI TAILSCALE TENCENT -->
	<div class="rounded-card border border-line bg-surface p-4 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
		<div>
			<div class="flex items-center gap-2.5">
				<h1 class="text-16 font-bold text-text">Node Tencent (Tailscale WireGuard)</h1>
				<span class="rounded px-2 py-0.5 text-10 font-mono font-bold border {statusHealth === 'ok' ? 'bg-pos/15 text-pos border-pos/30' : 'bg-neg/15 text-neg border-neg/30'}">
					{statusHealth === 'ok' ? 'WIREGUARD CONNECTED' : 'DISCONNECTED'}
				</span>
			</div>
			<p class="text-12 text-text-3 mt-1 font-mono">
				Tunnel: <span class="text-accent">http://100.126.10.74:8790</span> · Host: <span class="text-text-2">vm-0-10-ubuntu.tail3e1951.ts.net</span>
			</p>
		</div>

		<div class="flex items-center gap-3 font-mono text-11">
			<div class="p-2 rounded bg-surface-2 border border-line">
				<span class="text-text-3 block text-10">DXY TICKER</span>
				<span class="font-bold {dxyData?.change_pct >= 0 ? 'text-pos' : 'text-neg'}">
					{dxyData?.change_pct != null ? `${dxyData.change_pct > 0 ? '+' : ''}${dxyData.change_pct.toFixed(3)}%` : '—'}
				</span>
			</div>
			<div class="p-2 rounded bg-surface-2 border border-line">
				<span class="text-text-3 block text-10">CRYPTO UNIVERSE</span>
				<span class="font-bold text-accent">{universeList.length} Symbols</span>
			</div>
			<a 
				href="http://100.126.10.74:8790/docs" 
				target="_blank" 
				rel="noreferrer"
				class="px-3 py-2 rounded bg-accent/15 border border-accent/40 text-accent font-bold hover:bg-accent/25 transition-colors"
			>
				Open API Docs ↗
			</a>
		</div>
	</div>

	<!-- KONTROL PEMILIHAN MARKET & SIMBOL -->
	<div class="p-3 rounded-card border border-line bg-surface-2 flex flex-wrap items-center justify-between gap-3 font-mono text-12">
		<div class="flex items-center gap-2">
			<button 
				type="button" 
				class="px-3 py-1.5 rounded cursor-pointer transition-colors {activeMarket === 'crypto' ? 'bg-accent text-canvas font-bold' : 'bg-surface text-text-3 border border-line hover:text-text'}"
				onclick={() => { activeMarket = 'crypto'; selectedSymbol = 'BTCUSDT'; queryTencentData(); }}
			>
				Crypto Universe
			</button>
			<button 
				type="button" 
				class="px-3 py-1.5 rounded cursor-pointer transition-colors {activeMarket === 'forex' ? 'bg-accent text-canvas font-bold' : 'bg-surface text-text-3 border border-line hover:text-text'}"
				onclick={() => { activeMarket = 'forex'; selectedSymbol = 'XAUUSD'; queryTencentData(); }}
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
					onchange={queryTencentData}
					class="bg-surface border border-line rounded px-2.5 py-1 text-text focus:outline-hidden focus:border-accent"
				>
					{#each universeList as sym}
						<option value={sym}>{sym}</option>
					{/each}
				</select>

				<label for="play-select" class="text-text-3 ml-2">Mode:</label>
				<select 
					id="play-select"
					bind:value={selectedPlay} 
					onchange={queryTencentData}
					class="bg-surface border border-line rounded px-2.5 py-1 text-text focus:outline-hidden focus:border-accent"
				>
					<option value="scalping">Scalping (5m)</option>
					<option value="swing">Swing (1h/4h)</option>
				</select>
			</div>
		{/if}

		<button 
			type="button" 
			onclick={queryTencentData} 
			class="px-3 py-1 rounded bg-surface border border-line hover:border-accent text-accent cursor-pointer ml-auto"
		>
			{loadingData ? 'Tarik Data...' : 'Segarkan Data ⟳'}
		</button>
	</div>

	<!-- HASIL TARIKAN REALTIME DARI TENCENT -->
	<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
		<!-- KARTU 1: LEVEL & PUTUSAN RULES TENCENT -->
		<div class="rounded-card border border-line bg-surface p-4 space-y-3 font-mono">
			<div class="flex items-center justify-between border-b border-line pb-2">
				<span class="text-13 font-bold text-text flex items-center gap-2">
					<span class="w-2 h-2 rounded-full {levelResult?.status === 'OK' ? 'bg-pos' : 'bg-warn'}"></span>
					Level Kalkulasi: {levelResult?.symbol ?? selectedSymbol}
				</span>
				<span class="px-2 py-0.5 rounded text-10 font-bold border {levelResult?.status === 'OK' ? 'bg-pos/15 text-pos border-pos/30' : 'bg-neg/15 text-neg border-neg/30'}">
					{levelResult?.status ?? 'LOADING'}
				</span>
			</div>

			{#if levelResult}
				<div class="space-y-2 text-11">
					<div class="grid grid-cols-3 gap-2 p-2 rounded bg-surface-2 border border-line">
						<div>
							<span class="text-text-3 block text-10">HARGA SAAT INI</span>
							<span class="font-bold text-text text-13">{levelResult.price}</span>
						</div>
						<div>
							<span class="text-text-3 block text-10">ARAH BIAS</span>
							<span class="font-bold {levelResult.side === 'LONG' ? 'text-pos' : 'text-neg'} text-13">{levelResult.side}</span>
						</div>
						<div>
							<span class="text-text-3 block text-10">VOLATILITAS ATR</span>
							<span class="font-bold text-accent text-13">{levelResult.atr?.toFixed(2)}</span>
						</div>
					</div>

					{#if levelResult.status === 'OK' && levelResult.levels}
						<div class="p-3 rounded bg-pos/10 border border-pos/25 space-y-2 mt-2">
							<div class="text-11 font-bold text-pos">REKOMENDASI LEVEL VALID:</div>
							<div class="grid grid-cols-3 gap-2 font-mono">
								<div><span class="text-10 text-text-3">ENTRY:</span> <b class="text-text">{levelResult.levels.entry}</b></div>
								<div><span class="text-10 text-text-3">SL:</span> <b class="text-neg">{levelResult.levels.sl}</b></div>
								<div><span class="text-10 text-text-3">TP1:</span> <b class="text-pos">{levelResult.levels.tp1}</b></div>
							</div>
							<div class="text-10 text-text-3 pt-1 border-t border-pos/20">
								Zona: {levelResult.levels.zone} [{levelResult.levels.zone_low} - {levelResult.levels.zone_high}] · Jarak Risiko: {levelResult.levels.risk_pct}%
							</div>
						</div>
					{:else if levelResult.reason}
						<div class="p-3 rounded bg-surface-2 border border-line text-warn text-11 mt-2">
							<span class="font-bold block">Status Setup: DITOLAK</span>
							Alasan: {levelResult.reason}
						</div>
					{/if}
				</div>
			{/if}
		</div>

		<!-- KARTU 2: TICKER & DATA PASAR 24 JAM -->
		<div class="rounded-card border border-line bg-surface p-4 space-y-3 font-mono">
			<div class="flex items-center justify-between border-b border-line pb-2">
				<span class="text-13 font-bold text-text">Live Ticker Stats</span>
				<span class="text-10 text-text-3">FEED: {tickerResult?.source?.toUpperCase() ?? 'TENCENT'}</span>
			</div>

			{#if tickerResult}
				<div class="grid grid-cols-2 gap-2 text-11">
					<div class="p-2.5 rounded bg-surface-2 border border-line">
						<span class="text-text-3 block text-10">LAST PRICE</span>
						<span class="font-bold text-text text-14">${tickerResult.last_price?.toLocaleString()}</span>
					</div>
					<div class="p-2.5 rounded bg-surface-2 border border-line">
						<span class="text-text-3 block text-10">24H CHANGE</span>
						<span class="font-bold text-14 {tickerResult.change_pct_24h >= 0 ? 'text-pos' : 'text-neg'}">
							{tickerResult.change_pct_24h > 0 ? '+' : ''}{tickerResult.change_pct_24h}%
						</span>
					</div>
					<div class="p-2.5 rounded bg-surface-2 border border-line">
						<span class="text-text-3 block text-10">24H HIGH</span>
						<span class="text-text">${tickerResult.high_24h?.toLocaleString()}</span>
					</div>
					<div class="p-2.5 rounded bg-surface-2 border border-line">
						<span class="text-text-3 block text-10">24H LOW</span>
						<span class="text-text">${tickerResult.low_24h?.toLocaleString()}</span>
					</div>
				</div>
			{:else}
				<div class="py-6 text-center text-11 text-text-3 font-sans">
					Pilih pair crypto di atas untuk melihat data statistik 24 jam real-time.
				</div>
			{/if}
		</div>
	</div>

	<!-- TABEL CANDLES OHLCV TERAKHIR -->
	<div class="rounded-card border border-line bg-surface p-4 space-y-3 font-mono">
		<div class="flex items-center justify-between border-b border-line pb-2">
			<div>
				<h3 class="text-13 font-bold text-text">Candles OHLCV Feed ({activeMarket.toUpperCase()})</h3>
				<span class="text-11 text-text-3">15 Lilin Candle Terakhir Langsung dari Node Tencent</span>
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
							<th class="py-1.5 px-2">Waktu (Epoch)</th>
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
								<td class="py-1.5 px-2 text-text-3">{c.t}</td>
								<td class="py-1.5 px-2 text-text">{c.o}</td>
								<td class="py-1.5 px-2 text-pos">{c.h}</td>
								<td class="py-1.5 px-2 text-neg">{c.l}</td>
								<td class="py-1.5 px-2 font-bold text-text">{c.c}</td>
								<td class="py-1.5 px-2 text-right text-text-3">{c.v?.toLocaleString()}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	</div>
</div>
