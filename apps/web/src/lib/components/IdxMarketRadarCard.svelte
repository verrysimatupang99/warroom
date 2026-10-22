<script lang="ts">
	import { onMount } from 'svelte';

	interface IdxSignal {
		time: string;
		ticker: string;
		name?: string;
		preset: string;
		price: number;
		change_pct: number;
		rsi?: number;
		score?: number;
		confidence?: string;
		notes?: string;
		volume?: number;
	}

	interface IdxStats {
		total_runs?: number;
		unique_tickers_tracked?: number;
		total_signals?: number;
		universe_size?: number;
		signal_counts_by_preset?: Record<string, number>;
	}

	interface IdxLedger {
		signals?: number;
		filled?: number;
		pending?: number;
		closed?: number;
		tp1?: number;
		tp2?: number;
		sl?: number;
		win_rate?: number;
		expectancy_r?: number;
		profit_factor?: number;
	}

	let stats = $state<IdxStats | null>(null);
	let ledger = $state<IdxLedger | null>(null);
	let signals = $state<IdxSignal[]>([]);
	let loading = $state(true);
	let gagal = $state<string | null>(null);

	async function muatIdx() {
		try {
			const [st, led, sig] = await Promise.all([
				fetch('/api/v1/idx/stats'),
				fetch('/api/v1/idx/ledger'),
				fetch('/api/v1/idx/signals?limit=12'),
			]);
			if (!st.ok || !sig.ok) {
				gagal = `MiniMax IDX tidak terbaca (stats ${st.status}, signals ${sig.status})`;
				return;
			}
			stats = await st.json();
			ledger = led.ok ? await led.json() : null;
			const payload = await sig.json();
			signals = payload.signals ?? [];
			gagal = null;
		} catch (e) {
			gagal = 'Gagal menghubungi API IDX';
			console.error(e);
		} finally {
			loading = false;
		}
	}

	onMount(() => {
		muatIdx();
		const t = setInterval(muatIdx, 60000);
		return () => clearInterval(t);
	});
</script>

<div class="rounded-card border border-line bg-surface p-4 shadow-xl backdrop-blur-sm">
	<div class="flex flex-wrap items-center justify-between gap-3 border-b border-line-soft pb-3">
		<div class="flex items-center gap-2.5">
			<div class="flex h-8 w-8 items-center justify-center rounded-control bg-neg/10 border border-neg/20 text-neg font-mono font-bold text-xs">
				IDX
			</div>
			<div>
				<div class="flex items-center gap-2">
					<h3 class="font-mono text-sm font-semibold tracking-wider text-text">
						RADAR SAHAM INDONESIA
					</h3>
					<span class="rounded-control bg-neg/10 px-2 py-0.5 text-[10px] font-medium font-mono text-neg border border-neg/20">
						HERMES DATA API
					</span>
				</div>
				<p class="text-xs text-text-3 font-sans">
					Sinyal &amp; ledger IDX dari node MiniMax (Tailscale) — read-only
				</p>
			</div>
		</div>

		{#if stats}
			<div class="flex items-center gap-3 font-mono text-[11px] text-text-3">
				<span>RUN <strong class="text-text">{stats.total_runs ?? 0}</strong></span>
				<span>TICKER <strong class="text-text">{stats.unique_tickers_tracked ?? 0}</strong></span>
				<span>SINYAL <strong class="text-text">{stats.total_signals ?? 0}</strong></span>
			</div>
		{/if}
	</div>

	{#if gagal}
		<p class="mt-3 rounded-control bg-neg/10 px-3 py-2 text-xs font-mono text-neg border border-neg/20">
			{gagal}
		</p>
	{/if}

	{#if ledger}
		<div class="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
			<div class="rounded-control bg-surface-2 p-2 border border-line-soft">
				<span class="text-[10px] font-mono uppercase text-text-3">Win Rate</span>
				<div class="mt-0.5 font-mono text-sm font-bold text-text">
					{ledger.win_rate ?? 0}%
				</div>
			</div>
			<div class="rounded-control bg-surface-2 p-2 border border-line-soft">
				<span class="text-[10px] font-mono uppercase text-text-3">Expectancy</span>
				<div class="mt-0.5 font-mono text-sm font-bold text-text">
					{ledger.expectancy_r ?? 0}R
				</div>
			</div>
			<div class="rounded-control bg-surface-2 p-2 border border-line-soft">
				<span class="text-[10px] font-mono uppercase text-text-3">Profit Factor</span>
				<div class="mt-0.5 font-mono text-sm font-bold text-text">
					{ledger.profit_factor ?? 0}
				</div>
			</div>
			<div class="rounded-control bg-surface-2 p-2 border border-line-soft">
				<span class="text-[10px] font-mono uppercase text-text-3">Closed</span>
				<div class="mt-0.5 font-mono text-sm font-bold text-text">
					{ledger.closed ?? 0}/{ledger.signals ?? 0}
				</div>
			</div>
		</div>
	{/if}

	<!-- Sinyal terbaru -->
	<div class="mt-3 space-y-1.5">
		{#if loading && signals.length === 0}
			{#each Array(4) as _}
				<div class="animate-pulse rounded-control bg-surface-2 p-2.5 h-12 border border-line-soft"></div>
			{/each}
		{:else if signals.length === 0}
			<p class="rounded-control bg-surface-2 py-3 text-center text-xs font-mono text-text-3">
				Belum ada sinyal IDX yang tercatat.
			</p>
		{:else}
			{#each signals as s}
				<div class="rounded-control bg-surface-2 px-3 py-2 border border-line-soft">
					<div class="flex flex-wrap items-center justify-between gap-2">
						<div class="flex items-baseline gap-2">
							<span class="font-mono text-sm font-bold text-text">{s.ticker}</span>
							<span class="text-[11px] font-sans text-text-3">{s.name ?? ''}</span>
							<span class="rounded-control bg-accent/10 px-1.5 py-0.5 text-[10px] font-mono text-accent border border-accent/20">
								{s.preset}
							</span>
						</div>
						<div class="flex items-baseline gap-3 font-mono text-xs">
							<span class="text-text-2">Rp {s.price.toLocaleString('id-ID')}</span>
							<span class="font-bold {s.change_pct >= 0 ? 'text-pos' : 'text-neg'}">
								{s.change_pct >= 0 ? '+' : ''}{s.change_pct.toFixed(2)}%
							</span>
							{#if s.score !== undefined}
								<span class="text-text-3">skor {s.score}</span>
							{/if}
						</div>
					</div>
				</div>
			{/each}
		{/if}
	</div>
</div>
