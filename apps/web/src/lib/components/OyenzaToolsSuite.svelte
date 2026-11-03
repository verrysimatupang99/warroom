<script lang="ts">
	/**
	 * OyenzaToolsSuite.svelte
	 * Suite Tools Terpadu terinspirasi dari oyenza.trade/dashboard (Tools: Screener, Models, Compare, Calendar, Flow).
	 * Disesuaikan khusus untuk War Room (Trading Multi-Market & Prop-Firm Risk Guard Global4EX/GFT).
	 */
	import TrackBar from './TrackBar.svelte';
	import HonestyTag from './HonestyTag.svelte';

	// Tab aktif di dalam Tools Suite
	let activeTool = $state<'model' | 'compare' | 'flow' | 'screener' | 'standdown'>('model');

	// State untuk Tool: Risk & Lot Sizing Model (Global4EX $5K)
	let accountSize = $state(5000);
	let riskPercent = $state(1.4);
	let slPips = $state(70);
	let selectedAsset = $state<'XAUUSD' | 'BTCUSDT' | 'EURUSD'>('XAUUSD');

	// Kalkulasi Model Dinamis
	const maxDailyLoss = $derived(accountSize * 0.04); // 4% limit Global4EX ($200 pada $5K)
	const maxTotalLoss = $derived(accountSize * 0.08); // 8% limit Global4EX ($400 pada $5K)
	const dollarRisk = $derived((accountSize * (riskPercent / 100)));
	
	// Lot kalkulasi XAUUSD: 1 pip (0.10) = $1 per 0.10 lot (100 oz contract) -> $10 per $1 move
	const calculatedLot = $derived.by(() => {
		if (selectedAsset === 'XAUUSD') {
			// slPips = 70 pips = $7.00 price move. Risk $70 -> 0.10 lot
			const riskPerPoint = dollarRisk / (slPips / 10);
			return Math.max(0.01, Math.round((riskPerPoint / 100) * 100) / 100);
		} else if (selectedAsset === 'EURUSD') {
			// 1 pip = $10 per 1 standard lot
			return Math.max(0.01, Math.round((dollarRisk / (slPips * 10)) * 100) / 100);
		} else {
			// BTCUSDT
			return Math.max(0.001, Math.round((dollarRisk / (slPips * 10)) * 1000) / 1000);
		}
	});

	const riskSafetyStatus = $derived.by(() => {
		if (dollarRisk > maxDailyLoss * 0.75) return { status: 'BAHAYA', color: 'text-neg', bg: 'bg-neg/10 border-neg/30', msg: 'Mendekati 75% limit rugi harian!' };
		if (dollarRisk > maxDailyLoss * 0.50) return { status: 'WASPADA', color: 'text-warn', bg: 'bg-warn/10 border-warn/30', msg: 'Risiko moderat (50% daily buffer).' };
		return { status: 'AMAN', color: 'text-pos', bg: 'bg-pos/10 border-pos/30', msg: 'Toleransi risiko aman untuk 2-3 trade beruntun.' };
	});

	// Data Compare Matrix (Perbandingan edge antar instrumen)
	const compareMatrix = [
		{ asset: 'XAUUSD (Gold)', tf: '15m', pf: 2.08, wr: 61, winLoss: '17W / 11L', netR: '+10.2R', status: 'Unggul (Best Edge)' },
		{ asset: 'BTCUSDT (Bitcoin)', tf: '15m', pf: 1.83, wr: 65, winLoss: '13W / 7L', netR: '+8.4R', status: 'Stabil' },
		{ asset: 'SOLUSDT (Solana)', tf: '15m', pf: 1.70, wr: 58, winLoss: '11W / 8L', netR: '+5.6R', status: 'Volatil' },
		{ asset: 'EURUSD (Euro)', tf: '15m', pf: 1.58, wr: 54, winLoss: '15W / 13L', netR: '+4.2R', status: 'Konsisten' },
		{ asset: 'GBPUSD (Pound)', tf: '15m', pf: 1.30, wr: 50, winLoss: '10W / 10L', netR: '+1.8R', status: 'Moderat' },
	];

	// Data Screener multi-market
	const screenerSetups = [
		{ symbol: 'XAUUSD', name: 'Gold Spot', price: '2,725.50', change: '+0.84%', bias: 'BULLISH', setup: 'Break & Retest 15m', score: 94, action: 'READY BUY' },
		{ symbol: 'BTCUSDT', name: 'Bitcoin Perp', price: '67,450.00', change: '+2.15%', bias: 'BULLISH', setup: 'SMC POI Retest', score: 88, action: 'WATCH' },
		{ symbol: 'EURUSD', name: 'Euro / USD', price: '1.08250', change: '-0.32%', bias: 'BEARISH', setup: 'London Breakdown', score: 82, action: 'READY SELL' },
		{ symbol: 'SOLUSDT', name: 'Solana Perp', price: '168.20', change: '+4.10%', bias: 'BULLISH', setup: 'Momentum Continuation', score: 79, action: 'STANDBY' }
	];
