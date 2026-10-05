<script lang="ts">
	// SignalCard: Kartu setup trading modern & actionable.
	// Menyajikan pair, arah, entry, SL, TP, dan checklist aturan secara visual.
	import { angka, waktuWIB } from '$lib/format';

	interface RuleItem {
		rule?: string;
		ok?: boolean;
		hard?: boolean;
		reason?: string;
	}

	interface SetupData {
		pair?: string;
		arah?: string;
		direction?: string;
		tier?: string;
		entry?: number;
		sl?: number;
		tp1?: number;
		risk_pct?: number;
		ts?: string;
		rules?: RuleItem[];
		aturan_gagal?: string[];
	}

	interface Props {
		setup: SetupData;
	}

	let { setup }: Props = $props();

	let expandRules = $state(false);

	const rawArah = $derived((setup.direction ?? setup.arah ?? 'LONG').toUpperCase());
	const isLong = $derived(rawArah === 'LONG');
	const pairClean = $derived(
		(setup.pair ?? 'UNKNOWN').replace(/USDT$/, ' / USDT').replace(/USD$/, ' / USD')
	);

	// Deteksi bila TP atau SL berada di sisi yang salah (anomali arah)
	const isArahAnomali = $derived.by(() => {
		if (!setup.entry || !setup.tp1) return false;
		if (isLong && setup.tp1 <= setup.entry) return true;
		if (!isLong && setup.tp1 >= setup.entry) return true;
		return false;
	});

	// Hitung rasio Risk-Reward (RR)
	const rr = $derived.by(() => {
		if (!setup.entry || !setup.sl || !setup.tp1) return null;
		const risk = Math.abs(setup.entry - setup.sl);
		const reward = Math.abs(setup.tp1 - setup.entry);
		if (risk === 0) return null;
		return (reward / risk).toFixed(1);
	});

	const slDistancePct = $derived.by(() => {
		if (!setup.entry || !setup.sl) return null;
		return (Math.abs(setup.entry - setup.sl) / setup.entry * 100).toFixed(2);
	});
</script>

<div class="permukaan-2 rounded-card border border-line p-3 transition-all hover:border-line-soft">
	<div class="flex flex-wrap items-center justify-between gap-2 border-b border-line-soft pb-2">
		<div class="flex items-center gap-2">
			<span class="text-14 font-bold tracking-tight text-text font-mono">{pairClean}</span>
			<span
				class="rounded px-2 py-0.5 text-11 font-bold tracking-wider uppercase {isLong
					? 'bg-pos/15 text-pos border border-pos/30'
					: 'bg-neg/15 text-neg border border-neg/30'}"
			>
				{rawArah}
			</span>
			{#if isArahAnomali}
				<span class="rounded bg-warn/15 text-warn border border-warn/30 px-1.5 py-0.5 text-9 font-bold">
					⚠ Sisi TP Tidak Sesuai Arah
				</span>
			{/if}
		</div>

		<div class="flex items-center gap-1.5 text-11">
			{#if setup.tier}
				<span class="rounded bg-surface px-1.5 py-0.5 font-mono text-text-3 border border-line">
					{setup.tier}
				</span>
			{/if}
			{#if rr}
				<span class="rounded bg-accent/10 px-1.5 py-0.5 font-mono font-medium text-accent border border-accent/20">
					1:{rr} R:R
				</span>
			{/if}
		</div>
	</div>

	<!-- Price Targets Grid -->
	<div class="my-2.5 grid grid-cols-3 gap-2 text-center">
		<div class="rounded bg-surface p-1.5 border border-line-soft">
			<span class="text-10 uppercase text-text-3 block">Entry</span>
			<span class="angka text-12 font-bold text-text">
				{setup.entry != null ? angka(setup.entry) : '—'}
			</span>
		</div>

		<div class="rounded bg-surface p-1.5 border border-line-soft">
			<span class="text-10 uppercase text-neg block">Stop Loss</span>
			<span class="angka text-12 font-bold text-neg">
				{setup.sl != null ? angka(setup.sl) : '—'}
			</span>
			{#if slDistancePct}
				<span class="text-9 text-text-3 block mt-0.5">({slDistancePct}%)</span>
			{/if}
		</div>

		<div class="rounded bg-surface p-1.5 border border-line-soft">
			<span class="text-10 uppercase text-pos block">Take Profit</span>
			<span class="angka text-12 font-bold text-pos">
				{setup.tp1 != null ? angka(setup.tp1) : '—'}
			</span>
		</div>
	</div>

	<!-- Friksi & Biaya Eksekusi (Inspirasi Fomo Family) -->
	<div class="mb-2 flex items-center justify-between rounded bg-surface/60 px-2 py-1 text-10 font-mono text-text-3 border border-line-soft">
		<div class="flex items-center gap-1.5">
			<span class="text-accent font-bold">Friksi:</span>
			<span>Maker 0.00% (MEXC) · Taker 0.05%</span>
		</div>
		<div class="flex items-center gap-1">
			<span>BE Move: <b class="text-text-2">~0.04%</b></span>
			<span>·</span>
			<span class="text-pos font-bold">Paper Safe</span>
		</div>
	</div>

	<!-- Rules Summary & Toggle -->
	{#if setup.rules && setup.rules.length}
		{@const gagalCount = setup.rules.filter((r) => !r.ok).length}
		<div class="border-t border-line-soft pt-2">
			<button
				type="button"
				class="flex w-full items-center justify-between text-11 text-text-3 hover:text-text"
				onclick={() => (expandRules = !expandRules)}
			>
				<span class="flex items-center gap-1.5">
					{#if gagalCount === 0}
						<span class="text-pos">✓ Semua ({setup.rules.length}) aturan lolos</span>
					{:else}
						<span class="text-warn">⚠ {gagalCount} dari {setup.rules.length} aturan belum lolos</span>
					{/if}
				</span>
				<span>{expandRules ? '▲ tutup' : '▼ rincian'}</span>
			</button>

			{#if expandRules}
				<ul class="mt-2 space-y-1 rounded bg-surface p-2 text-11">
					{#each setup.rules as r}
						<li class="flex items-start gap-1.5">
							<span class="font-bold {r.ok ? 'text-pos' : 'text-neg'}">{r.ok ? '✓' : '✗'}</span>
							<div class="flex-1">
								<span class="font-mono text-text-2">{r.rule}</span>
								{#if r.reason}
									<p class="text-10 text-text-3">{r.reason}</p>
								{/if}
							</div>
						</li>
					{/each}
				</ul>
			{/if}
		</div>
	{/if}

	{#if setup.ts}
		<div class="mt-2 text-right text-10 text-text-3">
			Waktu: {waktuWIB(setup.ts)}
		</div>
	{/if}
</div>
