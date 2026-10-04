<script lang="ts">
	// StrategyLeaderboard: Papan Peringkat Strategi Kuantitatif (Inspirasi Fomo Family).
	// Mengurutkan dan membandingkan performa seluruh mesin sinyal & eksekusi War Room
	// berdasarkan risk-adjusted return, winrate, sampel (N), dan status operasional.
	import { angka } from '$lib/format';

	export interface StrategyItem {
		rank: number;
		id: string;
		nama: string;
		venue: string;
		tipe: 'PAPER' | 'LIVE' | 'SIGNAL-ONLY' | 'RESEARCH';
		winrate_pct: number | null;
		total_r: number | null;
		expectancy_r: number | null;
		n_samples: number;
		max_dd_r: number | null;
		status: 'UNGGUL' | 'PENGUJIAN' | 'FLAG_EXIT' | 'MONITOR';
		status_detail: string;
		friksi_est_pct: number;
	}

	interface Props {
		strategies?: StrategyItem[];
	}

	const DEFAULT_STRATEGIES: StrategyItem[] = [
		{
			rank: 1,
			id: 'crypto-smc',
			nama: 'Crypto SMC Multi-Timeframe (1H/4H POI)',
			venue: 'MEXC / Binance Futures',
			tipe: 'PAPER',
			winrate_pct: 80.0,
			total_r: 3.844,
			expectancy_r: 0.769,
			n_samples: 5,
			max_dd_r: 0.0,
			status: 'UNGGUL',
			status_detail: '4 Menang, 0 Kalah, 1 Expired. Edge konsisten di retest order block.',
			friksi_est_pct: 0.02
		},
		{
			rank: 2,
			id: 'pm-arm-b',
			nama: 'Polymarket Down-only Cheap (Arm B)',
			venue: 'Polymarket CLOB 5m',
			tipe: 'PAPER',
			winrate_pct: 78.2,
			total_r: null,
			expectancy_r: 0.015,
			n_samples: 4133,
			max_dd_r: 1.2,
			status: 'PENGUJIAN',
			status_detail: 'Sampel besar (N=4.133), ci_low mendekati BE (0.7666). Menunggu izin gate.',
			friksi_est_pct: 0.0
		},
		{
			rank: 3,
			id: 'idx-arjum',
			nama: 'IDX Arjum Multi-Factor Screener',
			venue: 'Bursa Efek Indonesia (IDX)',
			tipe: 'SIGNAL-ONLY',
			winrate_pct: null,
			total_r: null,
			expectancy_r: null,
			n_samples: 24,
			max_dd_r: null,
			status: 'MONITOR',
			status_detail: 'Top pick: SAPX (Score 3.0), WOOD (Score 2.0). Hanya sinyal, tanpa auto-trade.',
			friksi_est_pct: 0.35
		},
		{
			rank: 4,
			id: 'forex-gold',
			nama: 'Forex Spot Gold (XAUUSD Momentum)',
			venue: 'TradingView / OANDA Demo',
			tipe: 'RESEARCH',
			winrate_pct: null,
			total_r: null,
			expectancy_r: null,
			n_samples: 12,
			max_dd_r: null,
			status: 'MONITOR',
			status_detail: 'Spot Gold bearish < EMA20 ($3.883,9). Sesi Asia/London/NY tracking.',
			friksi_est_pct: 0.04
		},
		{
			rank: 5,
			id: 'gmgn-lp',
			nama: 'GMGN Multi-Chain LP Arbitrage',
			venue: 'Solana / Base DEX',
			tipe: 'PAPER',
			winrate_pct: 33.3,
			total_r: -0.42,
			expectancy_r: -0.14,
			n_samples: 3,
			max_dd_r: 2.1,
			status: 'FLAG_EXIT',
			status_detail: 'Posisi UBI terpicu rule KELUAR: IL -9.01% melebihi ambang batas risiko.',
			friksi_est_pct: 1.2
		}
	];

	let { strategies = DEFAULT_STRATEGIES }: Props = $props();
</script>

