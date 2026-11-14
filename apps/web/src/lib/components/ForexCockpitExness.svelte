<script lang="ts">
	import { onMount } from 'svelte';
	import { urlApi } from '$lib/api/client';
	import Skeleton from '$lib/components/Skeleton.svelte';

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
		currency?: string;
		cent_factor?: number;
		balance: number;
		equity: number;
		floating_pnl: number;
		margin: number;
		free_margin: number;
		positions: Array<any>;
		total_trades_today?: number | null;
		win_rate_pct?: number | null;
		wins_today?: number | null;
		losses_today?: number | null;
		win_rate_today_pct?: number | null;
		net_pnl_today_usd?: number | null;
		wins?: number;
		losses?: number;
		net_pnl_usd?: number;
		seconds_ago: number;
		bid?: number | null;
		ask?: number | null;
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
	let galat = $state<string | null>(null);
	let streamConnected = $state(false);
	let streamStatus = $state<'connecting' | 'connected' | 'disconnected'>('connecting');

	let evtSource: EventSource | null = null;

	let isCent = $derived(mt5?.currency === 'USC' || mt5?.account === '452009427');
	let modalAwal = $derived(
		mt5?.account === '452009427' ? 1008.0 : isCent ? 1000.0 : 500.0
	);
	let retPct = $derived(
		mt5?.equity !== undefined && modalAwal > 0
			? ((mt5.equity - modalAwal) / modalAwal) * 100
			: 0
	);
	let pnlToday = $derived(
		mt5?.net_pnl_today_usd != null
			? mt5.net_pnl_today_usd
			: (mt5?.equity !== undefined ? mt5.equity - modalAwal : null)
	);
	let winsDisplay = $derived(mt5?.wins_today ?? mt5?.wins ?? 0);
	let lossesDisplay = $derived(mt5?.losses_today ?? mt5?.losses ?? 0);
	let totalTradesDisplay = $derived(
		mt5?.total_trades_today != null && mt5.total_trades_today > 0
			? mt5.total_trades_today
			: (winsDisplay + lossesDisplay)
	);
	let winRateDisplay = $derived(
		mt5?.win_rate_today_pct ??
		mt5?.win_rate_pct ??
		(totalTradesDisplay > 0 ? Math.round((winsDisplay / totalTradesDisplay) * 1000) / 10 : 0)
	);

	function formatUang(v?: number | null) {
		if (v == null) return '—';
		if (isCent) {
			const usd = (v / 100).toFixed(2);
			return `${v.toFixed(2)} USC ($${usd})`;
		}
		return `$${v.toFixed(2)}`;
	}

	function formatPnl(v?: number | null) {
		if (v == null) return '—';
		const sign = v > 0 ? '+' : '';
		if (isCent) {
			const usd = (v / 100).toFixed(2);
			return `${sign}${v.toFixed(2)} USC (${sign}$${usd})`;
		}
		return `${sign}$${v.toFixed(2)}`;
	}

	function handleTelemetryPacket(packet: Partial<MT5Status>) {
		if (!packet) return;
		mt5 = {
			connected: packet.connected ?? true,
			account: packet.account ?? mt5?.account ?? '452009427',
			broker: packet.broker ?? mt5?.broker ?? 'Exness Technologies Ltd',
			currency: packet.currency ?? mt5?.currency,
			cent_factor: packet.cent_factor ?? mt5?.cent_factor,
			balance: packet.balance ?? mt5?.balance ?? 0,
			equity: packet.equity ?? mt5?.equity ?? 0,
			floating_pnl: packet.floating_pnl ?? mt5?.floating_pnl ?? 0,
			margin: packet.margin ?? mt5?.margin ?? 0,
			free_margin: packet.free_margin ?? mt5?.free_margin ?? 0,
			positions: packet.positions ?? mt5?.positions ?? [],
			total_trades_today: packet.total_trades_today ?? mt5?.total_trades_today,
			win_rate_pct: packet.win_rate_pct ?? mt5?.win_rate_pct,
			wins_today: packet.wins_today ?? mt5?.wins_today,
			losses_today: packet.losses_today ?? mt5?.losses_today,
			win_rate_today_pct: packet.win_rate_today_pct ?? mt5?.win_rate_today_pct,
			net_pnl_today_usd: packet.net_pnl_today_usd ?? mt5?.net_pnl_today_usd,
			wins: packet.wins ?? mt5?.wins,
			losses: packet.losses ?? mt5?.losses,
			net_pnl_usd: packet.net_pnl_usd ?? mt5?.net_pnl_usd,
			seconds_ago: packet.seconds_ago ?? 0,
			bid: packet.bid ?? mt5?.bid,
			ask: packet.ask ?? mt5?.ask
		};
	}

	async function fetchInitialData() {
		try {
			const [resMt5, resSen, resSig] = await Promise.all([
				fetch(urlApi('/api/v1/tencent/mt5/status?account=452009427'), { credentials: 'include' }),
				fetch(urlApi('/api/v1/tencent/forex/sentinel'), { credentials: 'include' }),
				fetch(urlApi('/api/v1/tencent/forex/levels?symbol=XAUUSD'), { credentials: 'include' })
			]);
			if (resMt5.ok) {
				const data = await resMt5.json();
				handleTelemetryPacket(data);
			}
			if (resSen.ok) sentinel = await resSen.json();
			if (resSig.ok) signal = await resSig.json();
			galat = null;
		} catch (e) {
			console.error('Error fetching forex dashboard data:', e);
			galat = e instanceof Error ? e.message : 'Gagal menghubungi server';
		} finally {
			loading = false;
		}
	}

	function connectSse() {
		if (typeof window === 'undefined' || typeof EventSource === 'undefined') {
			streamStatus = 'disconnected';
			return;
		}

		if (evtSource) {
			evtSource.close();
			evtSource = null;
		}

		streamStatus = 'connecting';
		const streamUrl = urlApi('/api/v1/tencent/forex/stream?account=452009427');

		try {
			evtSource = new EventSource(streamUrl, { withCredentials: true });

			evtSource.onopen = () => {
				streamConnected = true;
				streamStatus = 'connected';
				galat = null;
			};

			evtSource.onmessage = (event) => {
				if (!event.data) return;
				try {
					const packet = JSON.parse(event.data);
					handleTelemetryPacket(packet);
					streamConnected = true;
					streamStatus = 'connected';
					loading = false;
				} catch (err) {
					console.warn('Failed to parse SSE packet:', err);
				}
			};

			evtSource.onerror = () => {
				streamConnected = false;
				streamStatus = 'disconnected';
			};
		} catch (e) {
			streamConnected = false;
			streamStatus = 'disconnected';
		}
	}

	function retry() {
		loading = true;
		galat = null;
		void fetchInitialData();
		connectSse();
	}

	onMount(() => {
		void fetchInitialData();
		connectSse();

		return () => {
			if (evtSource) {
				evtSource.close();
				evtSource = null;
			}
		};
	});
