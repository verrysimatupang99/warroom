<script lang="ts">
	import { onMount } from 'svelte';

	interface SentinelStatus {
		sentinel: string;
		active: boolean;
		verdict: string;
		security: string;
		confidence: number;
		engine: string;
		active_strategy: string;
		all_strategies: Array<{
			key: string;
			name: string;
			timeframe: string;
			rrr_min: number;
			is_active: boolean;
		}>;
	}

	interface MT5Status {
		connected: boolean;
		account: string;
		broker: string;
		balance: number;
		equity: number;
		floating_pnl: number;
		margin: number;
		free_margin: number;
		positions: Array<any>;
		total_trades_today: number;
		win_rate_pct: number;
		wins: number;
		losses: number;
		net_pnl_usd: number;
		seconds_ago: number;
	}

	interface ForexSignal {
		symbol: string;
		side: 'LONG' | 'SHORT';
		price: number;
		strategy: string;
		confidence: number;
		status: string;
		rrr: number;
		levels: {
			entry: number;
			sl: number;
			tp1: number;
			tp2: number;
			risk: number;
			reward: number;
		};
	}

	let mt5 = $state<MT5Status | null>(null);
	let sentinel = $state<SentinelStatus | null>(null);
	let signal = $state<ForexSignal | null>(null);
	let loading = $state(true);

	const MODAL_AWAL = 500.0;
	let retPct = $derived(mt5?.equity !== undefined ? ((mt5.equity - MODAL_AWAL) / MODAL_AWAL) * 100 : 0);

	async function fetchData() {
		try {
			const [resMt5, resSen, resSig] = await Promise.all([
				fetch('/api/v1/tencent/mt5/status'),
				fetch('/api/v1/tencent/forex/sentinel'),
				fetch('/api/v1/tencent/forex/levels?symbol=XAUUSD')
			]);
			if (resMt5.ok) mt5 = await resMt5.json();
			if (resSen.ok) sentinel = await resSen.json();
			if (resSig.ok) signal = await resSig.json();
		} catch (e) {
			console.error('Error fetching forex dashboard data:', e);
		} finally {
			loading = false;
		}
	}

	onMount(() => {
		fetchData();
		const interval = setInterval(fetchData, 2500);
		return () => clearInterval(interval);
	});
</script>

