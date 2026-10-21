<script lang="ts">
	// Komponen visual Quant Strategy & Backtest Break-Retest Multi-Asset (Gold, Crypto, Forex)
	// Ditampilkan di seluruh halaman War Room (https://0xgunsl1ng3r.xyz)
	import Istilah from './Istilah.svelte';
	import HonestyTag from './HonestyTag.svelte';

	interface Props {
		filter?: string; // 'all' | 'crypto' | 'forex' | 'idx' | 'gmgn'
	}

	let { filter = 'all' }: Props = $props();

	interface AssetPerformance {
		symbol: string;
		name: string;
		category: string;
		market: string;
		win_rate: number;
		pf: number;
		pnl: number;
		max_dd: number;
		trades: number;
		config: string;
	}

	const rawAssets: AssetPerformance[] = [
		{
			symbol: 'XAUUSD',
			name: 'Gold (Emas)',
			category: 'Metal / Komoditas',
			market: 'forex',
			win_rate: 32.5,
			pf: 1.30,
			pnl: 2.34,
			max_dd: 2.38,
			trades: 40,
			config: 'LB 35 bar · SL 1.6x ATR · RRR 1:3.0 · Rejection Filter'
		},
		{
			symbol: 'BTCUSDT',
			name: 'Bitcoin',
			category: 'Crypto Pair',
			market: 'crypto',
			win_rate: 39.4,
			pf: 1.74,
			pnl: 3.49,
			max_dd: 1.74,
			trades: 33,
			config: 'LB 20 bar · SL 1.2x ATR · RRR 1:2.0 · Rejection Filter'
		},
		{
			symbol: 'SOLUSDT',
			name: 'Solana',
			category: 'Crypto Pair',
			market: 'crypto',
			win_rate: 30.0,
			pf: 1.80,
			pnl: 7.74,
			max_dd: 4.23,
			trades: 20,
			config: 'LB 15 bar · SL 1.8x ATR · RRR 1:3.0 · Expansion Focus'
		},
		{
			symbol: 'EURUSD',
			name: 'Euro / US Dollar',
			category: 'Forex Major',
			market: 'forex',
			win_rate: 41.0,
			pf: 1.67,
			pnl: 1.45,
			max_dd: 0.38,
			trades: 39,
			config: 'LB 30 bar · SL 2.0x ATR · RRR 1:3.0 · Rejection Filter'
		},
		{
			symbol: 'GBPUSD',
			name: 'British Pound / USD',
			category: 'Forex Major',
			market: 'forex',
			win_rate: 42.4,
			pf: 2.10,
			pnl: 2.04,
			max_dd: 0.58,
			trades: 33,
			config: 'LB 15 bar · SL 2.0x ATR · RRR 1:3.0 · Trend Follow'
		}
	];

	const assets = $derived.by(() => {
		if (filter === 'all') return rawAssets;
		return rawAssets.filter((a) => a.market === filter);
	});
</script>

