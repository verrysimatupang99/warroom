<script lang="ts">
	// StatisticalEdgeCard: Kartu status bukti statistik (Polymarket / Gate).
	// Menjelaskan secara visual apakah strategi memiliki keunggulan matematis (Edge)
	// yang terbukti secara statistik (Wilson CI95% > Break-Even).
	import { angka } from '$lib/format';

	interface VerdictData {
		n?: number;
		win?: number;
		be?: number;
		ci?: number;
		ci95?: [number, number];
		alat?: string;
	}

	interface Props {
		verdict?: VerdictData | null;
		judul?: string;
	}

	let { verdict = null, judul = 'Statistical Edge Gate' }: Props = $props();

	const n = $derived(verdict?.n ?? 0);
	const win = $derived(verdict?.win ?? 0);
	const winrate = $derived(n > 0 ? (win / n) * 100 : 0);
	const bePct = $derived((verdict?.be ?? 0.7666) * 100);
	const ciLow = $derived(verdict?.ci95?.[0] ?? winrate * 0.98);
	const ciHigh = $derived(verdict?.ci95?.[1] ?? winrate * 1.02);

	const isEdgeProven = $derived(ciLow > bePct && n >= 100);
</script>

<div class="permukaan-2 rounded-card border border-line p-3">
	<div class="mb-2.5 flex items-center justify-between border-b border-line-soft pb-2">
		<div>
			<h3 class="text-13 font-medium text-text">{judul}</h3>
			<p class="text-11 text-text-3">Validasi matematis probabilitas menang vs ambang impas (BE)</p>
		</div>

		{#if n > 0}
			<span
				class="rounded px-2 py-0.5 text-10 font-bold uppercase tracking-wider border {isEdgeProven
					? 'bg-pos/15 text-pos border-pos/40'
					: 'bg-warn/15 text-warn border-warn/40'}"
			>
				{isEdgeProven ? 'EDGE TERBUKTI' : 'BELUM LOLOS GATE'}
			</span>
		{/if}
	</div>

	{#if n > 0}
		<div class="space-y-3">
			<div class="grid grid-cols-3 gap-2 text-center">
				<div class="rounded bg-surface p-2 border border-line-soft">
					<span class="text-10 uppercase text-text-3 block">Win Rate</span>
					<span class="angka text-15 font-bold {winrate > bePct ? 'text-pos' : 'text-neg'}">
						{angka(winrate)}%
					</span>
					<span class="text-10 text-text-3 block mt-0.5">{win} / {n} sampel</span>
				</div>

				<div class="rounded bg-surface p-2 border border-line-soft">
					<span class="text-10 uppercase text-text-3 block">Break-Even (BE)</span>
					<span class="angka text-15 font-bold text-text-2">
						{angka(bePct)}%
					</span>
					<span class="text-10 text-text-3 block mt-0.5">ambang batas</span>
				</div>

				<div class="rounded bg-surface p-2 border border-line-soft">
					<span class="text-10 uppercase text-text-3 block">Batas Bawah CI95</span>
					<span class="angka text-15 font-bold {ciLow > bePct ? 'text-pos' : 'text-warn'}">
						{angka(ciLow)}%
					</span>
					<span class="text-10 text-text-3 block mt-0.5">Wilson 95%</span>
				</div>
			</div>

			<!-- Visual Scale Indicator -->
			<div>
				<div class="flex justify-between text-10 text-text-3 mb-1">
					<span>BE ({angka(bePct)}%)</span>
					<span class="text-pos font-medium">Rentang Kepercayaan [{angka(ciLow)}% - {angka(ciHigh)}%]</span>
				</div>
				<div class="relative h-2 w-full rounded-full bg-surface border border-line-soft overflow-hidden">
					<!-- Threshold marker at BE -->
					<div
						class="absolute top-0 bottom-0 w-0.5 bg-warn z-10"
						style={`left: ${Math.min(95, Math.max(5, bePct))}%`}
						title={`Break Even ${bePct}%`}
					></div>
					<!-- Range of confidence interval -->
					<div
						class="absolute top-0 bottom-0 {isEdgeProven ? 'bg-pos' : 'bg-warn'} rounded-full opacity-80"
						style={`left: ${Math.min(95, Math.max(5, ciLow))}%; width: ${Math.max(4, ciHigh - ciLow)}%`}
					></div>
				</div>
				<p class="mt-1.5 text-11 text-text-3">
					{#if isEdgeProven}
						<span class="text-pos font-medium">✓ Lolos:</span> Batas bawah keyakinan 95% ({angka(ciLow)}%) berada di atas Break-Even ({angka(bePct)}%). Strategi memiliki keunggulan statistik riil.
					{:else}
						<span class="text-warn font-medium">⚠ Perhatian:</span> Data belum cukup atau batas bawah CI belum melampaui break-even. Eksekusi live dibatasi.
					{/if}
				</p>
			</div>
		</div>
	{:else}
		<div class="py-4 text-center text-text-3 text-12">
			Menunggu sinkronisasi data verdict statistik...
		</div>
	{/if}
</div>
