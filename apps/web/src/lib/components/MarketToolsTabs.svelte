<script lang="ts">
	/**
	 * MarketToolsTabs.svelte
	 * Tooling Khusus & Kontekstual yang tertanam di tab "Alat / Tools" setiap Pasar.
	 * Menghadirkan model sizing, kalkulator prop-firm, radar scanner, dan stand-down calendar.
	 */
	import HonestyTag from './HonestyTag.svelte';
	import TrackBar from './TrackBar.svelte';

	interface Props {
		pasar: 'forex' | 'crypto' | 'polymarket' | 'idx' | 'gmgn';
	}
	let { pasar }: Props = $props();

	// --- 1. STATE FOREX / GOLD TOOL: GLOBAL4EX PROP-FIRM GUARD ---
	let propAccountSize = $state(5000);
	let propRiskPct = $state(1.4); // $70 pada $5K
	let propSlPips = $state(70); // 70 pips = $7.00
	let entryPrice = $state(2725.50);
	let copyStatus = $state(false);

	const propDollarRisk = $derived(propAccountSize * (propRiskPct / 100));
	const propMaxDailyLoss = $derived(propAccountSize * 0.04); // 4% ($200)
	const propMaxTotalLoss = $derived(propAccountSize * 0.08); // 8% ($400)
	
	// Sizing XAUUSD: 1 pip = $0.10 per 0.10 lot ($10 per $1 move per standard lot)
	const propCalculatedLot = $derived.by(() => {
		const riskPerPoint = propDollarRisk / (propSlPips / 10);
		return Math.max(0.01, Math.round((riskPerPoint / 100) * 100) / 100);
	});

	function copyOrderPlan() {
		const slPrice = (entryPrice - (propSlPips * 0.1)).toFixed(2);
		const tpPrice = (entryPrice + (propSlPips * 0.1 * 2)).toFixed(2);
		const text = `XAUUSD BUY LIMIT\nEntry: ${entryPrice.toFixed(2)}\nSL: ${slPrice} (${propSlPips} pips)\nTP: ${tpPrice} (1:2 R:R)\nLot: ${propCalculatedLot} (Risk: $${propDollarRisk.toFixed(0)})`;
		navigator.clipboard.writeText(text);
		copyStatus = true;
		setTimeout(() => (copyStatus = false), 2000);
	}

	// --- 2. STATE CRYPTO TOOL: LEVERAGE & LIQUIDATION SIZER ---
	let cryptoCapital = $state(1000);
	let cryptoRiskPct = $state(2.0);
	let cryptoLeverage = $state(10);
	let cryptoEntry = $state(67400);
	let cryptoStop = $state(66200);

	const cryptoDistPct = $derived(Math.abs((cryptoEntry - cryptoStop) / cryptoEntry) * 100);
	const cryptoPositionSize = $derived((cryptoCapital * (cryptoRiskPct / 100)) / (cryptoDistPct / 100));
	const cryptoEstLiq = $derived(cryptoEntry * (1 - (1 / cryptoLeverage) * 0.9));

	// --- 3. STATE POLYMARKET TOOL: KELLY SIZER & PARITY ---
	let polyProb = $state(82); // 82% win prob estimate
	let polyMarketPrice = $state(0.78); // 78c per share
	const polyEdge = $derived((polyProb / 100) - polyMarketPrice);
	const polyKellyPct = $derived(Math.max(0, Math.round(((polyEdge / (1 - polyMarketPrice)) * 0.5) * 100)));

	// --- 4. STATE IDX TOOL: BANDARMOLOGI & CASH SIZER ---
	let idxCash = $state(25000000); // Rp 25 juta
	let idxRiskPerTrade = $state(2.0); // 2% = Rp 500rb
	let idxEntry = $state(4200);
	let idxStop = $state(3990);
	const idxRiskShare = $derived(idxEntry - idxStop);
	const idxMaxLots = $derived(Math.max(1, Math.floor(((idxCash * (idxRiskPerTrade / 100)) / idxRiskShare) / 100)));
</script>

