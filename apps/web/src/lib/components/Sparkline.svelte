<script lang="ts">
	// Sparkline SVG murni. Aturan: tidak ada seri (atau < 2 titik) → TIDAK dirender,
	// supaya tidak ada grafik kosong yang menyamar sebagai data.
	interface Props {
		seri: number[] | null | undefined;
		lebar?: number;
		tinggi?: number;
		warna?: string;
		isi?: boolean;
		judul?: string;
	}
	let {
		seri,
		lebar = 120,
		tinggi = 32,
		warna = 'var(--color-accent-2)',
		isi = false,
		judul = 'kurva mini'
	}: Props = $props();

	const titik = $derived((seri ?? []).filter((v) => typeof v === 'number' && Number.isFinite(v)));
	const cukup = $derived(titik.length >= 2);
	const lintasan = $derived.by(() => {
		if (!cukup) return '';
		const min = Math.min(...titik);
		const maks = Math.max(...titik);
		const rentang = maks - min || 1;
		const pad = 2;
		const w = lebar - pad * 2;
		const h = tinggi - pad * 2;
		return titik
			.map((v, i) => {
				const x = pad + (i / (titik.length - 1)) * w;
				const y = pad + h - ((v - min) / rentang) * h;
				return `${i === 0 ? 'M' : 'L'}${x.toFixed(2)},${y.toFixed(2)}`;
			})
			.join(' ');
	});
	const area = $derived(
		lintasan ? `${lintasan} L${lebar - 2},${tinggi - 2} L2,${tinggi - 2} Z` : ''
	);
</script>

{#if cukup}
	<svg
		width={lebar}
		height={tinggi}
		viewBox={`0 0 ${lebar} ${tinggi}`}
		role="img"
		aria-label={judul}
		class="block"
		data-testid="sparkline"
	>
		{#if isi}<path d={area} fill={warna} opacity="0.14" />{/if}
		<path
			d={lintasan}
			fill="none"
			stroke={warna}
			stroke-width="1.5"
			stroke-linecap="round"
			stroke-linejoin="round"
		/>
	</svg>
{/if}