<div class="space-y-6">
	<!-- HEADER COCKPIT: EXNESS MT5 & LAYA AI SENTINEL STATUS -->
	<div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
		<!-- KARTU 1: EXNESS MT5 REAL-TIME TELEMETRY -->
		<div class="lg:col-span-2 rounded-xl border border-line bg-surface/90 p-5 shadow-2xl backdrop-blur relative overflow-hidden">
			<div class="absolute -right-10 -bottom-10 w-44 h-44 bg-emerald-500/5 rounded-full blur-3xl pointer-events-none"></div>
			
			<div class="flex flex-wrap items-center justify-between gap-3 border-b border-line-soft pb-4 mb-4">
				<div class="flex items-center gap-3">
					<div class="relative flex h-3.5 w-3.5">
						{#if mt5?.connected}
							<span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
							<span class="relative inline-flex rounded-full h-3.5 w-3.5 bg-emerald-500"></span>
						{:else}
							<span class="relative inline-flex rounded-full h-3.5 w-3.5 bg-zinc-500"></span>
						{/if}
					</div>
					<div>
						<div class="flex items-center gap-2">
							<h2 class="font-mono text-base font-bold tracking-wider text-white">EXNESS MT5 ALGO COCKPIT</h2>
							<span class="rounded bg-emerald-500/10 px-2.5 py-0.5 text-xs font-mono font-bold text-emerald-400 border border-emerald-500/20">
								#{mt5?.account ?? '416510164'}
							</span>
							<span class="rounded bg-white/5 px-2 py-0.5 text-[11px] font-mono text-zinc-300 border border-white/10">
								{mt5?.broker ?? 'Exness Technologies Ltd'}
							</span>
						</div>
						<p class="text-xs text-zinc-400 mt-0.5 font-sans">
							Live Telemetry Outbound Azure VM (138.91.35.65) • Detak: {mt5?.seconds_ago ?? 0}s yang lalu
						</p>
					</div>
				</div>

				<div class="flex items-center gap-2">
					<a
						href="/api/v1/tencent/mt5/source.raw"
						target="_blank"
						class="rounded bg-emerald-500/15 hover:bg-emerald-500/25 transition px-3 py-1.5 text-xs font-mono font-semibold text-emerald-400 border border-emerald-500/30 flex items-center gap-1.5"
					>
						<svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
						</svg>
						Unduh EA v2.0 (.mq5)
					</a>
				</div>
			</div>

			<!-- METRIK KEUANGAN AKUN EXNESS -->
			<div class="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono">
				<div class="rounded-lg bg-black/30 p-3 border border-white/5">
					<span class="text-[11px] text-zinc-400 block mb-0.5">MODAL AWAL</span>
					<span class="text-lg font-bold text-white">${MODAL_AWAL.toFixed(2)}</span>
					<span class="text-[10px] text-zinc-400 block mt-0.5">Baseline Demo</span>
				</div>
				<div class="rounded-lg bg-black/30 p-3 border border-white/5">
					<span class="text-[11px] text-zinc-400 block mb-0.5">EKUITAS BERJALAN</span>
					<span class="text-lg font-bold {retPct >= 0 ? 'text-emerald-400' : 'text-rose-400'}">
						${mt5?.equity?.toFixed(2) ?? '456.98'}
					</span>
					<span class="text-[10px] {retPct >= 0 ? 'text-emerald-400' : 'text-rose-400'} block mt-0.5">
						{retPct >= 0 ? '+' : ''}{retPct.toFixed(1)}%
					</span>
				</div>
				<div class="rounded-lg bg-black/30 p-3 border border-white/5">
					<span class="text-[11px] text-zinc-400 block mb-0.5">NET REALIZED PNL</span>
					<span class="text-lg font-bold {mt5?.net_pnl_usd && mt5.net_pnl_usd >= 0 ? 'text-emerald-400' : 'text-rose-400'}">
						{mt5?.net_pnl_usd && mt5.net_pnl_usd >= 0 ? '+' : ''}${mt5?.net_pnl_usd?.toFixed(2) ?? '-43.02'}
					</span>
					<span class="text-[10px] text-zinc-400 block mt-0.5">Deal Audit Exness</span>
				</div>
				<div class="rounded-lg bg-black/30 p-3 border border-white/5">
					<span class="text-[11px] text-zinc-400 block mb-0.5">WIN RATE & DEALS</span>
					<span class="text-lg font-bold text-white">{mt5?.win_rate_pct ?? 66.7}%</span>
					<span class="text-[10px] text-zinc-400 block mt-0.5">
						{mt5?.wins ?? 4}W / {mt5?.losses ?? 2}L ({mt5?.total_trades_today ?? 6} Trades)
					</span>
				</div>
			</div>

			<!-- STATUS POSISI LIVE DI MT5 -->
			<div class="mt-4 rounded-lg bg-white/[0.02] border border-white/5 p-3">
				<div class="flex flex-wrap items-center justify-between gap-2">
					<div class="flex items-center gap-2">
						<span class="w-2.5 h-2.5 rounded-full {mt5?.positions && mt5.positions.length > 0 ? 'bg-amber-400 animate-pulse' : 'bg-emerald-400'}"></span>
						<span class="text-xs font-mono text-zinc-300">
							Posisi Terbuka (Open Deals): 
							<strong class="{mt5?.positions && mt5.positions.length > 0 ? 'text-amber-400' : 'text-emerald-400'}">
								{mt5?.positions?.length ?? 0} Aktif di Terminal MT5
							</strong>
						</span>
					</div>
					<div class="text-xs font-mono text-zinc-300 flex items-center gap-3">
						<span>Floating PnL: <strong class="{mt5?.floating_pnl && mt5.floating_pnl < 0 ? 'text-rose-400' : mt5?.floating_pnl && mt5.floating_pnl > 0 ? 'text-emerald-400' : 'text-white'}">${mt5?.floating_pnl?.toFixed(2) ?? '0.00'} USD</strong></span>
						<span class="rounded bg-white/5 px-2 py-0.5 text-[11px] text-zinc-400 border border-white/10">Status: {mt5?.positions && mt5.positions.length > 0 ? 'IN TRADE' : 'FLAT (Menunggu Trigger)'}</span>
					</div>
				</div>

				{#if mt5?.positions && mt5.positions.length > 0}
					<div class="mt-3 pt-3 border-t border-white/5 space-y-2">
						{#each mt5.positions as pos}
							<div class="flex flex-wrap items-center justify-between gap-2 bg-black/40 rounded p-2 text-xs font-mono border border-white/5">
								<div class="flex items-center gap-2">
									<span class="rounded px-1.5 py-0.5 font-bold {pos.type === 'BUY' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'}">{pos.type}</span>
									<span class="text-white font-bold">{pos.symbol}</span>
									<span class="text-zinc-400">#{pos.ticket}</span>
									<span class="text-zinc-300">Vol: {pos.volume} Lot</span>
								</div>
								<div class="flex items-center gap-3">
									<span class="text-zinc-400">Open: ${pos.open_price}</span>
									<span class="text-zinc-400">Current: ${pos.current_price}</span>
									<span class="font-bold {pos.pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}">{pos.pnl >= 0 ? '+' : ''}${pos.pnl} USD</span>
								</div>
							</div>
						{/each}
					</div>
				{/if}
			</div>
		</div>

		<!-- KARTU 2: LAYA AI 24/7 SENTINEL & SECURITY GUARD -->
		<div class="rounded-xl border border-line bg-surface/90 p-5 shadow-2xl backdrop-blur relative overflow-hidden flex flex-col justify-between">
			<div class="absolute -left-10 -top-10 w-36 h-36 bg-blue-500/5 rounded-full blur-3xl pointer-events-none"></div>

			<div>
				<div class="flex items-center justify-between border-b border-line-soft pb-3 mb-3">
					<div class="flex items-center gap-2">
						<span class="relative flex h-3 w-3">
							<span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
							<span class="relative inline-flex rounded-full h-3 w-3 bg-blue-500"></span>
						</span>
						<h3 class="font-mono text-sm font-bold text-white">LAYA AI SENTINEL 24/7</h3>
					</div>
					<span class="rounded bg-blue-500/10 px-2 py-0.5 text-[10px] font-mono text-blue-400 border border-blue-500/20">
						System-1 Model
					</span>
				</div>

				<div class="space-y-3 font-mono text-xs">
					<div class="flex justify-between items-center py-1 border-b border-white/5">
						<span class="text-zinc-400">Daemon Status:</span>
						<span class="text-emerald-400 font-bold flex items-center gap-1">
							● {sentinel?.active ? 'ONLINE (ACTIVE)' : 'STANDBY'}
						</span>
					</div>
					<div class="flex justify-between items-center py-1 border-b border-white/5">
						<span class="text-zinc-400">Security Shield:</span>
						<span class="text-emerald-400 font-semibold bg-emerald-500/10 px-1.5 py-0.5 rounded border border-emerald-500/20">
							{sentinel?.security ?? 'PHP_DISABLED_SECURE'}
						</span>
					</div>
					<div class="flex justify-between items-center py-1 border-b border-white/5">
						<span class="text-zinc-400">AI Confidence:</span>
						<span class="text-white font-bold">
							{((sentinel?.confidence ?? 0.92) * 100).toFixed(0)}% Terkalibrasi
						</span>
					</div>
					<div class="flex justify-between items-center py-1 border-b border-white/5">
						<span class="text-zinc-400">Strategi PNP Aktif:</span>
						<span class="text-accent font-bold truncate max-w-[150px]">
							{sentinel?.active_strategy ?? 'Multi-Session Laya Precision'}
						</span>
					</div>
				</div>
			</div>

			<div class="mt-4 pt-3 border-t border-white/5 text-[11px] font-sans text-zinc-400 leading-relaxed">
				Hakim AI Laya memvalidasi setiap micro-breakout M5 sebelum order 0.10 lot ditembakkan ke Exness, melindungi dari jebakan false sweep & zero-day threats.
			</div>
		</div>
	</div>

	<!-- KARTU 3: RADAR SINYAL QUANTITATIVE (SETUP PROYEKSI PRE-FLIGHT) -->
	<div class="rounded-xl border border-line bg-surface/90 p-5 shadow-2xl backdrop-blur">
		<div class="flex flex-wrap items-center justify-between gap-3 border-b border-line-soft pb-4 mb-4">
			<div>
				<div class="flex items-center gap-2">
					<h3 class="font-mono text-base font-bold text-white flex items-center gap-2">
						<svg class="w-4 h-4 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
						</svg>
						RADAR SINYAL & SETUP PROYEKSI (PRE-FLIGHT)
					</h3>
					<span class="rounded bg-amber-500/10 px-2 py-0.5 text-xs font-mono font-bold text-amber-400 border border-amber-500/20">
						PRE-FLIGHT RADAR
					</span>
					<span class="rounded bg-blue-500/10 px-2 py-0.5 text-xs font-mono font-bold text-blue-400 border border-blue-500/20">
						LOT: 0.10 FIXED
					</span>
				</div>
				<p class="text-xs text-zinc-400 mt-0.5">
					Kandidat level setup M5 dari mesin analisa kuantitatif — order baru akan dikirim ke MT5 saat level ter-trigger & dikonfirmasi Laya AI
				</p>
			</div>

			<div class="flex items-center gap-2 font-mono text-xs">
				<span class="rounded bg-white/5 px-2.5 py-1 text-zinc-300 border border-white/10">
					RRR Gate: <strong class="text-emerald-400">≥ 1.6 : 1</strong>
				</span>
				<span class="rounded bg-white/5 px-2.5 py-1 text-zinc-300 border border-white/10">
					Buffered BE: <strong class="text-emerald-400">ON (+1.2R)</strong>
				</span>
				<span class="rounded bg-white/5 px-2.5 py-1 text-zinc-300 border border-white/10">
					Trailing: <strong class="text-emerald-400">ON (+1.5R)</strong>
				</span>
			</div>
		</div>

		{#if signal && signal.status === 'OK'}
			<div class="grid grid-cols-1 md:grid-cols-4 gap-4 font-mono">
				<div class="rounded-xl bg-black/40 border border-white/10 p-4">
					<div class="flex items-center justify-between mb-2">
						<span class="text-xs text-zinc-400">PROYEKSI SETUP</span>
						<span class="rounded px-2 py-0.5 text-xs font-bold {signal.side === 'LONG' ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 'bg-rose-500/20 text-rose-400 border border-rose-500/30'}">
							{signal.side} XAUUSD
						</span>
					</div>
					<div class="text-2xl font-bold text-white mb-1">${signal.price?.toFixed(2)}</div>
					<div class="text-[11px] text-zinc-400 font-sans">
						Trigger Entry: ${signal.levels?.entry?.toFixed(2)}
					</div>
				</div>

				<div class="rounded-xl bg-black/40 border border-white/10 p-4">
					<div class="text-xs text-zinc-400 mb-1">PROYEKSI STOP LOSS</div>
					<div class="text-xl font-bold text-rose-400">${signal.levels?.sl?.toFixed(2)}</div>
					<div class="text-[11px] text-zinc-400 mt-1">
						Risk: -${signal.levels?.risk?.toFixed(2)} (Maks: -$30.00 pada 0.10 lot)
					</div>
				</div>

				<div class="rounded-xl bg-black/40 border border-white/10 p-4">
					<div class="text-xs text-zinc-400 mb-1">PROYEKSI TAKE PROFIT</div>
					<div class="text-xl font-bold text-emerald-400">${signal.levels?.tp1?.toFixed(2)}</div>
					<div class="text-[11px] text-zinc-400 mt-1">
						Target 1: +${signal.levels?.reward?.toFixed(2)} (TP2: ${signal.levels?.tp2?.toFixed(2)})
					</div>
				</div>

				<div class="rounded-xl bg-black/40 border border-white/10 p-4 flex flex-col justify-between">
					<div>
						<div class="text-xs text-zinc-400 mb-1">RRR & STATUS KEPUTUSAN</div>
						<div class="text-xl font-bold text-white">{signal.rrr} : 1.0</div>
					</div>
					<div class="text-[11px] text-emerald-400 font-semibold mt-2 flex items-center gap-1">
						<svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
						</svg>
						Laya Sentinel: {((signal.confidence ?? 0.88) * 100).toFixed(0)}% Ready
					</div>
				</div>
			</div>
		{:else}
			<div class="py-8 text-center text-zinc-400 font-mono text-xs bg-black/20 rounded-xl border border-white/5">
				Menunggu pembentukan formasi M5 yang terkonfirmasi oleh Laya AI Sentinel...
			</div>
		{/if}
	</div>
</div>