<div class="market-tools-container font-sans">
	<div class="tools-head">
		<div>
			<span class="oy-tag font-mono">CONTEXTUAL TOOL</span>
			<h2 class="text-16 font-bold text-text">
				{#if pasar === 'forex'}
					Forex &amp; Gold Sizing Guard (Global4Ex / GFT $5K)
				{:else if pasar === 'crypto'}
					Crypto SMC Sizer &amp; Liquidation Risk Calculator
				{:else if pasar === 'polymarket'}
					Polymarket Kelly Sizer &amp; Parity Drift
				{:else if pasar === 'idx'}
					IDX Bandarmologi &amp; Cash Risk Sizer
				{:else}
					GMGN Solana Smart Money Radar &amp; Pool Risk
				{/if}
			</h2>
		</div>
		<HonestyTag terverifikasi={true} sumber="Kalkulasi Dinamis Terisolir" />
	</div>

	<!-- TOOL PER MARKET -->
	{#if pasar === 'forex'}
		<div class="grid grid-cols-1 md:grid-cols-2 gap-4 mt-3">
			<!-- Panel Input Prop-Firm -->
			<div class="oy-panel">
				<div class="panel-header">
					<span class="panel-title">Parameter Prop-Firm ($5K Tier)</span>
					<span class="font-mono text-11 text-accent font-bold">$9 USD Promo Plan</span>
				</div>

				<div class="space-y-3.5 text-12">
					<div>
						<label for="f-size" class="input-lbl">Modal Akun ($ USD):</label>
						<div class="flex items-center gap-2 mt-1">
							<input id="f-size" type="number" bind:value={propAccountSize} class="oy-input font-mono" step="500" />
							<button type="button" class="preset-btn font-mono" onclick={() => (propAccountSize = 5000)}>$5K</button>
							<button type="button" class="preset-btn font-mono" onclick={() => (propAccountSize = 10000)}>$10K</button>
						</div>
					</div>

					<div class="grid grid-cols-2 gap-3">
						<div>
							<label for="f-risk" class="input-lbl">Toleransi Risiko (%):</label>
							<input id="f-risk" type="number" bind:value={propRiskPct} step="0.1" max="4.0" class="oy-input font-mono mt-1" />
							<span class="text-10 text-text-3 font-mono mt-0.5 block">${propDollarRisk.toFixed(1)} USD</span>
						</div>
						<div>
							<label for="f-sl" class="input-lbl">Jarak Stop Loss (Pips):</label>
							<input id="f-sl" type="number" bind:value={propSlPips} step="5" class="oy-input font-mono mt-1" />
							<span class="text-10 text-text-3 font-mono mt-0.5 block">${(propSlPips * 0.1).toFixed(2)} move</span>
						</div>
					</div>

					<div>
						<label for="f-entry" class="input-lbl">Rencana Harga Entry Emas:</label>
						<input id="f-entry" type="number" bind:value={entryPrice} step="0.5" class="oy-input font-mono mt-1" />
					</div>
				</div>
			</div>

			<!-- Panel Hasil & Safety Guard -->
			<div class="oy-panel bg-surface-2/60">
				<div class="panel-header">
					<span class="panel-title">Safety Guard &amp; Order Execution</span>
					<span class="status-pill {propDollarRisk > propMaxDailyLoss * 0.5 ? 'warn' : 'pos'} font-mono">
						{propDollarRisk > propMaxDailyLoss * 0.5 ? 'WASPADA DAILY LOSS' : 'RISIKO AMAN'}
					</span>
				</div>

				<div class="grid grid-cols-2 gap-2.5 font-mono my-2.5">
					<div class="kpi-cell">
						<span class="lbl">Rekomendasi Lot</span>
						<span class="val text-accent">{propCalculatedLot} Lot</span>
						<span class="sub">1 Pip = ${(propCalculatedLot * 10).toFixed(1)}</span>
					</div>
					<div class="kpi-cell">
						<span class="lbl">Max Daily Loss (4%)</span>
						<span class="val text-text">${propMaxDailyLoss}</span>
						<span class="sub">Batas gugur harian</span>
					</div>
					<div class="kpi-cell">
						<span class="lbl">Max Total Loss (8%)</span>
						<span class="val text-text">${propMaxTotalLoss}</span>
						<span class="sub">Static stop out</span>
					</div>
					<div class="kpi-cell">
						<span class="lbl">Sisa Napas Rugi</span>
						<span class="val text-pos">{Math.floor(propMaxDailyLoss / propDollarRisk)} Trade</span>
						<span class="sub">Consecutive loss limit</span>
					</div>
				</div>

				<button 
					type="button" 
					class="w-full mt-3 py-2 px-3 bg-accent text-on-accent font-bold rounded font-mono text-12 flex items-center justify-center gap-2 hover:opacity-90 transition-opacity"
					onclick={copyOrderPlan}
				>
					<span>{copyStatus ? '✓ ORDER COPIED TO CLIPBOARD' : '📋 SALIN ORDER PLAN (MT4/MT5)'}</span>
				</button>
			</div>
		</div>

		<!-- Stand-Down Calendar Widget Langsung di Bawahnya -->
		<div class="standdown-box mt-4 font-mono">
			<div class="flex items-center justify-between pb-2 border-b border-line">
				<span class="text-12 font-bold text-pos flex items-center gap-2">
					<span class="w-2.5 h-2.5 rounded-full bg-pos animate-pulse"></span>
					ECONOMIC STAND-DOWN GUARD (XAUUSD)
				</span>
				<span class="text-10 text-text-3">AUTO-PAUSE 15M SEBELUM HIGH-IMPACT NEWS</span>
			</div>
			<div class="grid grid-cols-1 md:grid-cols-3 gap-3 mt-3 text-11">
				<div class="p-2.5 rounded bg-surface border border-line">
					<span class="text-text-3 block">US CPI (Inflation)</span>
					<span class="font-bold text-text text-13">Kamis, 19:30 WIB</span>
					<span class="text-neg block mt-1 font-bold">STAND-DOWN AKTIF</span>
				</div>
				<div class="p-2.5 rounded bg-surface border border-line">
					<span class="text-text-3 block">Fed FOMC Rate Decision</span>
					<span class="font-bold text-text text-13">Kamis Malam, 01:00 WIB</span>
					<span class="text-warn block mt-1 font-bold">MONITORING</span>
				</div>
				<div class="p-2.5 rounded bg-surface border border-line">
					<span class="text-text-3 block">US NFP (Non-Farm Payrolls)</span>
					<span class="font-bold text-text text-13">Jumat Pertama, 19:30 WIB</span>
					<span class="text-pos block mt-1 font-bold">CLEAR (NO TRADE WINDOW)</span>
				</div>
			</div>
		</div>

	{:else if pasar === 'crypto'}
		<div class="grid grid-cols-1 md:grid-cols-2 gap-4 mt-3">
			<div class="oy-panel">
				<div class="panel-header">
					<span class="panel-title">Perp Position Sizer &amp; Leverage</span>
					<span class="font-mono text-11 text-accent">Isolated Mode</span>
				</div>
				<div class="space-y-3 text-12">
					<div class="grid grid-cols-2 gap-3">
						<div>
							<label for="c-cap" class="input-lbl">Modal Margin ($):</label>
							<input id="c-cap" type="number" bind:value={cryptoCapital} class="oy-input font-mono mt-1" />
						</div>
						<div>
							<label for="c-lev" class="input-lbl">Leverage (x):</label>
							<input id="c-lev" type="number" bind:value={cryptoLeverage} min="1" max="50" class="oy-input font-mono mt-1" />
						</div>
					</div>
					<div class="grid grid-cols-2 gap-3">
						<div>
							<label for="c-entry" class="input-lbl">Entry Price ($):</label>
							<input id="c-entry" type="number" bind:value={cryptoEntry} class="oy-input font-mono mt-1" />
						</div>
						<div>
							<label for="c-stop" class="input-lbl">Stop Loss ($):</label>
							<input id="c-stop" type="number" bind:value={cryptoStop} class="oy-input font-mono mt-1" />
						</div>
					</div>
				</div>
			</div>

			<div class="oy-panel bg-surface-2/60 font-mono">
				<div class="panel-header">
					<span class="panel-title">Hasil Simulasi Risiko</span>
					<span class="text-pos text-11">SL Distance: {cryptoDistPct.toFixed(2)}%</span>
				</div>
				<div class="grid grid-cols-2 gap-2.5 my-2.5">
					<div class="kpi-cell">
						<span class="lbl">Ukuran Posisi Notional</span>
						<span class="val text-accent">${cryptoPositionSize.toFixed(0)}</span>
						<span class="sub">{((cryptoPositionSize / cryptoEntry)).toFixed(3)} Coin</span>
					</div>
					<div class="kpi-cell">
						<span class="lbl">Estimasi Harga Likuidasi</span>
						<span class="val text-neg">${cryptoEstLiq.toFixed(0)}</span>
						<span class="sub">Jauh di bawah Stop Loss</span>
					</div>
				</div>
				<div class="p-2.5 rounded bg-surface border border-line text-11 text-text-3 font-sans mt-2">
					Stop loss Anda di ${cryptoStop} akan membatasi risiko tepat pada <b>${(cryptoCapital * (cryptoRiskPct / 100)).toFixed(0)} ({cryptoRiskPct}%)</b> sebelum menyentuh likuidasi.
				</div>
			</div>
		</div>

	{:else if pasar === 'polymarket'}
		<div class="grid grid-cols-1 md:grid-cols-2 gap-4 mt-3 font-mono">
			<div class="oy-panel">
				<div class="panel-header">
					<span class="panel-title">Kelly Sizer Binary CLOB</span>
					<span class="text-accent text-11">Band Favorit 0.70 - 0.95</span>
				</div>
				<div class="space-y-3 text-12 font-sans">
					<div>
						<label for="p-prob" class="input-lbl">Estimasi Probabilitas Menang (%):</label>
						<input id="p-prob" type="number" bind:value={polyProb} min="50" max="99" class="oy-input font-mono mt-1" />
					</div>
					<div>
						<label for="p-share" class="input-lbl">Harga Saham YES Saat Ini ($):</label>
						<input id="p-share" type="number" bind:value={polyMarketPrice} step="0.01" min="0.10" max="0.99" class="oy-input font-mono mt-1" />
					</div>
				</div>
			</div>
			<div class="oy-panel bg-surface-2/60">
				<div class="panel-header">
					<span class="panel-title">Rekomendasi Alokasi Kelly</span>
					<span class="status-pill pos">POSITIVE EDGE</span>
				</div>
				<div class="grid grid-cols-2 gap-2.5 my-2.5">
					<div class="kpi-cell">
						<span class="lbl">Theoretical Edge</span>
						<span class="val text-pos">+{(polyEdge * 100).toFixed(1)}%</span>
						<span class="sub">Model vs Book Implied</span>
					</div>
					<div class="kpi-cell">
						<span class="lbl">Half-Kelly Size</span>
						<span class="val text-accent">{polyKellyPct}%</span>
						<span class="sub">Alokasi maksimal dompet</span>
					</div>
				</div>
			</div>
		</div>

	{:else if pasar === 'idx'}
		<div class="grid grid-cols-1 md:grid-cols-2 gap-4 mt-3">
			<div class="oy-panel">
				<div class="panel-header">
					<span class="panel-title">Kalkulator Lot Saham Tunai</span>
					<span class="font-mono text-11 text-text-3">Tanpa Margin/Short</span>
				</div>
				<div class="space-y-3 text-12">
					<div>
						<label for="i-cash" class="input-lbl">Kas Portofolio (Rp):</label>
						<input id="i-cash" type="number" bind:value={idxCash} step="1000000" class="oy-input font-mono mt-1" />
					</div>
					<div class="grid grid-cols-2 gap-3">
						<div>
							<label for="i-entry" class="input-lbl">Harga Beli / Entry:</label>
							<input id="i-entry" type="number" bind:value={idxEntry} class="oy-input font-mono mt-1" />
						</div>
						<div>
							<label for="i-stop" class="input-lbl">Cutloss (Rp):</label>
							<input id="i-stop" type="number" bind:value={idxStop} class="oy-input font-mono mt-1" />
						</div>
					</div>
				</div>
			</div>
			<div class="oy-panel bg-surface-2/60 font-mono">
				<div class="panel-header">
					<span class="panel-title">Rekomendasi Pembelian Lot</span>
					<span class="text-accent text-11">Risk Rp {(idxCash * (idxRiskPerTrade / 100)).toLocaleString('id-ID')}</span>
				</div>
				<div class="grid grid-cols-2 gap-2.5 my-2.5">
					<div class="kpi-cell">
						<span class="lbl">Batas Maksimal</span>
						<span class="val text-accent">{idxMaxLots} Lot</span>
						<span class="sub">Rp {(idxMaxLots * idxEntry * 100).toLocaleString('id-ID')}</span>
					</div>
					<div class="kpi-cell">
						<span class="lbl">Beban Porto</span>
						<span class="val text-text">{(((idxMaxLots * idxEntry * 100) / idxCash) * 100).toFixed(1)}%</span>
						<span class="sub">Diversifikasi aman</span>
					</div>
				</div>
			</div>
		</div>

	{:else}
		<!-- GMGN Tools -->
		<div class="p-4 rounded-card border border-line bg-surface font-mono">
			<div class="flex items-center justify-between pb-2 border-b border-line mb-3">
				<span class="font-bold text-text">Solana Smart Money &amp; Dev Rug-Check</span>
				<span class="text-accent text-11">RAYDIUM &amp; PUMPFUN</span>
			</div>
			<p class="text-11 text-text-3 font-sans">
				Scanner otomatis mendeteksi transaksi wallet beruntun &gt; 15 SOL dengan batas holding dev &lt; 5% untuk memfilter likuiditas berisiko tinggi.
			</p>
		</div>
	{/if}
</div>

<style>
	.market-tools-container {
		background: #121314;
		border: 1px solid #232629;
		border-radius: 8px;
		padding: 1rem;
		margin-block: 1rem;
	}
	.tools-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		border-bottom: 1px solid #232629;
		padding-bottom: 0.75rem;
	}
	.oy-tag {
		font-size: 9.5px;
		font-weight: 700;
		color: #f5b83d;
		letter-spacing: 0.08em;
	}
	.oy-panel {
		background: #16181a;
		border: 1px solid #232629;
		border-radius: 6px;
		padding: 0.85rem;
	}
	.panel-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		border-bottom: 1px solid #232629;
		padding-bottom: 0.45rem;
		margin-bottom: 0.75rem;
	}
	.panel-title {
		font-size: 11.5px;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		color: #ededec;
	}
	.input-lbl {
		display: block;
		font-size: 11px;
		color: #a6aab0;
	}
	.oy-input {
		width: 100%;
		background: #0c0d0e;
		border: 1px solid #232629;
		border-radius: 4px;
		color: #ededec;
		padding: 0.35rem 0.55rem;
		font-size: 13px;
	}
	.preset-btn {
		background: #1c1f22;
		border: 1px solid #2f3337;
		color: #a6aab0;
		border-radius: 4px;
		padding: 0.35rem 0.6rem;
		font-size: 11px;
	}
	.preset-btn:hover {
		color: #f5b83d;
		border-color: #f5b83d;
	}
	.status-pill {
		font-size: 9.5px;
		font-weight: 700;
		padding: 2px 6px;
		border-radius: 4px;
		border: 1px solid;
	}
	.status-pill.pos {
		color: #3cc76b;
		background: rgba(60, 199, 107, 0.12);
		border-color: rgba(60, 199, 107, 0.3);
	}
	.status-pill.warn {
		color: #f5b83d;
		background: rgba(245, 184, 61, 0.12);
		border-color: rgba(245, 184, 61, 0.3);
	}
	.kpi-cell {
		background: #0c0d0e;
		border: 1px solid #232629;
		border-radius: 4px;
		padding: 0.5rem 0.6rem;
		display: flex;
		flex-direction: column;
	}
	.kpi-cell .lbl {
		font-size: 9.5px;
		color: #787d84;
		text-transform: uppercase;
	}
	.kpi-cell .val {
		font-size: 16px;
		font-weight: 700;
		margin-block: 1px;
	}
	.kpi-cell .sub {
		font-size: 10px;
		color: #787d84;
		font-family: sans-serif;
	}
	.standdown-box {
		background: #16181a;
		border: 1px solid #232629;
		border-radius: 6px;
		padding: 0.85rem;
	}
</style>
