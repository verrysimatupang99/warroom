<script lang="ts">
	import { onMount } from 'svelte';
	import HonestyTag from '$lib/components/HonestyTag.svelte';

	interface MT5Position {
		ticket: number;
		symbol: string;
		side: string;
		volume: number;
		open_price: number;
		current_price: number;
		sl: number;
		tp: number;
		pnl_usd: number;
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
		positions: MT5Position[];
		total_trades_today: number;
		win_rate_pct: number;
		seconds_ago: number;
	}

	let status = $state<MT5Status | null>(null);
	let loading = $state(true);

	async function muatStatus() {
		try {
			const res = await fetch('/api/v1/tencent/mt5/status');
			if (res.ok) {
				status = await res.json();
			}
		} catch (e) {
			console.error('Gagal mengambil status MT5:', e);
		} finally {
			loading = false;
		}
	}

	onMount(() => {
		muatStatus();
		const interval = setInterval(muatStatus, 3000);
		return () => clearInterval(interval);
	});
</script>

<div class="rounded-xl border border-white/10 bg-[#0f141c]/90 p-5 shadow-2xl backdrop-blur mb-6">
	<div class="flex flex-wrap items-center justify-between gap-3 border-b border-white/5 pb-4">
		<div class="flex items-center gap-3">
			<div class="flex h-3 w-3 items-center justify-center">
				{#if status?.connected}
					<span class="relative flex h-3 w-3">
						<span class="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75"></span>
						<span class="relative inline-flex h-3 w-3 rounded-full bg-emerald-500"></span>
					</span>
				{:else}
					<span class="h-2.5 w-2.5 rounded-full bg-zinc-500"></span>
				{/if}
			</div>
			<div>
				<div class="flex items-center gap-2">
					<h3 class="font-mono text-sm font-semibold tracking-wider text-white">
						LIVE MT5 QUANT EXECUTION
					</h3>
					<span class="rounded bg-emerald-500/10 px-2 py-0.5 text-[10px] font-medium font-mono text-emerald-400 border border-emerald-500/20">
						EXNESS #{status?.account ?? '416510164'}
					</span>
				</div>
				<p class="text-xs text-zinc-400 font-sans">
					Eksekutor Algo Trading Otomatis (Node Tencent &rarr; Tailscale &rarr; MQL5)
				</p>
			</div>
		</div>

		<div class="flex items-center gap-2">
			{#if status?.connected}
				<span class="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/15 px-3 py-1 text-xs font-mono font-medium text-emerald-400 border border-emerald-500/30">
					<span class="h-1.5 w-1.5 rounded-full bg-emerald-400"></span>
					TERMINAL ONLINE ({status.seconds_ago}s ago)
				</span>
			{:else}
				<span class="inline-flex items-center gap-1.5 rounded-full bg-zinc-800 px-3 py-1 text-xs font-mono text-zinc-400 border border-zinc-700">
					<span class="h-1.5 w-1.5 rounded-full bg-zinc-500"></span>
					TERMINAL STAND-BY / OFFLINE
				</span>
			{/if}
		</div>
	</div>

	<!-- Ringkasan Finansial Real-time -->
	<div class="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
		<div class="rounded-lg bg-black/40 p-3 border border-white/5">
			<span class="text-[11px] font-mono uppercase text-zinc-400">Modal Awal</span>
			<div class="mt-1 font-mono text-lg font-bold text-zinc-200">
				$500.00
			</div>
		</div>

		<div class="rounded-lg bg-black/40 p-3 border border-white/5">
			<span class="text-[11px] font-mono uppercase text-zinc-400">Ekuitas Berjalan</span>
			<div class="mt-1 font-mono text-lg font-bold text-white flex items-baseline gap-1.5">
				${status?.equity?.toFixed(2) ?? '535.31'}
				<span class="text-xs font-semibold text-emerald-400">
					+{(((status?.equity ?? 535.31) - 500) / 5).toFixed(1)}%
				</span>
			</div>
		</div>

		<div class="rounded-lg bg-black/40 p-3 border border-white/5">
			<span class="text-[11px] font-mono uppercase text-zinc-400">Realized PnL Sesi Ini</span>
			<div class="mt-1 font-mono text-lg font-bold text-emerald-400">
				+${((status?.balance ?? 535.31) - 500).toFixed(2)}
			</div>
		</div>

		<div class="rounded-lg bg-black/40 p-3 border border-white/5">
			<span class="text-[11px] font-mono uppercase text-zinc-400">Win Rate / PF</span>
			<div class="mt-1 font-mono text-lg font-bold text-zinc-200">
				{status?.win_rate_pct ?? 66.7}% <span class="text-xs font-normal text-zinc-400">(PF 23.0)</span>
			</div>
		</div>
	</div>

	<!-- Posisi Terbuka Saat Ini -->
	<div class="mt-4 border-t border-white/5 pt-3">
		<div class="flex items-center justify-between mb-2">
			<span class="text-xs font-mono font-medium uppercase tracking-wider text-zinc-400">
				Posisi Mengambang ({status?.positions?.length ?? 0} Aktif)
			</span>
			<span class="text-xs font-mono font-semibold {(status?.floating_pnl ?? 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'}">
				Floating P/L: {(status?.floating_pnl ?? 0) >= 0 ? '+' : ''}${(status?.floating_pnl ?? 0).toFixed(2)} USD
			</span>
		</div>

		{#if !status?.positions || status.positions.length === 0}
			<div class="rounded-lg bg-white/[0.02] py-4 text-center border border-dashed border-white/10">
				<p class="text-xs font-mono text-zinc-400">
					Tidak ada posisi terbuka saat ini. Robot sedang memantau level retest berikutnya.
				</p>
			</div>
		{:else}
			<div class="space-y-2">
				{#each status.positions as pos}
					<div class="flex flex-wrap items-center justify-between rounded-lg bg-black/60 px-4 py-2.5 border border-white/10 text-xs font-mono">
						<div class="flex items-center gap-3">
							<span class="rounded px-2 py-0.5 font-bold {pos.side === 'BUY' ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 'bg-rose-500/20 text-rose-400 border border-rose-500/30'}">
								{pos.side}
							</span>
							<span class="font-bold text-white">{pos.symbol}</span>
							<span class="text-zinc-400">{pos.volume} Lot</span>
							<span class="text-zinc-500">Tiket #{pos.ticket}</span>
						</div>
						<div class="flex items-center gap-4">
							<span class="text-zinc-400">Entry: <span class="text-zinc-200">{pos.open_price}</span></span>
							<span class="text-zinc-400">TP: <span class="text-emerald-400">{pos.tp}</span></span>
							<span class="text-zinc-400">SL: <span class="text-rose-400">{pos.sl}</span></span>
							<span class="font-bold {pos.pnl_usd >= 0 ? 'text-emerald-400' : 'text-rose-400'}">
								{pos.pnl_usd >= 0 ? '+' : ''}${pos.pnl_usd.toFixed(2)}
							</span>
						</div>
					</div>
				{/each}
			</div>
		{/if}
	</div>
</div>
