<script lang="ts">
	// EquityCurve: Grafik kurva return R kumulatif interaktif.
	// Bersih, presisi, tanpa chart library berat — SVG murni dan responsif.
	import { angka } from '$lib/format';

	interface Point {
		i: number;
		r: number;
	}

	interface Stats {
		trades?: number;
		wins?: number;
		losses?: number;
		total_r?: number;
		winrate_pct?: number;
		expectancy_r?: number;
		max_drawdown_r?: number;
	}

	interface Props {
		points?: Point[] | null;
		stats?: Stats | null;
	}

	let { points = [], stats = null }: Props = $props();

	let hoverPoint = $state<Point | null>(null);

	const validPoints = $derived(
		(points ?? []).filter((p) => p && typeof p.r === 'number' && Number.isFinite(p.r))
	);

	const cukup = $derived(validPoints.length >= 2);

	const W = 600;
	const H = 160;
	const PAD_X = 36;
	const PAD_Y = 24;

	const minR = $derived.by(() => {
		if (!validPoints.length) return 0;
		const m = Math.min(...validPoints.map((p) => p.r));
		return m < 0 ? m * 1.15 : -0.5; // beri ruang di bawah nol
	});

	const maxR = $derived.by(() => {
		if (!validPoints.length) return 1;
		const m = Math.max(...validPoints.map((p) => p.r));
		return m > 0 ? m * 1.15 : 1;
	});

	const rRange = $derived(maxR - minR || 1);

	function toX(index: number): number {
		if (validPoints.length <= 1) return PAD_X;
		return PAD_X + (index / (validPoints.length - 1)) * (W - PAD_X * 2);
	}

	function toY(r: number): number {
		return PAD_Y + (H - PAD_Y * 2) - ((r - minR) / rRange) * (H - PAD_Y * 2);
	}

	const zeroY = $derived(toY(0));

	const pathLine = $derived.by(() => {
		if (!cukup) return '';
		return validPoints
			.map((p, idx) => `${idx === 0 ? 'M' : 'L'} ${toX(idx).toFixed(1)} ${toY(p.r).toFixed(1)}`)
			.join(' ');
	});

	const pathArea = $derived.by(() => {
		if (!pathLine || !validPoints.length) return '';
		const firstX = toX(0).toFixed(1);
		const lastX = toX(validPoints.length - 1).toFixed(1);
		return `${pathLine} L ${lastX} ${zeroY.toFixed(1)} L ${firstX} ${zeroY.toFixed(1)} Z`;
	});

	const isPositive = $derived((stats?.total_r ?? validPoints[validPoints.length - 1]?.r ?? 0) >= 0);
	const strokeColor = $derived(isPositive ? 'var(--color-pos)' : 'var(--color-neg)');
</script>

<div class="permukaan-2 rounded-card border border-line p-3">
	<div class="mb-3 flex flex-wrap items-center justify-between gap-2 border-b border-line-soft pb-2.5">
		<div>
			<h3 class="text-13 font-medium text-text">Kurva Ekuitas (R Kumulatif)</h3>
			<p class="text-11 text-text-3">Performa kumulatif unit risiko (R) dari waktu ke waktu</p>
		</div>

		{#if stats}
			<div class="flex flex-wrap items-center gap-3 text-11">
				<div class="flex items-center gap-1">
					<span class="text-text-3">Total R:</span>
					<span class="angka text-13 font-bold {isPositive ? 'text-pos' : 'text-neg'}">
						{stats.total_r != null && stats.total_r > 0 ? '+' : ''}{angka(stats.total_r ?? 0)} R
					</span>
				</div>
				{#if stats.winrate_pct != null}
					<div class="flex items-center gap-1">
						<span class="text-text-3">Win Rate:</span>
						<span class="angka text-text">{angka(stats.winrate_pct)}%</span>
					</div>
				{/if}
				{#if stats.expectancy_r != null}
					<div class="flex items-center gap-1">
						<span class="text-text-3">Exp:</span>
						<span class="angka text-text">{angka(stats.expectancy_r)} R/trade</span>
					</div>
				{/if}
				{#if stats.trades != null}
					<div class="flex items-center gap-1 text-text-3">
						<span>Trades:</span>
						<span class="angka text-text-2">{stats.trades}</span>
					</div>
				{/if}
			</div>
		{/if}
	</div>

	{#if cukup}
		<div class="relative w-full overflow-hidden">
			<svg
				viewBox={`0 0 ${W} ${H}`}
				class="w-full h-44 overflow-visible"
				preserveAspectRatio="none"
				role="img"
				aria-label="Grafik kurva ekuitas R"
			>
				<defs>
					<linearGradient id="equityGradient" x1="0" y1="0" x2="0" y2="1">
						<stop offset="0%" stop-color={strokeColor} stop-opacity="0.25" />
						<stop offset="100%" stop-color={strokeColor} stop-opacity="0.0" />
					</linearGradient>
				</defs>

				<!-- Garis nol (Baseline) -->
				<line
					x1={PAD_X}
					y1={zeroY}
					x2={W - PAD_X}
					y2={zeroY}
					stroke="var(--color-line)"
					stroke-dasharray="3 3"
					stroke-width="1"
				/>
				<text
					x={PAD_X - 6}
					y={zeroY + 3}
					fill="var(--color-text-3)"
					font-size="10"
					text-anchor="end"
					class="angka"
				>0R</text>

				<!-- Label Atas & Bawah -->
				<text
					x={PAD_X - 6}
					y={PAD_Y + 4}
					fill="var(--color-text-3)"
					font-size="10"
					text-anchor="end"
					class="angka"
				>{maxR.toFixed(1)}R</text>

				<!-- Area bayangan gradien -->
				<path d={pathArea} fill="url(#equityGradient)" />

				<!-- Garis utama kurva -->
				<path
					d={pathLine}
					fill="none"
					stroke={strokeColor}
					stroke-width="2"
					stroke-linecap="round"
					stroke-linejoin="round"
				/>

				<!-- Titik-titik data -->
				{#each validPoints as p, idx}
					{@const cx = toX(idx)}
					{@const cy = toY(p.r)}
					<circle
						cx={cx}
						cy={cy}
						r={hoverPoint === p ? 5 : 3}
						fill="var(--color-bg)"
						stroke={strokeColor}
						stroke-width="2"
						class="cursor-pointer transition-all"
						onmouseenter={() => (hoverPoint = p)}
						onmouseleave={() => (hoverPoint = null)}
					/>
				{/each}
			</svg>

			{#if hoverPoint}
				<div
					class="absolute top-2 right-2 rounded border border-line bg-surface px-2 py-1 text-11 shadow-lg pointer-events-none"
				>
					<span class="text-text-3">Trade #{hoverPoint.i}:</span>
					<span class="angka font-bold {hoverPoint.r >= 0 ? 'text-pos' : 'text-neg'}">
						{hoverPoint.r >= 0 ? '+' : ''}{angka(hoverPoint.r)} R
					</span>
				</div>
			{/if}
		</div>
	{:else}
		<div class="flex h-36 flex-col items-center justify-center text-center text-text-3">
			<p class="text-12">Belum cukup data titik ekuitas untuk menggambar kurva.</p>
			<p class="text-11 mt-1">Data akan otomatis digambar setelah minimal 2 trade tercatat.</p>
		</div>
	{/if}
</div>
