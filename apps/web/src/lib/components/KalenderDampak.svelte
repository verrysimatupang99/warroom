<script lang="ts">
	/**
	 * Kalender ekonomi dengan DAMPAK & COUNTDOWN (7 Okt).
	 *
	 * Riset 7 Okt (StrikeGEX/TradingView): yang membuat dashboard terasa hidup adalah
	 * hitungan mundur ke event — bukan tabel statis. Jam hitung dipakai WIB; kalau waktu
	 * event tidak diketahui, ditulis "—" (tidak dikarang).
	 */
	interface Item {
		ts?: number;
		title?: string;
		impact?: string;
		mata_uang?: string;
		forecast?: string;
		previous?: string;
	}
	interface Props {
		macro?: { berikutnya?: Item[]; tersedia?: boolean; jumlah?: number } | null;
	}

	let { macro }: Props = $props();

	// Jam berdetak: hanya untuk countdown, tidak menyentuh angka fakta.
	let sekarang = $state(Date.now());
	$effect(() => {
		const t = setInterval(() => (sekarang = Date.now()), 1000);
		return () => clearInterval(t);
	});

	const daftar = $derived(
		(macro?.berikutnya ?? [])
			.filter((m) => typeof m.ts === 'number' && m.ts > sekarang / 1000 - 3600)
			.slice(0, 8)
	);

	function mundur(ts: number): string {
		const sisa = ts - Math.round(sekarang / 1000);
		if (sisa <= 0) return 'sudah lewat';
		const j = Math.floor(sisa / 3600);
		const m = Math.floor((sisa % 3600) / 60);
		const d = sisa % 60;
		return j > 0 ? `${j}j ${m}m` : `${m}m ${String(d).padStart(2, '0')}s`;
	}

	function jam(ts: number): string {
		return new Intl.DateTimeFormat('id-ID', {
			timeZone: 'Asia/Jakarta', day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', hour12: false
		}).format(new Date(ts * 1000));
	}

	const kelas = (impact: string | undefined) =>
		impact === 'High'
			? 'text-neg bg-neg/10 border-neg/20'
			: impact === 'Medium'
				? 'text-warn bg-warn/10 border-warn/20'
				: impact === 'Holiday'
					? 'text-accent bg-accent/10 border-accent/20'
					: 'text-text-3 bg-canvas border-line';
</script>

<div class="permukaan-2 rounded-card border border-line p-3">
	<div class="mb-3 flex items-center justify-between border-b border-line-soft pb-2">
		<div>
			<h3 class="text-14 font-medium text-text">Kalender Ekonomi — Dampak &amp; Hitung Mundur</h3>
			<p class="text-11 text-text-3">
				Event berdampak tinggi = zona bahaya: sinyal baru sebaiknya ditahan ±60 menit
			</p>
		</div>
		<span class="rounded bg-surface border border-line px-2 py-0.5 text-11 font-mono text-accent">
			{macro?.jumlah ?? 0} agenda
		</span>
	</div>
	{#if daftar.length === 0}
		<div class="py-3 text-center text-12 text-text-3">Tidak ada agenda terjadwal terdekat.</div>
	{:else}
		<div class="space-y-1.5">
			{#each daftar as m (String(m.ts) + (m.title ?? ''))}
				{#if typeof m.ts === 'number'}
					{@const sisa = m.ts - Math.round(sekarang / 1000)}
					<div class="flex flex-wrap items-center gap-2 rounded-card border border-line bg-surface p-2 text-12 {sisa > 0 && sisa < 3600 && m.impact === 'High' ? 'border-neg/40' : ''}">
						<span class="w-24 shrink-0 font-mono text-11 text-text-3">{jam(m.ts)}</span>
						<span class="min-w-0 flex-1 truncate text-text-2">{m.title ?? '—'}</span>
						<span class="rounded border px-1.5 py-0.5 text-10 font-bold {kelas(m.impact)}">{m.impact ?? '—'}</span>
						{#if m.mata_uang}<span class="font-mono text-10 text-text-3">{m.mata_uang}</span>{/if}
						<span class="w-20 shrink-0 text-right font-mono text-11 {sisa > 0 && sisa < 3600 && m.impact === 'High' ? 'text-neg font-bold' : 'text-text-3'}">
							{mundur(m.ts)}
						</span>
					</div>
				{/if}
			{/each}
		</div>
		{#if daftar.some((m) => typeof m.ts === 'number' && m.ts - sekarang / 1000 > 0 && m.ts - sekarang / 1000 < 3600 && m.impact === 'High')}
			<p class="mt-2 text-11 text-neg font-bold">⚠ Ada event dampak tinggi dalam 60 menit — tahan sinyal baru.</p>
		{/if}
	{/if}
</div>
