<script lang="ts">
	import { onMount } from 'svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';

	type SignalItem = {
		id: number;
		channel_id: string;
		channel_name: string;
		category: string;
		message_text: string;
		timestamp: string;
		views: number;
		forwards: number;
	};

	function parseSignal(text: string) {
		const upper = (text || '').toUpperCase();
		const dirMatch = upper.match(/\b(BUY|SELL|LONG|SHORT)\b/);
		const pairMatch = upper.match(/\b(XAUUSD|EURUSD|GBPUSD|USDJPY|BTCUSDT|ETHUSDT|SOLUSDT|BTC|ETH|SOL|[A-Z]{4}(?:\.JK)?)\b/);
		const entryMatch = text.match(/(?:entry|enter|@|price)\s*[:=]?\s*([0-9]+(?:[.,][0-9]+)?)/i);
		const slMatch = text.match(/(?:sl|stop\s*loss)\s*[:=]?\s*([0-9]+(?:[.,][0-9]+)?)/i);
		const tpMatch = text.match(/(?:tp\s*1?|take\s*profit)\s*[:=]?\s*([0-9]+(?:[.,][0-9]+)?)/i);
		return {
			dir: dirMatch?.[1] ?? null,
			pair: pairMatch?.[1] ?? null,
			entry: entryMatch?.[1] ?? null,
			sl: slMatch?.[1] ?? null,
			tp: tpMatch?.[1] ?? null
		};
	}

	let signals = $state<SignalItem[]>([]);
	let loading = $state(true);
	let errorMsg = $state<string | null>(null);
	let search = $state('');
	let activeCategory = $state('SEMUA');
	let onlyValid = $state(false);

	async function fetchSignals() {
		loading = true;
		errorMsg = null;
		try {
			const res = await fetch('/signals/api/signals', { credentials: 'include' });
			if (!res.ok) throw new Error(`HTTP ${res.status}`);
			const json = (await res.json()) as { status?: string; data?: SignalItem[] };
			signals = Array.isArray(json.data) ? json.data : [];
		} catch (e) {
			errorMsg = e instanceof Error ? e.message : 'Gagal memuat sinyal Telegram';
		} finally {
			loading = false;
		}
	}

	onMount(() => {
		void fetchSignals();
		const timer = setInterval(() => void fetchSignals(), 30000);
		return () => clearInterval(timer);
	});

	const categories = $derived.by(() => {
		const set = new Set<string>();
		for (const s of signals) {
			if (s.category) set.add(s.category.toUpperCase());
		}
		return ['SEMUA', ...Array.from(set).sort()];
	});

	const filtered = $derived.by(() => {
		const q = search.trim().toLowerCase();
		return signals.filter((s) => {
			if (onlyValid) {
				const p = parseSignal(s.message_text);
				if (!p.dir && !p.entry && !p.sl && !p.tp) return false;
			}
			if (activeCategory !== 'SEMUA' && (s.category ?? '').toUpperCase() !== activeCategory) {
				return false;
			}
			if (!q) return true;
			return (
				(s.channel_name ?? '').toLowerCase().includes(q) ||
				(s.category ?? '').toLowerCase().includes(q) ||
				(s.message_text ?? '').toLowerCase().includes(q)
			);
		});
	});
</script>

<svelte:head><title>Sinyal Telegram | War Room</title></svelte:head>

