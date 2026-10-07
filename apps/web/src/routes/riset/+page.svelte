<script lang="ts">
	// Riset — arsitektur mengikuti algentis (/performance, /calendar, /tools),
	// isi kita sendiri. Tiga tab, URL = sumber kebenaran:
	//   kinerja  : statistik + trade terakhir + PnL per pair (ledger nyata)
	//   kalender : agenda makro (bagian.macro, 82 event nyata)
	//   alat     : kalkulator position size / likuidasi / risk-reward (murni hitung)
	//
	// ATURAN YANG DIPEGANG: angka hanya dari fakta; yang tidak ada ditulis "—",
	// bukan 0. Kalkulator menandai asumsinya terang-terangan (fee, leverage).
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { getArea, getPasarRingkas } from '$lib/api/client';
	import type { AreaPayload, Fakta, PasarRingkasPayload } from '$lib/api/types';
	import { AREAS } from '$lib/nav';
	import { umurDetik, angka, waktuWIB } from '$lib/format';
	import SubNav from '$lib/components/SubNav.svelte';
	import Skeleton from '$lib/components/Skeleton.svelte';
	import ErrorState from '$lib/components/ErrorState.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import DompetLintasMarket from '$lib/components/DompetLintasMarket.svelte';
	import KinerjaBukti from '$lib/components/KinerjaBukti.svelte';

	const area = AREAS.find((a) => a.kunci === 'riset')!;
	// Data untuk sub "Bukti" (audit QA putaran 3): payload pasar/ringkas + umur fakta.
	let pasarRingkas = $state<PasarRingkasPayload | null>(null);
	async function muatBukti() {
		try {
			pasarRingkas = await getPasarRingkas();
		} catch {
			/* halaman induk sudah punya penanganan galat sendiri */
		}
	}
	$effect(() => {
		void muatBukti();
	});
	const sub = $derived.by(() => {
		const s = page.url.searchParams.get('sub');
		if (s && area.anak.some((a) => a.slug === s)) return s;
		return area.anak[0].slug;
	});
	function pilihSub(s: string) {
		if (typeof window !== 'undefined') void goto(`?sub=${s}`, { keepFocus: true, noScroll: true });
	}

	let kripto = $state<AreaPayload | null>(null);
	let forex = $state<AreaPayload | null>(null);
	let galat = $state<string | null>(null);
	let memuat = $state(true);

	async function muat() {
		const [k, f] = await Promise.allSettled([getArea('crypto'), getArea('forex')]);
		if (k.status === 'fulfilled') { kripto = k.value; galat = null; }
		else galat = k.reason instanceof Error ? k.reason.message : String(k.reason);
		if (f.status === 'fulfilled') forex = f.value;
		memuat = false;
	}
	$effect(() => {
		void muat();
		const t = setInterval(() => void muat(), 15000);
		return () => clearInterval(t);
	});

	const fakta = (p: AreaPayload | null, key: string) =>
		p?.facts.find((f) => f.key === key) ?? null;

	// Dompet lintas-market: fakta yang sama dengan tiap halaman area (satu sumber angka).
	const dompetObj = $derived(
		(fakta(kripto, 'dompet')?.value as { pasar?: Record<string, never>; kurs_usd_idr?: number } | undefined) ?? null
	);

	// ---- Kinerja ----
	type Stats = Record<string, number | null>;
	const stats = $derived((fakta(kripto, 'equity')?.value as { stats?: Stats } | undefined)?.stats ?? null);
	const equityPts = $derived(
		(fakta(kripto, 'equity')?.value as { points?: { i: number; r: number; cum?: number; pair?: string }[] } | undefined)?.points ?? []
	);
	const ledger = $derived(
		(fakta(kripto, 'ledger')?.value as { trade?: number; terakhir?: Record<string, unknown>[] } | undefined) ?? null
	);
	const trades = $derived((ledger?.terakhir ?? []) as Record<string, unknown>[]);

	// PnL per pair: dari titik equity (pair + r). Agregat R per pair, urut terbesar.
	const perPair = $derived.by(() => {
		const m = new Map<string, { n: number; r: number }>();
		for (const p of equityPts) {
			const pair = String(p.pair ?? '').trim();
			if (!pair || typeof p.r !== 'number') continue;
			const cur = m.get(pair) ?? { n: 0, r: 0 };
			cur.n += 1;
			cur.r += p.r;
			m.set(pair, cur);
		}
		return [...m.entries()]
			.map(([pair, v]) => ({ pair, n: v.n, r: v.r }))
			.sort((a, b) => b.r - a.r);
	});

	// ---- Kalender ----
	const macro = $derived(
		(fakta(forex, 'bagian')?.value as { macro?: { tersedia?: boolean; berikutnya?: Record<string, unknown>[]; jumlah?: number } } | undefined)?.macro ?? null
	);
	const events = $derived((macro?.berikutnya ?? []) as Record<string, unknown>[]);
	const dampakKelas = (im: unknown) => {
		const s = String(im ?? '').toLowerCase();
		if (s.includes('high')) return 'tinggi';
		if (s.includes('med')) return 'sedang';
		return 'rendah';
	};

	// ---- Alat (kalkulator) ----
	let modal = $state(1000);
	let risikoPct = $state(1);
	let entry = $state(100);
	let stop = $state(98);
	let leverage = $state(10);
	let feeBps = $state(10);

	const rr = $derived.by(() => {
		if (!entry || !stop || entry === stop) return null;
		const jarak = Math.abs(entry - stop) / entry;
		const sizeUsd = (modal * (risikoPct / 100)) / jarak;
		const margin = leverage > 0 ? sizeUsd / leverage : null;
		// likuidasi kasar (isolated, tanpa pemeliharaan): entry ∓ entry/leverage
		const liq = entry > stop ? entry * (1 - 1 / leverage) : entry * (1 + 1 / leverage);
		const feeUsd = sizeUsd * (feeBps / 10000) * 2; // buka + tutup
		return { jarakPct: jarak * 100, sizeUsd, margin, liq, feeUsd, risikoUsd: modal * (risikoPct / 100) };
	});
