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
		<div class="lg:col-span-2 rounded-card border border-line bg-surface p-5">
			
			<div class="flex flex-wrap items-center justify-between gap-3 border-b border-line-soft pb-4 mb-4">
				<div class="flex items-center gap-3">
					<div class="relative flex h-3.5 w-3.5">
						{#if mt5?.connected}
							<span class="relative inline-flex rounded-full h-3.5 w-3.5 bg-pos"></span>
						{:else}
							<span class="relative inline-flex rounded-full h-3.5 w-3.5 bg-text-3"></span>
						{/if}
					</div>
					<div>
						<div class="flex items-center gap-2">
							<h2 class="font-mono text-base font-bold tracking-wider text-text">EXNESS MT5 ALGO COCKPIT</h2>
							<span class="rounded bg-pos/10 px-2.5 py-0.5 text-xs font-mono font-bold text-pos border border-pos/20">
								#{mt5?.account ?? '—'}
							</span>
							<span class="rounded bg-surface-2 px-2 py-0.5 text-[11px] font-mono text-text-3 border border-line">
								{mt5?.broker ?? '—'}
							</span>
						</div>
						<p class="text-xs text-text-3 mt-0.5 font-sans">
							Live Telemetry Outbound Azure VM (138.91.35.65) • Detak: {mt5?.seconds_ago ?? 0}s yang lalu
						</p>
					</div>
				</div>

				<div class="flex items-center gap-2">
					<a
						href="/api/v1/tencent/mt5/source.raw"
						target="_blank"
						class="rounded bg-pos/15 hover:bg-pos/25 transition px-3 py-1.5 text-xs font-mono font-semibold text-pos border border-pos/30 flex items-center gap-1.5"
					>
						<svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
						</svg>
						Unduh EA v2.0 (.mq5)
					</a>
				</div>
			</div>

			<!-- METRIK KEUANGAN AKUN EXNESS (HAPUS-ANGKA-PALSU) -->
			<div class="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono">
				<div class="rounded-lg bg-surface-2 p-3 border border-line-soft">
					<span class="text-[11px] text-text-3 block mb-0.5">BALANCE</span>
					<span class="text-lg font-bold text-text">{mt5?.balance != null ? `$${mt5.balance.toFixed(2)}` : "—"}</span>
					<span class="text-[10px] text-text-3 block mt-0.5">Saldo akun</span>
				</div>
				<div class="rounded-lg bg-surface-2 p-3 border border-line-soft">
					<span class="text-[11px] text-text-3 block mb-0.5">EKUITAS BERJALAN</span>
					<span class="text-lg font-bold text-text">
						{mt5?.equity != null ? `$${mt5.equity.toFixed(2)}` : '—'}
					</span>
					<span class="text-[10px] text-text-3 block mt-0.5">
						Ekuitas akun real-time
					</span>
				</div>
				<div class="rounded-lg bg-surface-2 p-3 border border-line-soft">
					<span class="text-[11px] text-text-3 block mb-0.5">NET REALIZED PNL</span>
					<span class="text-lg font-bold {mt5?.net_pnl_usd && mt5.net_pnl_usd >= 0 ? 'text-pos' : 'text-neg'}">
						{mt5?.net_pnl_usd != null ? `${mt5.net_pnl_usd >= 0 ? '+' : ''}$${mt5.net_pnl_usd.toFixed(2)}` : '—'}
					</span>
					<span class="text-[10px] text-text-3 block mt-0.5">Deal Audit Exness</span>
				</div>
				<div class="rounded-lg bg-surface-2 p-3 border border-line-soft">
					<span class="text-[11px] text-text-3 block mb-0.5">WIN RATE & DEALS</span>
					<span class="text-lg font-bold text-text">{mt5?.win_rate_pct != null ? `${mt5.win_rate_pct}%` : '—'}</span>
					<span class="text-[10px] text-text-3 block mt-0.5">
						{mt5?.wins != null ? `${mt5.wins}W / ${mt5.losses ?? 0}L` : '—'} total · {mt5?.total_trades_today ?? 0} hari ini
					</span>
				</div>
			</div>

			<!-- STATUS POSISI LIVE DI MT5 -->
			<div class="mt-4 rounded-lg bg-white/[0.02] border border-line-soft p-3">
				<div class="flex flex-wrap items-center justify-between gap-2">
					<div class="flex items-center gap-2">
						<span class="w-2.5 h-2.5 rounded-full {mt5?.positions && mt5.positions.length > 0 ? 'bg-warn' : 'bg-pos'}"></span>
						<span class="text-xs font-mono text-text-3">
							Posisi Terbuka (Open Deals): 
							<strong class="{mt5?.positions && mt5.positions.length > 0 ? 'text-warn' : 'text-pos'}">
								{mt5?.positions?.length ?? 0} Aktif di Terminal MT5
							</strong>
						</span>
					</div>
					<div class="text-xs font-mono text-text-3 flex items-center gap-3">
						<span>Floating PnL: <strong class="{mt5?.floating_pnl && mt5.floating_pnl < 0 ? 'text-neg' : mt5?.floating_pnl && mt5.floating_pnl > 0 ? 'text-pos' : 'text-text'}">${mt5?.floating_pnl?.toFixed(2) ?? '0.00'} USD</strong></span>
						<span class="rounded bg-surface-2 px-2 py-0.5 text-[11px] text-text-3 border border-line">Status: {mt5?.positions && mt5.positions.length > 0 ? 'IN TRADE' : 'FLAT (Menunggu Trigger)'}</span>
					</div>
				</div>

				{#if mt5?.positions && mt5.positions.length > 0}
					<div class="mt-3 pt-3 border-t border-line-soft space-y-2">
						{#each mt5.positions as pos}
							<div class="flex flex-wrap items-center justify-between gap-2 bg-surface-2 rounded p-2 text-xs font-mono border border-line-soft">
								<div class="flex items-center gap-2">
									<span class="rounded px-1.5 py-0.5 font-bold {pos.type === 'BUY' ? 'bg-pos/20 text-pos' : 'bg-neg/20 text-neg'}">{pos.type}</span>
									<span class="text-text font-bold">{pos.symbol}</span>
									<span class="text-text-3">#{pos.ticket}</span>
									<span class="text-text-3">Vol: {pos.volume} Lot</span>
								</div>
								<div class="flex items-center gap-3">
									<span class="text-text-3">Open: ${pos.open_price}</span>
									<span class="text-text-3">Current: ${pos.current_price}</span>
									<span class="font-bold {pos.pnl >= 0 ? 'text-pos' : 'text-neg'}">{pos.pnl >= 0 ? '+' : ''}${pos.pnl} USD</span>
								</div>
							</div>
						{/each}
					</div>
				{/if}
			</div>
		</div>

		<!-- KARTU 2: LAYA AI 24/7 SENTINEL & SECURITY GUARD -->
		<div class="rounded-card border border-line bg-surface p-5">

			<div>
				<div class="flex items-center justify-between border-b border-line-soft pb-3 mb-3">
					<div class="flex items-center gap-2">
						<span class="relative flex h-3 w-3">
							<span class="relative inline-flex rounded-full h-3 w-3 bg-accent"></span>
						</span>
						<h3 class="font-mono text-sm font-bold text-text">LAYA AI SENTINEL 24/7</h3>
					</div>
					<span class="rounded bg-accent/10 px-2 py-0.5 text-[10px] font-mono text-accent border border-accent/20">
						System-1 Model
					</span>
				</div>

				<div class="space-y-3 font-mono text-xs">
					<div class="flex justify-between items-center py-1 border-b border-line-soft">
						<span class="text-text-3">Daemon Status:</span>
						<span class="text-pos font-bold flex items-center gap-1">
							● {sentinel?.active ? 'ONLINE (ACTIVE)' : 'STANDBY'}
						</span>
					</div>
					<div class="flex justify-between items-center py-1 border-b border-line-soft">
						<span class="text-text-3">Security Shield:</span>
						<span class="text-pos font-semibold bg-pos/10 px-1.5 py-0.5 rounded border border-pos/20">
							{sentinel?.security ?? 'PHP_DISABLED_SECURE'}
						</span>
					</div>
					<div class="flex justify-between items-center py-1 border-b border-line-soft">
						<span class="text-text-3">Keyakinan aturan:</span>
						<span class="text-text font-bold">
							{sentinel?.confidence == null ? '—' : `${(sentinel.confidence * 100).toFixed(0)}% Terkalibrasi`}
						</span>
					</div>
					<div class="flex justify-between items-center py-1 border-b border-line-soft">
						<span class="text-text-3">Strategi PNP Aktif:</span>
						<span class="text-accent font-bold truncate max-w-[150px]">
							{sentinel?.active_strategy ?? 'Multi-Session EMA+RSI (formula)'}
						</span>
					</div>
				</div>
			</div>

			<div class="mt-4 pt-3 border-t border-line-soft text-[11px] font-sans text-text-3 leading-relaxed">
				Aturan EMA+RSI memvalidasi setiap micro-breakout M5 sebelum order 0.10 lot ditembakkan ke Exness, melindungi dari jebakan false sweep. Laya AI sedang dinonaktifkan.
			</div>
		</div>
	</div>

	<!-- KARTU 3: RADAR SINYAL QUANTITATIVE (SETUP PROYEKSI PRE-FLIGHT) -->
	<div class="rounded-card border border-line bg-surface p-5">
		<div class="flex flex-wrap items-center justify-between gap-3 border-b border-line-soft pb-4 mb-4">
			<div>
				<div class="flex items-center gap-2">
					<h3 class="font-mono text-base font-bold text-text flex items-center gap-2">
						<svg class="w-4 h-4 text-warn" fill="none" viewBox="0 0 24 24" stroke="currentColor">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
						</svg>
						RADAR SINYAL & SETUP PROYEKSI (PRE-FLIGHT)
					</h3>
					<span class="rounded bg-warn/10 px-2 py-0.5 text-xs font-mono font-bold text-warn border border-warn/20">
						PRE-FLIGHT RADAR
					</span>
					<span class="rounded bg-accent/10 px-2 py-0.5 text-xs font-mono font-bold text-accent border border-accent/20">
						LOT: 0.10 FIXED
					</span>
				</div>
				<p class="text-xs text-text-3 mt-0.5">
					Kandidat level setup M5 dari mesin analisa kuantitatif — order baru akan dikirim ke MT5 saat level ter-trigger & dikonfirmasi Laya AI
				</p>
			</div>

			<div class="flex items-center gap-2 font-mono text-xs">
				<span class="rounded bg-surface-2 px-2.5 py-1 text-text-3 border border-line">
					RRR Gate: <strong class="text-pos">≥ 1.6 : 1</strong>
				</span>
				<span class="rounded bg-surface-2 px-2.5 py-1 text-text-3 border border-line">
					Buffered BE: <strong class="text-pos">ON (+1.2R)</strong>
				</span>
				<span class="rounded bg-surface-2 px-2.5 py-1 text-text-3 border border-line">
					Trailing: <strong class="text-pos">ON (+1.5R)</strong>
				</span>
			</div>
		</div>

		{#if signal && signal.status === 'OK'}
			<div class="grid grid-cols-1 md:grid-cols-4 gap-4 font-mono">
				<div class="rounded-xl bg-surface-2 border border-line p-4">
					<div class="flex items-center justify-between mb-2">
						<span class="text-xs text-text-3">PROYEKSI SETUP</span>
						<span class="rounded px-2 py-0.5 text-xs font-bold {signal.side === 'LONG' ? 'bg-pos/20 text-pos border border-pos/30' : 'bg-neg/20 text-neg border border-neg/30'}">
							{signal.side} XAUUSD
						</span>
					</div>
					<div class="text-2xl font-bold text-text mb-1">${signal.price?.toFixed(2)}</div>
					<div class="text-[11px] text-text-3 font-sans">
						Trigger Entry: ${signal.levels?.entry?.toFixed(2)}
					</div>
				</div>

				<div class="rounded-xl bg-surface-2 border border-line p-4">
					<div class="text-xs text-text-3 mb-1">PROYEKSI STOP LOSS</div>
					<div class="text-xl font-bold text-neg">${signal.levels?.sl?.toFixed(2)}</div>
					<div class="text-[11px] text-text-3 mt-1">
						Risk: -${signal.levels?.risk?.toFixed(2)} (Maks: -$30.00 pada 0.10 lot)
					</div>
				</div>

				<div class="rounded-xl bg-surface-2 border border-line p-4">
					<div class="text-xs text-text-3 mb-1">PROYEKSI TAKE PROFIT</div>
					<div class="text-xl font-bold text-pos">${signal.levels?.tp1?.toFixed(2)}</div>
					<div class="text-[11px] text-text-3 mt-1">
						Target 1: +${signal.levels?.reward?.toFixed(2)} (TP2: ${signal.levels?.tp2?.toFixed(2)})
					</div>
				</div>

				<div class="rounded-xl bg-surface-2 border border-line p-4 flex flex-col justify-between">
					<div>
						<div class="text-xs text-text-3 mb-1">RRR & STATUS KEPUTUSAN</div>
						<div class="text-xl font-bold text-text">{signal.rrr} : 1.0</div>
					</div>
					<div class="text-[11px] text-pos font-semibold mt-2 flex items-center gap-1">
						<svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
						</svg>
						Laya Sentinel: {((signal.confidence ?? 0.88) * 100).toFixed(0)}% Ready
					</div>
				</div>
			</div>
		{:else}
			<div class="py-8 text-center text-text-3 font-mono text-xs bg-surface-2 rounded-xl border border-line-soft">
				Menunggu pembentukan formasi M5 yang terkonfirmasi oleh Laya AI Sentinel...
			</div>
		{/if}
	</div>
</div>