<div class="space-y-4">
	<PageHeader
		eyebrow="War Room · Intelligence"
		title="Sinyal Telegram"
		tag="LIVE 24/7"
		description="Pemantau real-time channel sinyal Telegram lintas market yang terintegrasi native ke dalam War Room."
		sumber="/signals/api/signals"
		terverifikasi={true}
	>
		{#snippet action()}
			<button
				type="button"
				onclick={() => void fetchSignals()}
				class="inline-flex min-h-[38px] items-center gap-1.5 rounded-control border border-line bg-surface-2 px-3 py-1.5 font-mono text-11 font-bold text-text hover:border-accent hover:text-accent"
			>
				<span>{loading ? 'Memuat…' : 'Muat Ulang'}</span>
			</button>
		{/snippet}
	</PageHeader>

	<!-- Filter & Search Bar -->
	<div class="flex flex-wrap items-center justify-between gap-3 rounded-card border border-line bg-surface p-3">
		<div class="flex flex-wrap items-center gap-1.5">
			{#each categories as cat}
				<button
					type="button"
					onclick={() => (activeCategory = cat)}
					class="rounded-control border px-2.5 py-1 font-mono text-11 font-bold transition-colors {activeCategory === cat
						? 'border-accent bg-accent/15 text-accent'
						: 'border-line bg-surface-2 text-dim hover:text-text'}"
				>
					{cat}
				</button>
			{/each}
			<button
				type="button"
				onclick={() => (onlyValid = !onlyValid)}
				class="ml-1 rounded-control border px-2.5 py-1 font-mono text-11 font-bold transition-colors {onlyValid
					? 'border-pos bg-pos/15 text-pos'
					: 'border-line bg-surface-2 text-dim hover:text-text'}"
			>
				{onlyValid ? '✓ Hanya Sinyal Valid' : 'Filter: Sinyal Valid'}
			</button>
		</div>

		<input
			type="search"
			bind:value={search}
			placeholder="Cari channel, ticker, pesan..."
			class="w-full rounded-control border border-line bg-canvas px-3 py-1.5 font-mono text-12 text-text placeholder:text-dim focus:border-accent focus:outline-none sm:w-64"
		/>
	</div>

	{#if errorMsg}
		<div class="rounded-card border border-neg/40 bg-neg/10 p-4 font-mono text-12 text-neg">
			Gagal memuat sinyal: {errorMsg}
		</div>
	{:else if loading && signals.length === 0}
		<div class="rounded-card border border-line bg-surface p-6 text-center font-mono text-12 text-dim">
			Memuat sinyal Telegram…
		</div>
	{:else if filtered.length === 0}
		<div class="rounded-card border border-dashed border-line bg-surface p-6 text-center font-mono text-12 text-dim">
			Tidak ada sinyal yang cocok dengan filter saat ini.
		</div>
	{:else}
		<div class="grid gap-3 md:grid-cols-2">
			{#each filtered as item (item.id)}
				{@const parsed = parseSignal(item.message_text)}
				<article class="flex flex-col justify-between gap-2 rounded-card border border-line bg-surface p-4">
					<div class="flex items-start justify-between gap-2">
						<div class="min-w-0">
							<div class="truncate font-mono text-12 font-bold text-text">
								{item.channel_name || item.channel_id}
							</div>
							<div class="font-mono text-10 text-dim">{item.timestamp}</div>
						</div>
						{#if item.category}
							<span class="shrink-0 rounded-control border border-line bg-surface-2 px-2 py-0.5 font-mono text-10 font-bold text-accent">
								{item.category}
							</span>
						{/if}
					</div>

					{#if parsed.dir || parsed.pair || parsed.entry || parsed.sl || parsed.tp}
						<div class="flex flex-wrap items-center gap-1.5 font-mono text-10">
							{#if parsed.pair}
								<span class="rounded border border-line bg-surface-2 px-1.5 py-0.5 font-bold text-text">{parsed.pair}</span>
							{/if}
							{#if parsed.dir}
								<span class="rounded px-1.5 py-0.5 font-bold {parsed.dir === 'BUY' || parsed.dir === 'LONG' ? 'bg-pos/15 text-pos' : 'bg-neg/15 text-neg'}">{parsed.dir}</span>
							{/if}
							{#if parsed.entry}
								<span class="rounded border border-line bg-canvas px-1.5 py-0.5 text-text-2">Entry: {parsed.entry}</span>
							{/if}
							{#if parsed.sl}
								<span class="rounded border border-neg/30 bg-neg/10 px-1.5 py-0.5 text-neg">SL: {parsed.sl}</span>
							{/if}
							{#if parsed.tp}
								<span class="rounded border border-pos/30 bg-pos/10 px-1.5 py-0.5 text-pos">TP: {parsed.tp}</span>
							{/if}
						</div>
					{/if}

					<p class="whitespace-pre-wrap break-words text-12 leading-relaxed text-text/90">
						{item.message_text}
					</p>

					<div class="flex items-center gap-3 border-t border-line/60 pt-2 font-mono text-10 text-dim">
						<span>ID #{item.id}</span>
						<span>Views: {item.views ?? 0}</span>
						<span>Forwards: {item.forwards ?? 0}</span>
					</div>
				</article>
			{/each}
		</div>
	{/if}
</div>