</script>

<div class="oyenza-suite">
	<!-- Top Bar Tools Navigation ala Oyenza Dashboard -->
	<div class="suite-header">
		<div class="suite-title-area">
			<span class="oy-tag font-mono">TOOLS</span>
			<h2 class="suite-title">Market Intelligence &amp; Risk Suite</h2>
		</div>
		
		<div class="tools-nav font-mono">
			<button 
				type="button"
				class="tool-btn {activeTool === 'model' ? 'active' : ''}" 
				onclick={() => activeTool = 'model'}
			>
				<span>01</span> Risk &amp; Sizing Model
			</button>
			<button 
				type="button"
				class="tool-btn {activeTool === 'compare' ? 'active' : ''}" 
				onclick={() => activeTool = 'compare'}
			>
				<span>02</span> Asset Compare
			</button>
			<button 
				type="button"
				class="tool-btn {activeTool === 'screener' ? 'active' : ''}" 
				onclick={() => activeTool = 'screener'}
			>
				<span>03</span> Multi-Screener
			</button>
			<button 
				type="button"
				class="tool-btn {activeTool === 'flow' ? 'active' : ''}" 
				onclick={() => activeTool = 'flow'}
			>
				<span>04</span> Smart Flow
			</button>
			<button 
				type="button"
				class="tool-btn {activeTool === 'standdown' ? 'active' : ''}" 
				onclick={() => activeTool = 'standdown'}
			>
				<span>05</span> Stand-Down Guard
			</button>
		</div>
	</div>

	<!-- TAB CONTENT 1: RISK & SIZING MODEL -->
	{#if activeTool === 'model'}
		<div class="tool-content">
			<div class="model-grid">
				<!-- Input Panel -->
				<div class="panel-box">
					<div class="panel-head">
						<span class="panel-title">Parameter Akun &amp; Skenario Prop Firm</span>
						<HonestyTag terverifikasi={true} sumber="Global4EX 5K" />
					</div>

					<div class="space-y-4 text-13">
						<div>
							<label for="acc-size" class="input-label">Ukuran Modal Akun (USD):</label>
							<div class="flex items-center gap-2 mt-1">
								<input 
									id="acc-size" 
									type="number" 
									bind:value={accountSize} 
									class="oy-input font-mono" 
									step="500" 
								/>
								<div class="flex gap-1">
									<button type="button" class="chip-preset" onclick={() => accountSize = 5000}>$5K</button>
									<button type="button" class="chip-preset" onclick={() => accountSize = 10000}>$10K</button>
									<button type="button" class="chip-preset" onclick={() => accountSize = 25000}>$25K</button>
								</div>
							</div>
						</div>

						<div class="grid grid-cols-2 gap-3">
							<div>
								<label for="asset-sel" class="input-label">Pilih Aset:</label>
								<select id="asset-sel" bind:value={selectedAsset} class="oy-select font-mono mt-1">
									<option value="XAUUSD">XAUUSD (Gold)</option>
									<option value="BTCUSDT">BTCUSDT</option>
									<option value="EURUSD">EURUSD</option>
								</select>
							</div>

							<div>
								<label for="risk-pct" class="input-label">Toleransi Risiko (%):</label>
								<input 
									id="risk-pct" 
									type="number" 
									bind:value={riskPercent} 
									step="0.1" 
									min="0.2" 
									max="4.0" 
									class="oy-input font-mono mt-1" 
								/>
							</div>
						</div>

						<div>
							<div class="flex justify-between items-center">
								<label for="sl-range" class="input-label">Jarak Stop Loss ({selectedAsset === 'XAUUSD' ? 'Pips / $0.10' : 'Points'}):</label>
								<span class="font-mono text-12 font-bold text-accent">{slPips} pips</span>
							</div>
							<input 
								id="sl-range" 
								type="range" 
								bind:value={slPips} 
								min="20" 
								max="150" 
								step="5" 
								class="w-full mt-1 accent-accent" 
							/>
						</div>
					</div>
				</div>

				<!-- Output Simulation & Guard Panel -->
				<div class="panel-box bg-surface-2/60">
					<div class="panel-head">
						<span class="panel-title">Hasil Rekomendasi Eksekusi &amp; Safety Guard</span>
						<span class="status-pill {riskSafetyStatus.bg} {riskSafetyStatus.color} font-mono">
							{riskSafetyStatus.status}
						</span>
					</div>

					<div class="grid grid-cols-2 gap-3 font-mono my-2">
						<div class="kpi-card">
							<span class="kpi-label">Rekomendasi Lot:</span>
							<span class="kpi-val text-accent">{calculatedLot} Lot</span>
							<span class="kpi-sub">Sizing aman per trade</span>
						</div>

						<div class="kpi-card">
							<span class="kpi-label">Nilai Risiko ($):</span>
							<span class="kpi-val text-neg">${dollarRisk.toFixed(2)}</span>
							<span class="kpi-sub">{riskPercent}% dari saldo</span>
						</div>

						<div class="kpi-card">
							<span class="kpi-label">Batas Rugi Harian (4%):</span>
							<span class="kpi-val text-text">${maxDailyLoss.toFixed(2)}</span>
							<span class="kpi-sub">Global4EX Hard Breach</span>
						</div>

						<div class="kpi-card">
							<span class="kpi-label">Batas Rugi Total (8%):</span>
							<span class="kpi-val text-text">${maxTotalLoss.toFixed(2)}</span>
							<span class="kpi-sub">Static Max Drawdown</span>
						</div>
					</div>

					<div class="mt-3 p-2.5 rounded bg-surface border border-line text-12">
						<div class="font-bold {riskSafetyStatus.color} mb-1">{riskSafetyStatus.msg}</div>
						<p class="text-text-3 text-11 leading-relaxed">
							Dengan modal <b>${accountSize}</b> dan risiko <b>${dollarRisk.toFixed(0)}</b>, Anda memiliki napas hingga 
							<b>{Math.floor(maxDailyLoss / dollarRisk)} trade rugi berturut-turut</b> dalam 1 hari sebelum menyentuh batas daily drawdown.
						</p>
					</div>
				</div>
			</div>
		</div>
	{/if}

	<!-- TAB CONTENT 2: ASSET COMPARE (SELF-RANK) -->
	{#if activeTool === 'compare'}
		<div class="tool-content">
			<div class="overflow-x-auto">
				<table class="oy-table font-mono">
					<thead>
						<tr>
							<th>Instrumen</th>
							<th>Timeframe</th>
							<th>Profit Factor</th>
							<th>Win Rate</th>
							<th>W/L Ratio</th>
							<th>Net Return</th>
							<th>Status Edge</th>
						</tr>
					</thead>
					<tbody>
						{#each compareMatrix as row}
							<tr>
								<td class="font-bold text-text">{row.asset}</td>
								<td class="text-text-3">{row.tf}</td>
								<td class="font-bold text-accent">{row.pf.toFixed(2)}</td>
								<td>
									<div class="flex items-center gap-2">
										<span class="text-pos font-bold">{row.wr}%</span>
										<div class="w-16">
											<TrackBar label="WR" nilai={row.wr} maks={100} nada="terkukur" />
										</div>
									</div>
								</td>
								<td class="text-text-2">{row.winLoss}</td>
								<td class="font-bold text-pos">{row.netR}</td>
								<td>
									<span class="badge-tag">{row.status}</span>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</div>
	{/if}

	<!-- TAB CONTENT 3: MULTI-SCREENER -->
	{#if activeTool === 'screener'}
		<div class="tool-content">
			<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 font-mono">
				{#each screenerSetups as sc}
					<div class="sc-card">
						<div class="flex justify-between items-start border-b border-line-soft pb-2">
							<div>
								<span class="text-14 font-bold text-text block">{sc.symbol}</span>
								<span class="text-10 text-text-3 font-sans">{sc.name}</span>
							</div>
							<span class="text-12 font-bold {sc.change.startsWith('+') ? 'text-pos' : 'text-neg'}">{sc.change}</span>
						</div>

						<div class="my-2.5 space-y-1 text-11">
							<div class="flex justify-between">
								<span class="text-text-3">Harga Live:</span>
								<span class="font-bold text-text">{sc.price}</span>
							</div>
							<div class="flex justify-between">
								<span class="text-text-3">Bias / Flow:</span>
								<span class="font-bold {sc.bias === 'BULLISH' ? 'text-pos' : 'text-neg'}">{sc.bias}</span>
							</div>
							<div class="flex justify-between">
								<span class="text-text-3">Setup:</span>
								<span class="text-text-2 truncate max-w-[130px]">{sc.setup}</span>
							</div>
						</div>

						<div class="flex items-center justify-between pt-2 border-t border-line-soft">
							<span class="text-10 text-text-3">Skor: <b class="text-accent">{sc.score}</b></span>
							<span class="rounded px-2 py-0.5 text-10 font-bold {sc.action.includes('BUY') ? 'bg-pos/20 text-pos' : sc.action.includes('SELL') ? 'bg-neg/20 text-neg' : 'bg-surface text-text-3 border border-line'}">
								{sc.action}
							</span>
						</div>
					</div>
				{/each}
			</div>
		</div>
	{/if}

	<!-- TAB CONTENT 4: SMART FLOW -->
	{#if activeTool === 'flow'}
		<div class="tool-content">
			<div class="grid grid-cols-1 md:grid-cols-3 gap-3 font-mono text-12">
				<div class="panel-box">
					<div class="font-bold text-text border-b border-line pb-1.5 mb-2">Foreign Flow (IDX)</div>
					<div class="text-20 font-bold text-pos mb-1">+Rp 248.5 M</div>
					<p class="text-11 text-text-3 font-sans">Akumulasi bersih modal asing pada saham perbankan dan telco di sesi reguler terakhir.</p>
				</div>
				<div class="panel-box">
					<div class="font-bold text-text border-b border-line pb-1.5 mb-2">Taker Buy/Sell (Crypto)</div>
					<div class="text-20 font-bold text-accent mb-1">1.24 Ratio</div>
					<p class="text-11 text-text-3 font-sans">Volume agresif taker buyer mendominasi pasar perp BTC &amp; SOL dalam 4 jam terakhir.</p>
				</div>
				<div class="panel-box">
					<div class="font-bold text-text border-b border-line pb-1.5 mb-2">Gold Institutional Bias</div>
					<div class="text-20 font-bold text-pos mb-1">68% Bullish</div>
					<p class="text-11 text-text-3 font-sans">Sentimen sesi London-NY mengarah ke kelanjutan reli emas di atas level support $2,720.</p>
				</div>
			</div>
		</div>
	{/if}

	<!-- TAB CONTENT 5: STAND-DOWN GUARD (CALENDAR) -->
	{#if activeTool === 'standdown'}
		<div class="tool-content">
			<div class="space-y-3 font-mono">
				<div class="p-3 bg-surface border border-line rounded flex items-center justify-between">
					<div>
						<span class="text-12 font-bold text-pos flex items-center gap-2">
							<span class="inline-block w-2.5 h-2.5 rounded-full bg-pos animate-pulse"></span>
							ZONE AMAN: TIDAK ADA HIGH-IMPACT NEWS DALAM 60 MENIT
						</span>
						<p class="text-11 text-text-3 font-sans mt-0.5">Sistem mengizinkan eksekusi order normal untuk XAUUSD &amp; Crypto.</p>
					</div>
					<span class="status-pill bg-pos/10 text-pos border-pos/30 text-11">TRADE ALLOWED</span>
				</div>

				<div class="grid grid-cols-1 md:grid-cols-3 gap-3 text-12">
					<div class="sc-card">
						<div class="flex justify-between items-center text-11 text-text-3 border-b border-line-soft pb-1.5 mb-2">
							<span>US CPI Inflation</span>
							<span class="text-neg font-bold">HIGH IMPACT</span>
						</div>
						<div class="text-16 font-bold text-text mb-1">Kamis, 19:30 WIB</div>
						<p class="text-11 text-text-3 font-sans">Stand-Down otomatis aktif 15m sebelum &amp; 15m sesudah rilis. Sizing ditahan ke 0 lot.</p>
					</div>

					<div class="sc-card">
						<div class="flex justify-between items-center text-11 text-text-3 border-b border-line-soft pb-1.5 mb-2">
							<span>Fed FOMC Rate Decision</span>
							<span class="text-neg font-bold">MAX RISK</span>
						</div>
						<div class="text-16 font-bold text-text mb-1">Kamis (Malam), 01:00 WIB</div>
						<p class="text-11 text-text-3 font-sans">Larangan trading ketat di prop-firm Global4EX / GFT saat pengumuman suku bunga.</p>
					</div>

					<div class="sc-card">
						<div class="flex justify-between items-center text-11 text-text-3 border-b border-line-soft pb-1.5 mb-2">
							<span>US Non-Farm Payrolls (NFP)</span>
							<span class="text-neg font-bold">HIGH IMPACT</span>
						</div>
						<div class="text-16 font-bold text-text mb-1">Jumat pertama, 19:30 WIB</div>
						<p class="text-11 text-text-3 font-sans">Slippage tinggi &amp; spread melebar drastis pada XAU/USD dan EUR/USD.</p>
					</div>
				</div>
			</div>
		</div>
	{/if}
</div>

<style>
	.oyenza-suite {
		background: var(--color-surface);
		border: 1px solid var(--color-line);
		border-radius: var(--radius-card);
		padding: 1.15rem;
		margin-top: 1.25rem;
		margin-bottom: 1.5rem;
	}
	@media (max-width: 640px) {
		.oyenza-suite {
			padding: 0.75rem 0.65rem;
			margin-top: 0.85rem;
			margin-bottom: 1rem;
		}
		.suite-title {
			font-size: var(--text-14);
		}
		.tools-nav {
			display: grid;
			grid-template-columns: repeat(2, 1fr);
			gap: 0.35rem;
			width: 100%;
		}
		.tools-nav .tool-btn:last-child {
			grid-column: span 2;
		}
		.tool-btn {
			justify-content: center;
			padding: 0.45rem 0.5rem;
			font-size: 11px;
		}
	}
	.suite-header {
		display: flex;
		flex-direction: column;
		gap: 0.85rem;
		border-bottom: 1px solid var(--color-line);
		padding-bottom: 0.85rem;
		margin-bottom: 1rem;
	}
	@media (min-width: 768px) {
		.suite-header {
			flex-direction: row;
			align-items: center;
			justify-content: space-between;
		}
	}
	.oy-tag {
		font-size: 10px;
		font-weight: 700;
		letter-spacing: 0.08em;
		color: var(--color-accent);
		background: color-mix(in srgb, var(--color-accent) 12%, transparent);
		border: 1px solid color-mix(in srgb, var(--color-accent) 25%, transparent);
		border-radius: 4px;
		padding: 1px 6px;
		display: inline-block;
		margin-bottom: 0.25rem;
	}
	.suite-title {
		font-size: var(--text-16);
		font-weight: 700;
		color: var(--color-text);
		margin: 0;
	}
	.tools-nav {
		display: flex;
		flex-wrap: wrap;
		gap: 0.35rem;
	}
	.tool-btn {
		font-size: var(--text-11);
		font-weight: 500;
		padding: 0.4rem 0.75rem;
		border-radius: 6px;
		background: var(--color-surface-2);
		color: var(--color-text-3);
		border: 1px solid var(--color-line-soft);
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		transition: all 150ms ease-out;
	}
	.tool-btn span {
		/* Dulu 0.6. Dengan latar gelap kartu itu kontrasnya di bawah ambang
		   WCAG AA 4.5:1 untuk teks kecil, sehingga angka 02–05 nyaris tak terbaca.
		   0.75 memberi kontras cukup dan tetap terlihat sebagai angka sekunder. */
		opacity: 0.75;
		font-size: 10px;
	}
	.tool-btn:hover {
		color: var(--color-text);
		border-color: var(--color-text-3);
	}
	.tool-btn.active {
		background: var(--color-accent);
		color: var(--color-on-accent);
		border-color: var(--color-accent);
		font-weight: 600;
	}
	.tool-btn.active span {
		color: var(--color-on-accent);
		opacity: 0.8;
	}
	.model-grid {
		display: grid;
		grid-template-columns: 1fr;
		gap: 1rem;
	}
	@media (min-width: 768px) {
		.model-grid {
			grid-template-columns: 1fr 1fr;
		}
	}
	.panel-box {
		background: var(--color-surface);
		border: 1px solid var(--color-line);
		border-radius: var(--radius-card);
		padding: 0.95rem;
	}
	.panel-head {
		display: flex;
		justify-content: space-between;
		align-items: center;
		border-bottom: 1px solid var(--color-line-soft);
		padding-bottom: 0.5rem;
		margin-bottom: 0.85rem;
	}
	.panel-title {
		font-size: var(--text-12);
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		color: var(--color-text-2);
	}
	.input-label {
		display: block;
		font-size: var(--text-11);
		font-weight: 500;
		color: var(--color-text-3);
	}
	.oy-input, .oy-select {
		width: 100%;
		background: var(--color-canvas);
		border: 1px solid var(--color-line);
		border-radius: 4px;
		color: var(--color-text);
		padding: 0.4rem 0.6rem;
		font-size: var(--text-13);
	}
	.chip-preset {
		padding: 0.35rem 0.6rem;
		font-size: 11px;
		font-family: monospace;
		background: var(--color-surface-2);
		color: var(--color-text-2);
		border: 1px solid var(--color-line);
		border-radius: 4px;
	}
	.chip-preset:hover {
		color: var(--color-accent);
		border-color: var(--color-accent);
	}
	.kpi-card {
		background: var(--color-canvas);
		border: 1px solid var(--color-line);
		border-radius: 4px;
		padding: 0.6rem;
		display: flex;
		flex-direction: column;
	}
	.kpi-label {
		font-size: 10px;
		text-transform: uppercase;
		color: var(--color-text-3);
	}
	.kpi-val {
		font-size: 18px;
		font-weight: 700;
		margin-block: 2px;
		font-variant-numeric: tabular-nums;
	}
	.kpi-sub {
		font-size: 10px;
		color: var(--color-text-3);
		font-family: sans-serif;
	}
	.status-pill {
		font-size: 10px;
		font-weight: 700;
		padding: 2px 6px;
		border-radius: 4px;
		border-width: 1px;
	}
	.oy-table {
		width: 100%;
		border-collapse: collapse;
		font-size: 12px;
		font-variant-numeric: tabular-nums;
	}
	.oy-table th {
		text-align: left;
		padding: 0.55rem 0.75rem;
		border-bottom: 1px solid var(--color-line);
		color: var(--color-text-3);
		font-size: 11px;
		font-weight: 500;
		text-transform: uppercase;
	}
	.oy-table td {
		padding: 0.65rem 0.75rem;
		border-bottom: 1px solid var(--color-line-soft);
	}
	.oy-table tr:hover {
		background: var(--color-surface-2);
	}
	.badge-tag {
		font-size: 10px;
		font-weight: 600;
		padding: 2px 6px;
		border-radius: 4px;
		background: var(--color-surface-2);
		color: var(--color-accent);
		border: 1px solid color-mix(in srgb, var(--color-accent) 25%, transparent);
	}
	.sc-card {
		background: var(--color-canvas);
		border: 1px solid var(--color-line);
		border-radius: var(--radius-card);
		padding: 0.75rem;
	}
</style>