<div class="quant-card">
	<div class="quant-header">
		<div class="head-left">
			<span class="badge-quant">QUANT ENGINE · MULTI-ASSET</span>
			<h2 class="title">
				{#if filter === 'forex'}
					Struktur &amp; Validasi Kuantitatif Emas (XAUUSD) &amp; Valas
				{:else if filter === 'crypto'}
					Struktur &amp; Validasi Kuantitatif Crypto (BTC &amp; SOL)
				{:else}
					Break &amp; Retest 15m (Multi-Asset Optimization)
				{/if}
			</h2>
			<p class="subtitle">
				Hasil validasi backtest deterministik (Anti-Lookahead) terhadap data historis 1.000–2.000+ bar.
			</p>
		</div>
		<div class="head-right">
			<span class="status-pill pos">100% ASSET PROFITABLE</span>
		</div>
	</div>

	<!-- Bento Highlights: Gold & Top Crypto -->
	<div class="bento-grid">
		{#if filter === 'forex' || filter === 'all'}
			<div class="bento-item gold-box">
				<div class="item-head">
					<span class="symbol">🥇 XAUUSD (Gold)</span>
					<span class="subtext">Metal / Komoditas</span>
				</div>
				<div class="stats-row">
					<div class="metric">
						<span class="lbl">Profit Factor</span>
						<span class="val pos">1.30</span>
					</div>
					<div class="metric">
						<span class="lbl">Win Rate</span>
						<span class="val">32.5% <small class="dim">(BE: 25%)</small></span>
					</div>
					<div class="metric">
						<span class="lbl">Net PnL</span>
						<span class="val pos">+2.34%</span>
					</div>
					<div class="metric">
						<span class="lbl">Max DD</span>
						<span class="val">2.38%</span>
					</div>
				</div>
				<p class="formula-desc">
					<strong>Formula:</strong> Lookback 35 bars · Stop Loss 1.6x ATR · RRR 1:3.0 · Retest Rejection Validated
				</p>
			</div>
		{/if}

		{#if filter === 'crypto' || filter === 'all'}
			<div class="bento-item sol-box">
				<div class="item-head">
					<span class="symbol">⚡ SOLUSDT &amp; BTC</span>
					<span class="subtext">Crypto Momentum</span>
				</div>
				<div class="stats-row">
					<div class="metric">
						<span class="lbl">SOL Top PnL</span>
						<span class="val pos">+7.74%</span>
					</div>
					<div class="metric">
						<span class="lbl">SOL PF</span>
						<span class="val pos">1.80</span>
					</div>
					<div class="metric">
						<span class="lbl">BTC Win Rate</span>
						<span class="val">39.4%</span>
					</div>
					<div class="metric">
						<span class="lbl">BTC PF</span>
						<span class="val pos">1.74</span>
					</div>
				</div>
				<p class="formula-desc">
					<strong>Formula SOL:</strong> LB 15 bar, SL 1.8x ATR, RRR 1:3.0 | <strong>BTC:</strong> LB 20 bar, SL 1.2x ATR
				</p>
			</div>
		{/if}
	</div>

	<!-- Papan Klasemen Tabel Multi-Asset -->
	{#if assets.length > 0}
		<div class="table-container">
			<div class="table-label">
				<span>Papan Klasemen Performa Aset</span>
				<span class="dim">Total {assets.reduce((sum, a) => sum + a.trades, 0)} Trade Tuntas</span>
			</div>
			<div class="table-scroll">
				<table class="quant-table">
					<thead>
						<tr>
							<th>Instrumen</th>
							<th>Kategori</th>
							<th class="ka">Trades</th>
							<th class="ka">Win Rate</th>
							<th class="ka">Profit Factor</th>
							<th class="ka">Net PnL</th>
							<th class="ka">Max DD</th>
							<th>Formula Tuning</th>
						</tr>
					</thead>
					<tbody>
						{#each assets as a}
							<tr>
								<td class="bold">
									{a.symbol} <small class="dim">({a.name})</small>
								</td>
								<td><span class="cat-pill">{a.category}</span></td>
								<td class="ka angka">{a.trades}</td>
								<td class="ka angka">{a.win_rate.toFixed(1)}%</td>
								<td class="ka angka bold pos">{a.pf.toFixed(2)}</td>
								<td class="ka angka bold pos">+{a.pnl.toFixed(2)}%</td>
								<td class="ka angka dim">{a.max_dd.toFixed(2)}%</td>
								<td class="dim code">{a.config}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</div>
	{/if}
</div>

<style>
	.quant-card {
		background: var(--permukaan, #121417);
		border: 1px solid var(--garis, rgba(255, 255, 255, 0.08));
		border-radius: var(--radius-card, 8px);
		padding: 1.25rem;
		margin-bottom: 1.5rem;
	}
	.quant-header {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: 1rem;
		margin-bottom: 1.25rem;
		border-bottom: 1px solid var(--garis, rgba(255, 255, 255, 0.08));
		padding-bottom: 0.85rem;
	}
	.badge-quant {
		display: inline-block;
		font-size: 0.62rem;
		font-weight: 700;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--mint, #34e39a);
		margin-bottom: 0.25rem;
	}
	.title {
		font-size: 1.15rem;
		font-weight: 700;
		color: var(--tinta, #f3f4f6);
		margin: 0 0 0.25rem;
	}
	.subtitle {
		font-size: 0.8rem;
		color: var(--redup, #9ca3af);
		margin: 0;
	}
	.status-pill {
		font-size: 0.72rem;
		font-weight: 700;
		padding: 0.25rem 0.6rem;
		border-radius: 4px;
		background: color-mix(in srgb, var(--mint, #34e39a) 15%, transparent);
		color: var(--mint, #34e39a);
		border: 1px solid color-mix(in srgb, var(--mint, #34e39a) 40%, transparent);
	}
	.bento-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(18rem, 1fr));
		gap: 1rem;
		margin-bottom: 1.25rem;
	}
	.bento-item {
		background: color-mix(in srgb, var(--latar, #0a0b0d) 65%, var(--permukaan, #121417));
		border: 1px solid var(--garis, rgba(255, 255, 255, 0.08));
		border-radius: 6px;
		padding: 1rem;
	}
	.gold-box {
		border-left: 3px solid #eab308;
	}
	.sol-box {
		border-left: 3px solid var(--mint, #34e39a);
	}
	.item-head {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		margin-bottom: 0.75rem;
	}
	.symbol {
		font-size: 0.95rem;
		font-weight: 700;
		color: var(--tinta, #f3f4f6);
	}
	.subtext {
		font-size: 0.72rem;
		color: var(--redup, #9ca3af);
	}
	.stats-row {
		display: grid;
		grid-template-columns: repeat(4, 1fr);
		gap: 0.5rem;
		margin-bottom: 0.75rem;
	}
	.metric {
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
	}
	.lbl {
		font-size: 0.62rem;
		text-transform: uppercase;
		color: var(--redup, #9ca3af);
	}
	.val {
		font-size: 1.05rem;
		font-weight: 700;
		color: var(--tinta, #f3f4f6);
	}
	.formula-desc {
		font-size: 0.72rem;
		color: var(--redup, #9ca3af);
		margin: 0;
		line-height: 1.4;
	}
	.table-container {
		background: color-mix(in srgb, var(--latar, #0a0b0d) 50%, var(--permukaan, #121417));
		border: 1px solid var(--garis, rgba(255, 255, 255, 0.08));
		border-radius: 6px;
		padding: 0.85rem;
	}
	.table-label {
		display: flex;
		justify-content: space-between;
		font-size: 0.75rem;
		font-weight: 600;
		color: var(--tinta, #f3f4f6);
		margin-bottom: 0.65rem;
	}
	.table-scroll {
		overflow-x: auto;
	}
	.quant-table {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.78rem;
	}
	.quant-table th {
		text-align: left;
		font-size: 0.68rem;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--redup, #9ca3af);
		padding: 0.5rem;
		border-bottom: 1px solid var(--garis, rgba(255, 255, 255, 0.08));
	}
	.quant-table td {
		padding: 0.55rem 0.5rem;
		border-bottom: 1px solid rgba(255, 255, 255, 0.04);
	}
	.cat-pill {
		font-size: 0.68rem;
		padding: 0.15rem 0.4rem;
		background: rgba(255, 255, 255, 0.05);
		border-radius: 3px;
		color: var(--tinta, #f3f4f6);
	}
	.ka { text-align: right; }
	.bold { font-weight: 700; }
	.pos { color: var(--mint, #34e39a); }
	.dim { color: var(--redup, #9ca3af); }
	.code { font-family: monospace; font-size: 0.72rem; }
	.angka { font-family: monospace; }
</style>
