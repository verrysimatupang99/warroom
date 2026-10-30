<script lang="ts">
	// Kurva ekuitas ringan (SVG murni) dengan penanda deal tertutup.
	// Sumbu Y = ekuitas; sumbu X = urutan rekaman (bukan waktu linear) supaya celah
	// telemetri tidak membuat garis putus. Penanda ditempel ke titik terdekat.
	interface Titik {
		t?: string;
		equity?: number | null;
	}
	interface Marker {
		t?: string;
		ticket?: string;
		symbol?: string;
		net_usd?: number | null;
	}
	interface Props {
		deret?: Titik[];
		markers?: Marker[];
		drawdown_pct?: number | null;
	}
	let { deret = [], markers = [], drawdown_pct = null }: Props = $props();

	const titik = $derived(
		deret.filter(
			(d): d is { t: string; equity: number } =>
				typeof d.equity === 'number' && Number.isFinite(d.equity)
		)
	);

	const W = 600;
	const H = 160;
	const PAD_X = 8;
	const PAD_Y = 16;

	const minY = $derived(
		titik.length ? Math.min(...titik.map((d) => d.equity)) : 0
	);
	const maxY = $derived(
		titik.length ? Math.max(...titik.map((d) => d.equity)) : 1
	);
	const rangeY = $derived(maxY - minY || 1);

	function x(i: number) {
		if (titik.length <= 1) return PAD_X;
		return PAD_X + (i / (titik.length - 1)) * (W - PAD_X * 2);
	}
	function y(v: number) {
		return PAD_Y + (H - PAD_Y * 2) - ((v - minY) / rangeY) * (H - PAD_Y * 2);
	}

	const path = $derived(
		titik.length < 2
			? ''
			: titik
					.map((d, i) => `${i === 0 ? 'M' : 'L'} ${x(i).toFixed(1)} ${y(d.equity).toFixed(1)}`)
					.join(' ')
	);
	const area = $derived(
		path
			? `${path} L ${x(titik.length - 1).toFixed(1)} ${H - PAD_Y} L ${x(0).toFixed(1)} ${H - PAD_Y} Z`
			: ''
	);
	const naik = $derived(
		titik.length >= 2 ? titik[titik.length - 1].equity >= titik[0].equity : true
	);
	const warna = $derived(naik ? 'var(--color-pos)' : 'var(--color-neg)');

	function ms(t?: string) {
		if (!t) return Number.NaN;
		let s = t.trim().replace(' ', 'T');
		if (!/([zZ]|[+-]\d{2}:?\d{2})$/.test(s)) s += 'Z';
		return Date.parse(s);
	}

	// Indeks titik terdekat untuk setiap marker; marker di luar jangkauan tetap
	// ditempel ke ujung terdekat supaya tidak hilang diam-diam.
	const penanda = $derived.by(() => {
		if (!titik.length) return [];
		return markers
			.map((m) => {
				const t = ms(m.t);
				let idx = 0;
				if (Number.isFinite(t)) {
					let jarak = Number.POSITIVE_INFINITY;
					for (let i = 0; i < titik.length; i += 1) {
						const d = Math.abs((ms(titik[i].t) || 0) - t);
						if (d < jarak) {
							jarak = d;
							idx = i;
						}
					}
				}
				return { ...m, idx };
			})
			.filter((m) => m.idx >= 0 && m.idx < titik.length);
	});

	function rp(v?: number | null) {
		if (v == null) return '—';
		return `${v >= 0 ? '+' : ''}$${v.toFixed(2)}`;
	}
</script>

<div class="mt-3" data-testid="kurva-ekuitas">
	{#if titik.length < 2}
		<p class="text-11 text-text-3">
			Butuh minimal 2 titik rekaman untuk menggambar kurva. Titik terkumpul dari
			telemetri MT5 tiap menit.
		</p>
	{:else}
		<svg viewBox="0 0 {W} {H}" class="w-full" role="img" aria-label="Kurva ekuitas dengan penanda trade">
			<path d={area} fill={warna} opacity="0.10" />
			<path d={path} fill="none" stroke={warna} stroke-width="1.6" stroke-linejoin="round" />
			{#each penanda as m, i (i)}
				<circle
					cx={x(m.idx)}
					cy={y(titik[m.idx].equity)}
					r="4"
					fill={m.net_usd != null && m.net_usd < 0 ? 'var(--color-neg)' : 'var(--color-pos)'}
					stroke="var(--color-surface)"
					stroke-width="1.5"
					data-testid="marker-trade"
				>
					<title>{`#${m.ticket ?? '?'} ${m.symbol ?? ''} ${rp(m.net_usd)} · ${m.t ?? ''}`}</title>
				</circle>
			{/each}
		</svg>
		<p class="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-10 text-text-3">
			<span>● trade tutup (hijau profit, merah rugi)</span>
			{#if drawdown_pct != null}
				<span>drawdown maks {drawdown_pct.toFixed(2)}%</span>
			{/if}
			<span>{penanda.length} penanda</span>
		</p>
		{#if penanda.length > 0}
			<div class="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-10 text-text-3">
				{#each penanda.slice(-5) as m, i (i)}
					<span class="font-mono">
						#{m.ticket ?? '?'} {m.symbol ?? ''}
						<span class:text-pos={m.net_usd != null && m.net_usd >= 0} class:text-neg={m.net_usd != null && m.net_usd < 0}>
							{rp(m.net_usd)}
						</span>
					</span>
				{/each}
			</div>
		{/if}
	{/if}
</div>