<div class="permukaan-2 rounded-card border border-line p-3" data-testid="strategy-leaderboard">
	<div class="mb-3 flex flex-wrap items-center justify-between gap-2 border-b border-line-soft pb-2">
		<div>
			<div class="flex items-center gap-2">
				<h3 class="text-14 font-bold text-text">Papan Peringkat Strategi</h3>
				<span class="rounded bg-accent/10 px-2 py-0.5 text-10 font-bold uppercase text-accent border border-accent/20">
					Leaderboard
				</span>
			</div>
			<p class="text-11 text-text-3 mt-0.5">
				Peringkat performa strategi kuantitatif lintas instrumen berbasis risk-adjusted return
			</p>
		</div>
		<span class="text-11 font-mono text-text-3">
			{strategies.length} strategi aktif
		</span>
	</div>

	<!-- List / Table Leaderboard dengan Scroll Responsif -->
	<div class="overflow-x-auto -mx-3 px-3">
		<div class="space-y-2 min-w-[500px]">
			{#each strategies as s (s.id)}
				<div class="flex items-center justify-between gap-3 rounded-card border border-line-soft bg-surface p-2.5 transition-colors hover:border-line">
					<!-- Rank & Info -->
					<div class="flex items-center gap-3 min-w-[200px]">
						<div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full font-mono text-12 font-bold {s.rank === 1 ? 'bg-amber-500/20 text-amber-400 border border-amber-500/40' : s.rank === 2 ? 'bg-slate-400/20 text-slate-300 border border-slate-400/40' : s.rank === 3 ? 'bg-amber-700/20 text-amber-600 border border-amber-700/40' : 'bg-surface text-text-3 border border-line'}">
							#{s.rank}
						</div>
						<div>
							<div class="flex items-center gap-1.5">
								<span class="font-bold text-12 text-text">{s.nama}</span>
								<span class="rounded px-1.5 py-0.2 text-9 font-mono font-bold {s.tipe === 'LIVE' ? 'bg-pos/20 text-pos' : s.tipe === 'PAPER' ? 'bg-accent/15 text-accent' : 'bg-surface text-text-3 border border-line'}">
									{s.tipe}
								</span>
							</div>
							<div class="flex items-center gap-2 text-10 text-text-3 mt-0.5 font-mono">
								<span>{s.venue}</span>
								<span>·</span>
								<span>Friksi: ~{s.friksi_est_pct}%</span>
							</div>
						</div>
					</div>

					<!-- Metrics -->
					<div class="flex items-center gap-4 text-right">
						<div>
							<span class="text-10 text-text-3 uppercase block">Win Rate</span>
							<span class="angka text-12 font-bold {s.winrate_pct != null && s.winrate_pct >= 50 ? 'text-pos' : s.winrate_pct != null ? 'text-warn' : 'text-text-3'}">
								{s.winrate_pct != null ? `${s.winrate_pct.toFixed(1)}%` : '—'}
							</span>
						</div>

						<div>
							<span class="text-10 text-text-3 uppercase block">Return / R</span>
							<span class="angka text-12 font-bold {s.total_r != null && s.total_r >= 0 ? 'text-pos' : s.total_r != null ? 'text-neg' : 'text-text-3'}">
								{s.total_r != null ? `${s.total_r >= 0 ? '+' : ''}${angka(s.total_r)}R` : '—'}
							</span>
						</div>

						<div>
							<span class="text-10 text-text-3 uppercase block">Sampel</span>
							<span class="text-11 font-mono text-text-2">
								{s.n_samples} n
							</span>
						</div>

						<!-- Status Badge -->
						<div class="w-24 text-right">
							<span class="inline-block rounded px-2 py-0.5 text-10 font-bold {s.status === 'UNGGUL' ? 'bg-pos/15 text-pos border border-pos/30' : s.status === 'FLAG_EXIT' ? 'bg-neg/15 text-neg border border-neg/30' : s.status === 'PENGUJIAN' ? 'bg-warn/15 text-warn border border-warn/30' : 'bg-surface text-text-3 border border-line'}">
								{s.status}
							</span>
						</div>
					</div>
				</div>
			{/each}
		</div>
	</div>
</div>