</script>

<div class="space-y-6">
	<!-- ERROR BANNER WITH RETRY BUTTON -->
	{#if galat && !mt5}
		<div class="rounded-card border border-neg/30 bg-neg/10 p-4 text-xs font-mono text-neg flex flex-wrap items-center justify-between gap-3" role="alert">
			<div class="flex items-center gap-2">
				<span class="inline-block w-2.5 h-2.5 rounded-full bg-neg animate-pulse"></span>
				<span>Gagal memuat telemetri forex: {galat}</span>
			</div>
			<button
				type="button"
				class="px-3 py-1.5 rounded bg-neg text-white font-bold hover:bg-neg/80 transition cursor-pointer"
				onclick={retry}
			>
				Coba Lagi
			</button>
		</div>
	{/if}

	<!-- HEADER COCKPIT: EXNESS MT5 & LAYA AI SENTINEL STATUS -->
	<div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
		<!-- KARTU 1: EXNESS MT5 REAL-TIME TELEMETRY -->
		<div class="lg:col-span-2 rounded-card border border-line bg-surface p-5">
			
			<div class="flex flex-wrap items-center justify-between gap-3 border-b border-line-soft pb-4 mb-4">
				<div class="flex items-center gap-3">
					<div class="relative flex h-3.5 w-3.5">
						{#if mt5?.connected}
							<span class="relative inline-flex rounded-full h-3.5 w-3.5 bg-pos"></span>
						{:else if streamStatus === 'connecting'}
							<span class="relative inline-flex rounded-full h-3.5 w-3.5 bg-warn animate-pulse"></span>
						{:else}
							<span class="relative inline-flex rounded-full h-3.5 w-3.5 bg-text-3"></span>
						{/if}
					</div>
					<div>
						<div class="flex items-center gap-2">
							<h2 class="font-mono text-base font-bold tracking-wider text-text">EXNESS MT5 ALGO COCKPIT</h2>
							{#if !loading && mt5}
								<span class="rounded bg-pos/10 px-2.5 py-0.5 text-xs font-mono font-bold text-pos border border-pos/20">
									#{mt5.account}
								</span>
								{#if isCent}
									<span class="rounded bg-amber-500/15 px-2 py-0.5 text-xs font-mono font-bold text-amber-400 border border-amber-500/30">
										CENT
									</span>
								{/if}
								<span class="rounded bg-surface-2 px-2 py-0.5 text-[11px] font-mono text-text-3 border border-line">
									{mt5.broker}
								</span>
							{/if}
							<!-- LIVE STATUS PILL -->
							<span class="rounded px-2 py-0.5 text-[10px] font-mono font-bold border {streamConnected ? 'bg-pos/15 text-pos border-pos/30' : streamStatus === 'connecting' ? 'bg-warn/15 text-warn border-warn/30' : 'bg-surface-2 text-text-3 border-line'}">
								{streamConnected ? 'LIVE STREAM' : streamStatus === 'connecting' ? 'CONNECTING...' : 'DISCONNECTED'}
							</span>
						</div>
						<p class="text-xs text-text-3 mt-0.5 font-sans">
							Live Telemetry Outbound Instabox Cloud (box-2aacb3)
							{#if mt5}
								• Detak: {mt5.seconds_ago ?? 0}s yang lalu
								{#if mt5.bid != null || mt5.ask != null}
									• <span class="font-mono font-bold text-text">BID: ${mt5.bid?.toFixed(2) ?? '—'} / ASK: ${mt5.ask?.toFixed(2) ?? '—'}</span>
								{/if}
							{/if}
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

			{#if loading && !mt5}
				<div class="py-4">
					<Skeleton baris={4} tinggi={36} />
				</div>
			{:else}
				<!-- METRIK KEUANGAN AKUN EXNESS (HAPUS-ANGKA-PALSU) -->
				<div class="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono">
					<div class="rounded-lg bg-surface-2 p-3 border border-line-soft">
						<span class="text-[11px] text-text-3 block mb-0.5">MODAL / SALDO</span>
						<span class="text-lg font-bold text-text">{formatUang(mt5?.balance ?? modalAwal)}</span>
						<span class="text-[10px] text-text-3 block mt-0.5">{isCent ? 'Saldo Akun (Real Cent)' : 'Baseline Demo'}</span>
					</div>
					<div class="rounded-lg bg-surface-2 p-3 border border-line-soft">
						<span class="text-[11px] text-text-3 block mb-0.5">EKUITAS BERJALAN</span>
						<span class="text-lg font-bold {retPct >= 0 ? 'text-pos' : 'text-neg'}">
							{formatUang(mt5?.equity)}
						</span>
						<span class="text-[10px] {retPct >= 0 ? 'text-pos' : 'text-neg'} block mt-0.5">
							{retPct >= 0 ? '+' : ''}{retPct.toFixed(2)}%
						</span>
					</div>
					<div class="rounded-lg bg-surface-2 p-3 border border-line-soft">
						<span class="text-[11px] text-text-3 block mb-0.5">NET REALIZED PNL</span>
						<span class="text-lg font-bold {pnlToday && pnlToday >= 0 ? 'text-pos' : 'text-neg'}">
							{formatPnl(pnlToday)}
						</span>
						<span class="text-[10px] text-text-3 block mt-0.5">Audit Broker Exness</span>
					</div>
					<div class="rounded-lg bg-surface-2 p-3 border border-line-soft">
						<span class="text-[11px] text-text-3 block mb-0.5">WIN RATE & DEALS</span>
						<span class="text-lg font-bold text-text">{winRateDisplay}%</span>
						<span class="text-[10px] text-text-3 block mt-0.5">
							{winsDisplay}W / {lossesDisplay}L ({totalTradesDisplay} Trades)
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
							<span>Floating PnL: <strong class="{mt5?.floating_pnl && mt5.floating_pnl < 0 ? 'text-neg' : mt5?.floating_pnl && mt5.floating_pnl > 0 ? 'text-pos' : 'text-text'}">{formatPnl(mt5?.floating_pnl ?? 0)}</strong></span>
							<span class="rounded bg-surface-2 px-2 py-0.5 text-[11px] text-text-3 border border-line">Status: {mt5?.positions && mt5.positions.length > 0 ? 'IN TRADE' : 'FLAT (Menunggu Trigger)'}</span>
						</div>
					</div>

					{#if mt5?.positions && mt5.positions.length > 0}
						<div class="mt-3 pt-3 border-t border-line-soft space-y-2">
							{#each mt5.positions as pos}
								{@const arah = pos.side ?? pos.type ?? 'BUY'}
								{@const nilaiPnl = pos.pnl_usd ?? pos.pnl ?? 0}
								<div class="flex flex-wrap items-center justify-between gap-2 bg-surface-2 rounded p-2 text-xs font-mono border border-line-soft">
									<div class="flex items-center gap-2">
										<span class="rounded px-1.5 py-0.5 font-bold {arah === 'BUY' ? 'bg-pos/20 text-pos' : 'bg-neg/20 text-neg'}">{arah}</span>
										<span class="text-text font-bold">{pos.symbol}</span>
										<span class="text-text-3">#{pos.ticket}</span>
										<span class="text-text-3">Vol: {pos.volume} Lot</span>
									</div>
									<div class="flex flex-wrap items-center gap-3">
										<span class="text-text-3">Open: ${pos.open_price}</span>
										<span class="text-text-3">Current: ${pos.current_price}</span>
										{#if pos.sl}<span class="text-neg">SL: ${pos.sl}</span>{/if}
										{#if pos.tp}<span class="text-pos">TP: ${pos.tp}</span>{/if}
										<span class="font-bold {nilaiPnl >= 0 ? 'text-pos' : 'text-neg'}">{formatPnl(nilaiPnl)}</span>
									</div>
								</div>
							{/each}
						</div>
					{/if}
				</div>
			{/if}
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

				{#if loading && !sentinel}
					<Skeleton baris={4} tinggi={20} />
				{:else}
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
				{/if}
			</div>

			<div class="mt-4 pt-3 border-t border-line-soft text-[11px] font-sans text-text-3 leading-relaxed">
				Aturan EMA+RSI+ATR di GOLD_Reaper_Hexa memvalidasi setup M5 pada Sesi London (15:00–16:59 WIB) & NY (20:15–22:59 WIB) sebelum Twin-Order 0.01 lot (Scalp +0.7R & Runner +2.0R) ditembakkan ke Exness.
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
						TWIN: 2×0.01 LOT
					</span>
				</div>
				<p class="text-xs text-text-3 mt-0.5">
					Kandidat level setup M5 dari mesin analisa kuantitatif; eksekusi live dilakukan EA saat jendela sesi London/NY & filter M15/H1 terpenuhi
				</p>
			</div>

			<div class="flex flex-wrap items-center gap-2 font-mono text-xs">
				<span class="rounded bg-surface-2 px-2.5 py-1 text-text-3 border border-line">
					Target: <strong class="text-pos">+0.7R / +2.0R</strong>
				</span>
				<span class="rounded bg-surface-2 px-2.5 py-1 text-text-3 border border-line">
					Buffered BE: <strong class="text-pos">ON (+0.7R)</strong>
				</span>
				<span class="rounded bg-surface-2 px-2.5 py-1 text-text-3 border border-line">
					Ratchet & Squeeze: <strong class="text-pos">0.5R / 0.3R</strong>
				</span>
			</div>
		</div>

		{#if loading && !signal}
			<Skeleton baris={3} tinggi={28} />
		{:else if signal && signal.status === 'OK'}
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
						Risk: -${signal.levels?.risk?.toFixed(2)} harga (Twin 2×0.01 lot)
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