</script>

<svelte:head><title>Riset — War Room</title></svelte:head>

<div class="riset">
	<header class="kepala">
		<h1>Riset</h1>
		<p class="dim">Bukti dari ledger, agenda makro, dan kalkulator. Semua angka dari data nyata.</p>
	</header>

	<SubNav {area} aktif={sub} onpilih={pilihSub} />

	{#if galat && !kripto}
		<ErrorState pesan={galat} onulang={muat} />
	{:else if memuat && !kripto}
		<Skeleton baris={6} />
	{:else if sub === 'kinerja'}
		<!-- ============ KINERJA (padanan /performance algentis) ============ -->
		<!-- Satu-satunya tempat market dibandingkan: dompet Rp 10 juta, risiko sama. -->
		<DompetLintasMarket dompet={dompetObj} />
		{#if stats}
			<section class="stat-grid" aria-label="Statistik">
				<div class="stat"><span class="label">Total R</span><b class="angka {stats.total_r && stats.total_r >= 0 ? 'pos' : 'neg'}">{stats.total_r != null ? `${stats.total_r > 0 ? '+' : ''}${angka(stats.total_r)}` : '—'}</b></div>
				<div class="stat"><span class="label">Win-rate</span><b class="angka">{stats.winrate_pct != null ? `${angka(stats.winrate_pct)}%` : '—'}</b></div>
				<div class="stat"><span class="label">Trade</span><b class="angka">{stats.trades ?? '—'}</b></div>
				<div class="stat"><span class="label">Expectancy</span><b class="angka">{stats.expectancy_r != null ? `${angka(stats.expectancy_r)} R` : '—'}</b></div>
				<div class="stat"><span class="label">Max DD</span><b class="angka">{stats.max_drawdown_r != null ? `${angka(stats.max_drawdown_r)} R` : '—'}</b></div>
			</section>
		{:else}
			<EmptyState judul="Belum ada statistik" pesan="Fakta equity belum tersedia." />
		{/if}

		<section class="kartu" aria-label="Trade terakhir">
			<h2 class="judul">Trade terakhir <span class="dim">terbaru dulu</span></h2>
			{#if trades.length}
				<div class="gulir">
				<table class="tabel">
					<thead><tr><th>Pair</th><th>Arah</th><th>Status</th><th class="kanan">R</th><th class="kanan">Ditutup</th></tr></thead>
					<tbody>
						{#each trades as t (String(t.signal_id ?? t.pair) + String(t.closed_at))}
							<tr>
								<td class="angka kuat">{t.pair}</td>
								<td class="dim">{t.direction ?? '—'}</td>
								<td class="dim">{t.status ?? '—'}</td>
								<td class="angka kanan {typeof t.r === 'number' && t.r >= 0 ? 'pos' : 'neg'}">
									{typeof t.r === 'number' ? `${t.r > 0 ? '+' : ''}${angka(t.r)}` : '—'}
								</td>
								<td class="angka kanan dim">{t.closed_at ? waktuWIB(String(t.closed_at)) : '—'}</td>
							</tr>
						{/each}
					</tbody>
				</table>
				</div>
			{:else}
				<EmptyState judul="Belum ada trade" pesan="Ledger belum mencatat posisi tertutup." ringkas />
			{/if}
		</section>

		<section class="kartu" aria-label="PnL per pair">
			<h2 class="judul">PnL per pair <span class="dim">net R</span></h2>
			{#if perPair.length}
				<ul class="pair-list">
					{#each perPair as p (p.pair)}
						<li>
							<span class="angka kuat">{p.pair}</span>
							<span class="dim angka">{p.n} trade</span>
							<span class="bar"><span class="bar-isi {p.r >= 0 ? 'pos' : 'neg'}" style="width:{Math.min(100, Math.abs(p.r) / Math.max(...perPair.map((x) => Math.abs(x.r)), 1) * 100)}%"></span></span>
							<span class="angka kanan {p.r >= 0 ? 'pos' : 'neg'}">{p.r > 0 ? '+' : ''}{angka(p.r)} R</span>
						</li>
					{/each}
				</ul>
			{:else}
				<EmptyState judul="Belum ada pasangan" pesan="Titik equity belum memuat nama pair." ringkas />
			{/if}
		</section>
	{:else if sub === 'bukti'}
		<!-- ============ BUKTI (audit QA putaran 3) ============ -->
		<!-- Tujuh jawaban berdampingan untuk semua pasar: trade tuntas, WR, total R, PnL,
		     drawdown, biaya, periode + denominator. -->
		<KinerjaBukti akurasi={pasarRingkas} />
	{:else if sub === 'kalender'}
		<!-- ============ KALENDER (padanan /calendar algentis) ============ -->
		<section class="kartu" aria-label="Agenda makro">
			<h2 class="judul">
				Agenda makro
				<span class="dim">{macro?.jumlah != null ? `${macro.jumlah} event` : '—'}{forex ? ` · umur ${umurDetik(fakta(forex, 'bagian')?.age_s ?? null)}` : ''}</span>
			</h2>
			{#if events.length}
				<div class="gulir">
				<table class="tabel">
					<thead><tr><th>Waktu (WIB)</th><th>Peristiwa</th><th>Dampak</th><th class="kanan">Forecast</th><th class="kanan">Sebelumnya</th></tr></thead>
					<tbody>
						{#each events as e, i (String(e.ts) + i)}
							<tr>
								<td class="angka dim">{typeof e.ts === 'number' ? waktuWIB(new Date((e.ts as number) * 1000).toISOString()) : '—'}</td>
								<td>{e.title ?? '—'} <span class="dim">{e.mata_uang ?? ''}</span></td>
								<td><span class="pill {dampakKelas(e.impact)}">{e.impact ?? '—'}</span></td>
								<td class="angka kanan dim">{e.forecast || '—'}</td>
								<td class="angka kanan dim">{e.previous || '—'}</td>
							</tr>
						{/each}
					</tbody>
				</table>
				</div>
			{:else}
				<EmptyState
					judul="Agenda kosong"
					pesan={macro?.tersedia === false ? 'Sumber kalender belum tersedia.' : 'Tidak ada event terjadwal pada jendela ini.'}
					ringkas
				/>
			{/if}
		</section>
	{:else}
		<!-- ============ ALAT (padanan /tools algentis) ============ -->
		<section class="kartu" aria-label="Kalkulator risiko">
			<h2 class="judul">Position size &amp; risiko <span class="dim">murni hitungan</span></h2>
			<div class="form">
				<label>Modal (USD)<input type="number" bind:value={modal} min="0" step="10" /></label>
				<label>Risiko per trade (%)<input type="number" bind:value={risikoPct} min="0" max="100" step="0.1" /></label>
				<label>Entry<input type="number" bind:value={entry} min="0" step="0.01" /></label>
				<label>Stop<input type="number" bind:value={stop} min="0" step="0.01" /></label>
				<label>Leverage (x)<input type="number" bind:value={leverage} min="1" step="1" /></label>
				<label>Fee (bps/sisi)<input type="number" bind:value={feeBps} min="0" step="1" /></label>
			</div>
			{#if rr}
				<div class="hasil">
					<div class="h"><span class="label">Jarak stop</span><b class="angka">{rr.jarakPct.toFixed(2)}%</b></div>
					<div class="h"><span class="label">Ukuran posisi</span><b class="angka">${angka(rr.sizeUsd)}</b></div>
					<div class="h"><span class="label">Margin dibutuhkan</span><b class="angka">{rr.margin != null ? `$${angka(rr.margin)}` : '—'}</b></div>
					<div class="h"><span class="label">Harga likuidasi (perkiraan)</span><b class="angka warn">{angka(rr.liq)}</b></div>
					<div class="h"><span class="label">Risiko bila stop kena</span><b class="angka neg">-${angka(rr.risikoUsd)}</b></div>
					<div class="h"><span class="label">Fee total (buka+tutup)</span><b class="angka dim">${angka(rr.feeUsd)}</b></div>
				</div>
				<p class="catatan">
					Likuidasi dihitung kasar (isolated, tanpa margin pemeliharaan) — anggap perkiraan,
					bukan angka bursa. Fee memakai bps yang kamu isi, bukan asumsi kami.
				</p>
			{:else}
				<p class="dim">Isi entry dan stop yang berbeda untuk menghitung.</p>
			{/if}
		</section>
	{/if}
</div>

<style>
	.riset {
		display: flex;
		flex-direction: column;
		gap: var(--grid-gap);
	}
	.kepala h1 {
		margin: 0;
		font-family: var(--font-display);
		font-size: var(--text-26);
		font-weight: 700;
		letter-spacing: -0.02em;
	}
	.kepala p {
		margin: 0.15rem 0 0;
		font-size: var(--text-13);
	}
	.kartu {
		background: var(--color-surface);
		border: 1px solid var(--color-line);
		border-radius: var(--radius-card);
		padding: var(--card-pad);
	}
	.judul {
		margin: 0 0 0.6rem;
		font-size: var(--text-14);
		font-weight: 700;
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		gap: 0.6rem;
	}
	.stat-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(7rem, 1fr));
		gap: var(--grid-gap);
	}
	.stat {
		background: var(--color-surface);
		border: 1px solid var(--color-line);
		border-radius: var(--radius-card);
		padding: 0.6rem 0.75rem;
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
	}
	.label {
		font-size: var(--text-11);
		color: var(--color-text-3);
		text-transform: uppercase;
		letter-spacing: 0.06em;
	}
	.stat b {
		font-size: var(--text-20);
	}
	/* Tabel lebar menggulir DI DALAM bingkainya, tidak melebarkan halaman
	   (panduan ux). min-width menjaga kolom tetap terbaca saat digulir. */
	.gulir {
		overflow-x: auto;
	}
	.tabel {
		min-width: 34rem;
		width: 100%;
		border-collapse: collapse;
		font-size: var(--text-13);
	}
	.tabel th {
		text-align: left;
		font-size: var(--text-11);
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--color-text-3);
		padding: 0.35rem 0.4rem;
		border-bottom: 1px solid var(--color-line);
	}
	.tabel td {
		padding: 0.4rem;
		border-bottom: 1px solid var(--color-line-soft);
	}
	.tabel tr:last-child td {
		border-bottom: 0;
	}
	.kanan {
		text-align: right;
	}
	.kuat {
		font-weight: 600;
		color: var(--color-text);
	}
	.pair-list {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
	}
	.pair-list li {
		display: grid;
		grid-template-columns: 5.5rem 4.5rem 1fr 5rem;
		align-items: center;
		gap: 0.5rem;
		font-size: var(--text-13);
	}
	.bar {
		height: 6px;
		background: var(--color-surface-3);
		border-radius: 999px;
		overflow: hidden;
	}
	.bar-isi {
		display: block;
		height: 100%;
		border-radius: 999px;
	}
	.bar-isi.pos {
		background: var(--color-pos);
	}
	.bar-isi.neg {
		background: var(--color-neg);
	}
	.pill {
		font-size: var(--text-10);
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		padding: 0.1rem 0.45rem;
		border-radius: 999px;
		border: 1px solid;
	}
	.pill.tinggi {
		color: var(--color-neg);
		border-color: color-mix(in srgb, var(--color-neg) 45%, transparent);
	}
	.pill.sedang {
		color: var(--color-warn);
		border-color: color-mix(in srgb, var(--color-warn) 45%, transparent);
	}
	.pill.rendah {
		color: var(--color-text-3);
		border-color: var(--color-line);
	}
	.form {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(9rem, 1fr));
		gap: 0.6rem;
		margin-bottom: 0.85rem;
	}
	.form label {
		display: flex;
		flex-direction: column;
		gap: 0.2rem;
		font-size: var(--text-11);
		color: var(--color-text-3);
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}
	.form input {
		background: var(--color-surface-2);
		border: 1px solid var(--color-line);
		border-radius: var(--radius-control);
		padding: 0.35rem 0.5rem;
		color: var(--color-text);
		font-family: var(--font-mono);
		font-size: var(--text-13);
		min-height: 36px;
	}
	.hasil {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(11rem, 1fr));
		gap: 0.5rem;
	}
	.h {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		gap: 0.5rem;
		padding: 0.4rem 0.6rem;
		background: var(--color-surface-2);
		border: 1px solid var(--color-line-soft);
		border-radius: var(--radius-control);
	}
	.h b {
		font-size: var(--text-14);
	}
	.catatan {
		margin: 0.75rem 0 0;
		font-size: var(--text-12);
		color: var(--color-text-3);
		line-height: 1.5;
	}
	.dim {
		color: var(--color-text-3);
		font-weight: 400;
	}
	.pos {
		color: var(--color-pos);
	}
	.neg {
		color: var(--color-neg);
	}
	.warn {
		color: var(--color-warn);
	}
	.angka {
		font-family: var(--font-mono);
		font-variant-numeric: tabular-nums;
	}
</style>
