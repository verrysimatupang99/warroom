<script lang="ts">
	interface Props {
		market: 'forex' | 'crypto' | 'idx' | 'polymarket';
		defaultSymbol?: string;
	}
	let { market, defaultSymbol = 'XAUUSD' }: Props = $props();

	let strategyId = $state('break_retest_forex_m15');
	let symbol = $state(defaultSymbol);
	let timeframe = $state('M15');
	let riskPct = $state(1.5);
	let slAtr = $state(1.6);
	let tpRrr = $state(3.0);
	let running = $state(false);
	let result = $state<{ status?: string; trades?: number; pf?: number; win_rate?: number; pnl_pct?: number; message?: string } | null>(null);
	let errorMsg = $state<string | null>(null);

	async function jalankan(mode: 'backtest' | 'live') {
		running = true;
		errorMsg = null;
		result = null;
		try {
			const res = await fetch(`/api/v1/strategies/${strategyId}/backtest`, {
				method: 'POST',
				headers: { 'content-type': 'application/json' },
				credentials: 'include',
				body: JSON.stringify({
					mode,
					market,
					symbol,
					timeframe,
					risk_pct: riskPct,
					sl_atr: slAtr,
					tp_rrr: tpRrr
				})
			});
			if (!res.ok) throw new Error(`HTTP ${res.status}`);
			const json = (await res.json()) as { result?: typeof result };
			result = json.result ?? { status: 'OK' };
		} catch (e) {
			errorMsg = e instanceof Error ? e.message : 'Gagal menjalankan strategi';
		} finally {
			running = false;
		}
	}
</script>

<section class="rounded-card border border-line bg-surface p-4 space-y-4">
	<div class="flex flex-wrap items-center justify-between gap-2">
		<div>
			<h3 class="font-mono text-12 font-bold text-text">Uji &amp; Jalankan Strategi ({market.toUpperCase()})</h3>
			<p class="text-11 text-text-3">Isi parameter strategi di bawah ini untuk menjalankan backtest atau auto-trade langsung di mesin eksekusi.</p>
		</div>
		<span class="rounded border border-line bg-surface-2 px-2 py-0.5 font-mono text-10 text-accent">
			MODULAR ENGINE
		</span>
	</div>

	<div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
		<label class="space-y-1">
			<span class="block font-mono text-10 text-dim">PAIR / SIMBOL</span>
			<input type="text" bind:value={symbol} class="w-full rounded-control border border-line bg-canvas px-2.5 py-1.5 font-mono text-12 text-text focus:border-accent focus:outline-none" />
		</label>
		<label class="space-y-1">
			<span class="block font-mono text-10 text-dim">TIMEFRAME</span>
			<select bind:value={timeframe} class="w-full rounded-control border border-line bg-canvas px-2.5 py-1.5 font-mono text-12 text-text focus:border-accent focus:outline-none">
				<option value="M5">M5</option>
				<option value="M15">M15</option>
				<option value="H1">H1</option>
				<option value="H4">H4</option>
			</select>
		</label>
		<label class="space-y-1">
			<span class="block font-mono text-10 text-dim">RISK / TRADE (%)</span>
			<input type="number" step="0.1" min="0.5" max="2.0" bind:value={riskPct} class="w-full rounded-control border border-line bg-canvas px-2.5 py-1.5 font-mono text-12 text-text focus:border-accent focus:outline-none" />
		</label>
		<label class="space-y-1">
			<span class="block font-mono text-10 text-dim">SL (x ATR)</span>
			<input type="number" step="0.1" min="0.5" max="5.0" bind:value={slAtr} class="w-full rounded-control border border-line bg-canvas px-2.5 py-1.5 font-mono text-12 text-text focus:border-accent focus:outline-none" />
		</label>
		<label class="space-y-1">
			<span class="block font-mono text-10 text-dim">TP (RRR 1:X)</span>
			<input type="number" step="0.5" min="1.0" max="5.0" bind:value={tpRrr} class="w-full rounded-control border border-line bg-canvas px-2.5 py-1.5 font-mono text-12 text-text focus:border-accent focus:outline-none" />
		</label>
	</div>

	<div class="flex flex-wrap items-center gap-2">
		<button
			type="button"
			disabled={running}
			onclick={() => void jalankan('backtest')}
			class="rounded-control border border-accent bg-accent/15 px-3 py-1.5 font-mono text-11 font-bold text-accent hover:bg-accent/25 disabled:opacity-50"
		>
			{running ? 'Memproses…' : '▶ Jalankan Backtest'}
		</button>
		<button
			type="button"
			disabled={running}
			onclick={() => void jalankan('live')}
			class="rounded-control border border-pos bg-pos/15 px-3 py-1.5 font-mono text-11 font-bold text-pos hover:bg-pos/25 disabled:opacity-50"
		>
			⚡ Jalankan Auto-Trade
		</button>
	</div>

	{#if errorMsg}
		<div class="rounded-control border border-neg/40 bg-neg/10 p-2.5 font-mono text-11 text-neg">
			{errorMsg}
		</div>
	{/if}
	{#if result}
		<div class="rounded-control border border-pos/30 bg-pos/10 p-3 font-mono text-11 text-text">
			Status: <strong class="text-pos">{result.status ?? 'OK'}</strong> · Simbol: <strong>{symbol}</strong> ({timeframe}) · Risk: <strong>{riskPct}%</strong> · SL: <strong>{slAtr}x ATR</strong> · RRR: <strong>1:{tpRrr}</strong>
		</div>
	{/if}
</section>
