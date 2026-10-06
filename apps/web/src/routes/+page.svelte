<script lang="ts">
	// PRATINJAU arah baru (6 Okt 2026) — "Algentis gelap".
	//
	// Arah: algentis.xyz, tapi gelap (permintaan pemilik). Satu aksen MINT (#34E39A)
	// + merah + kuning. Font dipertahankan (Space Grotesk/Inter/JetBrains Mono).
	//
	// Tujuan 3 detik: "ada peluang atau tidak". Karena itu urutannya:
	//   1. Ticker pasar (denyut seluruh pasar, satu baris)
	//   2. SATU verdikt besar + alasan
	//   3. Baru rincian per pasar
	//
	// Ini halaman pratinjau: data nyata dari API, tidak ada yang dikarang.
	import { getArea, getPasarRingkas, getSinyalPerPasar } from '$lib/api/client';
	import type { AreaPayload, PasarRingkasPayload, SinyalPasar, SinyalPayload } from '$lib/api/types';
	import { umurDetik } from '$lib/format';

	let sinyal = $state<SinyalPayload | null>(null);
	let kripto = $state<AreaPayload | null>(null);
	let akurasi = $state<PasarRingkasPayload | null>(null);
	let galat = $state<string | null>(null);

	async function muat() {
		const [s, k, a] = await Promise.allSettled([getSinyalPerPasar(), getArea('crypto'), getPasarRingkas()]);
		if (s.status === 'fulfilled') { sinyal = s.value; galat = null; }
		else galat = s.reason instanceof Error ? s.reason.message : String(s.reason);
		if (k.status === 'fulfilled') kripto = k.value;
		if (a.status === 'fulfilled') akurasi = a.value;
	}
	$effect(() => {
		void muat();
		const t = setInterval(() => void muat(), 15000);
		return () => clearInterval(t);
	});

	const daftar = $derived(sinyal?.sinyal ?? []);

	// Ticker: dari bagian.crypto (pair + harga + chg24h) — angka nyata, bukan contoh.
	const ticker = $derived.by(() => {
		const bag = (kripto?.facts.find((f) => f.key === 'bagian')?.value ?? {}) as Record<string, unknown>;
		const rows = Array.isArray(bag.crypto) ? (bag.crypto as Record<string, unknown>[]) : [];
		return rows.slice(0, 8).map((r) => ({
			pair: String(r.pair ?? '—'),
			harga: typeof r.price === 'number' ? r.price : null,
			chg: typeof r.chg24h === 'number' ? r.chg24h : null
		}));
	});

	// Verdikt besar: berapa pasar punya peluang, dan berapa yang terverifikasi.
	const peluang = $derived(daftar.filter((r) => r.ada));
	const verdikt = $derived.by(() => {
		if (daftar.length === 0) return { judul: 'BELUM ADA DATA', nada: 'netral', alasan: 'Sumber belum mengirim sinyal.' };
		if (peluang.length === 0) return { judul: 'TIDAK ADA PELUANG', nada: 'diam', alasan: `Semua ${daftar.length} pasar ditolak gate. Menunggu lebih baik daripada memaksa.` };
		const teratas = [...peluang].sort((a, b) => (b.skor ?? -1) - (a.skor ?? -1))[0];
		return {
			judul: `${peluang.length} PELUANG`,
			nada: 'ada',
			alasan: `Teratas: ${teratas.label}${teratas.subjek ? ` · ${teratas.subjek}` : ''}${teratas.skor != null ? ` · skor ${teratas.skor}/100` : ''}. Semua belum terverifikasi — lihat catatan tiap pasar.`
		};
	});

	const formatHarga = (n: number | null) =>
		n == null ? '—' : n >= 1000 ? n.toLocaleString('en-US', { maximumFractionDigits: 0 }) : n >= 1 ? n.toFixed(2) : n.toPrecision(4);

	// SETUP ENTRY — ini yang menjawab "masuk di mana". Datanya SUDAH ada di
	// `detail` tiap pasar; sebelumnya tidak ditampilkan sehingga verdikt "ADA
	// PELUANG" tak memberi harga masuk. Angka ditampilkan apa adanya; yang tidak
	// ada tidak dikarang (mis. forex/idx yang belum punya sinyal).
	type Setup = { label: string; nilai: string; nada?: 'masuk' | 'stop' | 'target' | 'netral' };
	const setupDari = (s: SinyalPasar): Setup[] => {
		const d = (s.detail ?? {}) as Record<string, unknown>;
		const out: Setup[] = [];
		const num = (v: unknown) => (typeof v === 'number' ? v : null);
		const f = (v: number | null) => (v == null ? '—' : formatHarga(v));

		if (s.pasar === 'crypto') {
			const e = num(d.entry), sl = num(d.sl), tp = num(d.tp1);
			if (e != null) out.push({ label: 'Masuk', nilai: f(e), nada: 'masuk' });
			if (sl != null) out.push({ label: 'Stop', nilai: f(sl), nada: 'stop' });
			if (tp != null) out.push({ label: 'Target', nilai: f(tp), nada: 'target' });
			// jarak stop dalam % — dari angka, bukan taksiran
			if (e != null && sl != null) out.push({ label: 'Risiko', nilai: `${(Math.abs(e - sl) / e * 100).toFixed(2)}%` });
		} else if (s.pasar === 'polymarket') {
			const wr = num(d.winRate), be = num(d.breakEven_pct);
			if (wr != null) out.push({ label: 'Win-rate', nilai: `${wr.toFixed(2)}%` });
			if (be != null) out.push({ label: 'Break-even', nilai: `${be.toFixed(2)}%` });
			const n = num(d.n), need = num(d.nNeeded);
			if (n != null && need != null) out.push({ label: 'Sampel', nilai: `${n}/${need}` });
		} else if (s.pasar === 'gmgn') {
			const v = num(d.viable), p = num(d.pools);
			if (v != null && p != null) out.push({ label: 'Pool layak', nilai: `${v}/${p}` });
			const vl = num(d.avg_vl);
			if (vl != null) out.push({ label: 'V/L rata²', nilai: vl.toFixed(1) });
		} else if (s.pasar === 'lp') {
			const fee = num(d.fee_hari), umur = num(d.umur_hari);
			if (fee != null) out.push({ label: 'Fee/hari', nilai: `$${fee.toFixed(2)}` });
			if (umur != null) out.push({ label: 'Umur', nilai: `${umur.toFixed(1)} hr` });
		}
		return out;
	};
	const setupTeratas = $derived.by(() => {
		const ada = daftar.filter((r) => r.ada && r.pasar === 'crypto');
		const t = ada[0];
		return t ? setupDari(t) : [];
	});
	const subjekTeratas = $derived(daftar.find((r) => r.ada && r.pasar === 'crypto')?.subjek ?? null);
</script>

<svelte:head><title>War Room — satu layar, semua pasar</title></svelte:head>

<div class="pratinjau">
	<!-- 1. TICKER — denyut pasar dalam satu baris -->
	<div class="ticker" aria-label="Harga pasar">
		{#each ticker as t (t.pair)}
			<span class="tick">
				<span class="tick-pair">{t.pair.replace('USDT', '')}</span>
				<span class="tick-harga angka">{formatHarga(t.harga)}</span>
				{#if t.chg != null}
					<span class="tick-chg angka" class:naik={t.chg >= 0} class:turun={t.chg < 0}>
						{t.chg >= 0 ? '▲' : '▼'}{Math.abs(t.chg).toFixed(2)}%
					</span>
				{/if}
			</span>
		{/each}
		{#if ticker.length === 0}
			<span class="tick dim">ticker belum tersedia</span>
		{/if}
	</div>

	<div class="isi">
		<header class="kepala">
			<h1 class="merek">War<span>Room</span></h1>
			<span class="mode">PAPER</span>
			<span class="dim">multi-market · {daftar.length} pasar</span>
			<span class="spacer"></span>
			<span class="dim angka">{umurDetik(kripto?.facts?.[0]?.age_s ?? null)} lalu</span>
		</header>

		<!-- 2. VERDIKT BESAR — jawaban 3 detik -->
		<section class="verdikt {verdikt.nada}" aria-live="polite">
			<p class="verdikt-label">Status hari ini</p>
			<p class="verdikt-judul">{verdikt.judul}</p>
			<p class="verdikt-alasan">{verdikt.alasan}</p>

			<!-- SETUP ENTRY: jawaban "masuk di mana". Hanya bila datanya ada. -->
			{#if setupTeratas.length}
				<div class="setup" aria-label="Setup entry pasar teratas">
					<span class="setup-judul">
						Setup entry{subjekTeratas ? ` · ${subjekTeratas}` : ''}
					</span>
					<div class="setup-baris">
						{#each setupTeratas as st (st.label)}
							<div class="setup-item">
								<span class="setup-label">{st.label}</span>
								<span class="setup-nilai angka {st.nada ?? ''}">{st.nilai}</span>
							</div>
						{/each}
					</div>
				</div>
			{/if}
		</section>

		<!-- 2b. AKURASI & PnL per market (6 Okt): angka dari mesin pasar.py, satu standar bukti.
		     Sengaja TIDAK menjumlahkan R dan USD — satuannya beda; kolomnya dipisah. -->
		<section class="pasar" aria-label="Akurasi dan PnL per market">
			<div class="judul-bagian">
				<h2>Akurasi &amp; PnL per Market</h2>
				<p class="dim">Dari ledger nyata tiap market. Tingkat pakem: <span class="angka">INSUFFICIENT → DIRECTIONAL → PRELIMINARY → TUNING</span> (n efektif per hari).</p>
			</div>
			{#if akurasi}
				<div class="tabel-wrap">
					<table class="tabel-pasar angka">
						<thead>
							<tr>
								<th>Market</th><th>Setup terbesar</th><th class="ka">n</th><th class="ka">Hari</th>
								<th class="ka">WR</th><th class="ka">Mean R</th><th class="ka">P&amp;L</th><th>Pakem</th>
							</tr>
						</thead>
						<tbody>
							{#each Object.values(akurasi.pasar) as r (r.pasar)}
								<tr class:kosong={!r.tersedia}>
									<td class="nama-pasar">{r.label ?? r.pasar}</td>
									<td class="dim">{r.setup ?? '—'} <span class="dim">({r.jumlah_setup} setup)</span></td>
									<td class="ka">{r.n ?? '—'}</td>
									<td class="ka">{r.n_hari ?? '—'}</td>
									<td class="ka">{r.winrate_pct != null ? `${r.winrate_pct}%` : '—'}</td>
									<td class="ka {r.mean_r != null && r.mean_r > 0 ? 'pos' : r.mean_r != null && r.mean_r < 0 ? 'neg' : ''}">
										{r.mean_r != null ? `${r.mean_r > 0 ? '+' : ''}${r.mean_r}` : '—'}
									</td>
									<td class="ka">
										{#if r.total_r != null}<span class={r.total_r > 0 ? 'pos' : r.total_r < 0 ? 'neg' : ''}>{r.total_r > 0 ? '+' : ''}{r.total_r} R</span>{/if}
										{#if r.pnl_usd != null}<span class={r.pnl_usd > 0 ? 'pos' : r.pnl_usd < 0 ? 'neg' : ''}>{r.pnl_usd > 0 ? '+' : ''}{r.pnl_usd} USD</span>{/if}
										{#if r.total_r == null && r.pnl_usd == null}—{/if}
									</td>
									<td>
										<span class="pakem pakem-{r.tingkat ?? 'INSUFFICIENT'}">{r.tingkat ?? '—'}</span>
									</td>
								</tr>
								{#if !r.tersedia && r.alasan}
									<tr class="kosong"><td colspan="8" class="dim catatan-alasan">{r.alasan}</td></tr>
								{/if}
							{/each}
						</tbody>
					</table>
				</div>
				{#if akurasi.standar}<p class="dim kaki-tabel">{akurasi.standar}</p>{/if}
			{:else}
				<p class="dim">Ringkasan akurasi belum tersedia.</p>
			{/if}
		</section>

		<!-- 3. RINCIAN per pasar -->
		<section class="pasar" aria-label="Rincian per pasar">
			{#each daftar as s (s.pasar)}
				<article class="baris" class:kosong={!s.ada}>
					<div class="baris-kiri">
						<span class="nama">{s.label}</span>
						{#if s.subjek}<span class="subjek angka">{s.subjek}</span>{/if}
					</div>
					<div class="baris-kanan">
						{#if s.skor != null}
							<span class="skor angka">{s.skor}<span class="dari">/100</span></span>
						{:else}
							<span class="skor angka kosong">—</span>
						{/if}
						<span class="tanda" class:ada={s.ada} class:belum={!s.ada}>
							{s.ada ? (s.arah ?? 'ADA') : 'TIDAK ADA'}
						</span>
					</div>
					{#if s.catatan_kejujuran}
						<p class="catatan">{s.catatan_kejujuran}</p>
					{/if}
					{#if setupDari(s).length}
						<p class="setup-mini">
							{#each setupDari(s) as st, i (st.label)}
								{#if i > 0}<span class="pisah">·</span>{/if}<span class="setup-mini-label">{st.label}</span>
								<span class="angka setup-mini-nilai {st.nada ?? ''}">{st.nilai}</span>
							{/each}
						</p>
					{/if}
				</article>
			{/each}
			{#if daftar.length === 0}
				<p class="dim">Belum ada pasar yang bisa ditampilkan{galat ? `: ${galat}` : '.'}</p>
			{/if}
		</section>

		<p class="kaki dim">
			Pratinjau arah baru. Warna aksen tunggal (mint), ticker di atas, verdikt besar,
			rincian di bawah. Bandingkan dengan versi sekarang lalu bilang mana yang lebih tepat.
		</p>
	</div>
</div>

<style>
	/* Arah ini SUDAH dipromosikan: nilainya kini token global di app.css
	   (lapis primitive --p-mint-400 dst), jadi tidak ada nilai mentah di sini. */
	.pratinjau {
		--mint: var(--color-accent);
		--kuning: var(--color-warn);
		--merah: var(--color-neg);
		--latar: var(--color-bg);
		--permukaan: var(--color-surface);
		--garis: var(--color-line);
		--tinta: var(--color-text);
		--redup: var(--color-text-3);
	}

	.judul-bagian { margin: 0.5rem 0 0.75rem; }
	.judul-bagian h2 { font-size: 1.05rem; margin: 0 0 0.15rem; letter-spacing: 0.01em; }
	.tabel-wrap { overflow-x: auto; border: 1px solid var(--garis); border-radius: 0.75rem; background: var(--permukaan); }
	.tabel-pasar { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
	.tabel-pasar th { text-align: left; font-weight: 500; color: var(--redup); padding: 0.6rem 0.75rem; border-bottom: 1px solid var(--garis); white-space: nowrap; }
	.tabel-pasar td { padding: 0.55rem 0.75rem; border-bottom: 1px solid var(--garis); vertical-align: top; }
	.tabel-pasar tr:last-child td { border-bottom: none; }
	.tabel-pasar .ka { text-align: right; }
	.tabel-pasar .nama-pasar { text-transform: capitalize; font-weight: 600; }
	.tabel-pasar tr.kosong { opacity: 0.75; }
	.catatan-alasan { font-size: 0.75rem; padding-top: 0 !important; }
	.kaki-tabel { margin-top: 0.5rem; font-size: 0.72rem; }
	.pakem { display: inline-block; padding: 0.1rem 0.45rem; border-radius: 0.45rem; border: 1px solid var(--garis); font-size: 0.68rem; font-weight: 700; letter-spacing: 0.02em; }
	.pakem-INSUFFICIENT { color: var(--merah); border-color: var(--merah); }
	.pakem-DIRECTIONAL { color: var(--kuning); border-color: var(--kuning); }
	.pakem-PRELIMINARY { color: var(--mint); border-color: var(--mint); }
	.pakem-TUNING { color: var(--tinta); border-color: var(--tinta); }
	.pos { color: var(--mint); }
	.neg { color: var(--merah); }

	.ticker {
		display: flex;
		gap: 1.25rem;
		align-items: center;
		padding: 0.5rem 1rem;
		border-bottom: 1px solid var(--garis);
		background: var(--permukaan);
		overflow-x: auto;
		white-space: nowrap;
	}
	.tick {
		display: inline-flex;
		align-items: baseline;
		gap: 0.4rem;
		font-size: 0.75rem;
	}
	.tick-pair {
		color: var(--redup);
		font-weight: 600;
		letter-spacing: 0.04em;
	}
	.tick-harga {
		color: var(--tinta);
		font-weight: 600;
	}
	.tick-chg {
		font-weight: 600;
	}
	.tick-chg.naik {
		color: var(--mint);
	}
	.tick-chg.turun {
		color: var(--merah);
	}

	.isi {
		max-width: 62rem;
		margin: 0 auto;
		padding: 1.5rem 1rem 3rem;
		display: flex;
		flex-direction: column;
		gap: 1.25rem;
	}

	.kepala {
		display: flex;
		align-items: baseline;
		gap: 0.75rem;
		flex-wrap: wrap;
	}
	.merek {
		font-family: var(--font-display);
		font-size: 1.5rem;
		font-weight: 700;
		letter-spacing: -0.02em;
		margin: 0;
	}
	.merek span {
		color: var(--mint);
	}
	.mode {
		font-size: 0.7rem;
		font-weight: 700;
		letter-spacing: 0.1em;
		padding: 0.15rem 0.5rem;
		border: 1px solid var(--mint);
		color: var(--mint);
		border-radius: 999px;
	}
	.spacer {
		flex: 1;
	}

	/* Verdikt: satu blok besar, ini jawaban 3 detik. */
	.verdikt {
		border: 1px solid var(--garis);
		border-radius: 14px;
		padding: 1.5rem 1.5rem 1.35rem;
		background: var(--permukaan);
	}
	.verdikt.ada {
		border-color: color-mix(in srgb, var(--mint) 45%, var(--garis));
		background: linear-gradient(180deg, color-mix(in srgb, var(--mint) 8%, var(--permukaan)), var(--permukaan));
	}
	.verdikt.diam {
		border-color: var(--garis);
	}
	.verdikt-label {
		font-size: 0.7rem;
		font-weight: 700;
		letter-spacing: 0.14em;
		text-transform: uppercase;
		color: var(--redup);
		margin: 0 0 0.35rem;
	}
	.verdikt-judul {
		font-family: var(--font-display);
		font-size: clamp(2rem, 6vw, 3.25rem);
		font-weight: 700;
		letter-spacing: -0.03em;
		line-height: 1;
		margin: 0;
	}
	.verdikt.ada .verdikt-judul {
		color: var(--mint);
	}
	.verdikt-alasan {
		margin: 0.75rem 0 0;
		font-size: 0.9rem;
		color: var(--tinta);
		opacity: 0.85;
		max-width: 46rem;
	}

	.pasar {
		display: flex;
		flex-direction: column;
		border: 1px solid var(--garis);
		border-radius: 14px;
		overflow: hidden;
		background: var(--permukaan);
	}
	.baris {
		display: grid;
		grid-template-columns: 1fr auto;
		gap: 0.25rem 1rem;
		padding: 0.85rem 1.1rem;
		border-bottom: 1px solid var(--garis);
	}
	.baris:last-child {
		border-bottom: 0;
	}
	.baris.kosong {
		background: color-mix(in srgb, var(--latar) 55%, var(--permukaan));
	}
	.baris-kiri {
		display: flex;
		align-items: baseline;
		gap: 0.6rem;
		min-width: 0;
	}
	.nama {
		font-weight: 600;
	}
	.subjek {
		font-size: 0.8rem;
		color: var(--redup);
	}
	.baris-kanan {
		display: flex;
		align-items: baseline;
		gap: 0.75rem;
	}
	.skor {
		font-size: 1.35rem;
		font-weight: 700;
	}
	.skor.kosong {
		color: var(--redup);
	}
	.dari {
		font-size: 0.7rem;
		font-weight: 400;
		color: var(--redup);
	}
	.tanda {
		font-size: 0.68rem;
		font-weight: 700;
		letter-spacing: 0.08em;
		padding: 0.15rem 0.5rem;
		border-radius: 999px;
		border: 1px solid;
		white-space: nowrap;
	}
	.tanda.ada {
		color: var(--mint);
		border-color: color-mix(in srgb, var(--mint) 45%, transparent);
		background: color-mix(in srgb, var(--mint) 10%, transparent);
	}
	.tanda.belum {
		color: var(--redup);
		border-color: var(--garis);
	}
	.catatan {
		grid-column: 1 / -1;
		margin: 0.35rem 0 0;
		font-size: 0.78rem;
		color: var(--redup);
		line-height: 1.45;
	}
	.kaki {
		font-size: 0.78rem;
		line-height: 1.5;
		margin: 0;
	}

	/* Setup entry — blok "masuk di mana" di dalam verdikt. */
	.setup {
		margin-top: 1.1rem;
		padding-top: 1rem;
		border-top: 1px solid var(--garis);
	}
	.setup-judul {
		display: block;
		font-size: 0.7rem;
		font-weight: 700;
		letter-spacing: 0.12em;
		text-transform: uppercase;
		color: var(--redup);
		margin-bottom: 0.6rem;
	}
	.setup-baris {
		display: flex;
		flex-wrap: wrap;
		gap: 1.75rem;
	}
	.setup-item {
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
	}
	.setup-label {
		font-size: 0.68rem;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--redup);
	}
	.setup-nilai {
		font-size: 1.15rem;
		font-weight: 700;
	}
	.setup-nilai.masuk {
		color: var(--mint);
	}
	.setup-nilai.stop {
		color: var(--merah);
	}
	.setup-nilai.target {
		color: var(--kuning);
	}

	/* Setup ringkas di tiap baris pasar. */
	.setup-mini {
		grid-column: 1 / -1;
		margin: 0.45rem 0 0;
		font-size: 0.78rem;
		color: var(--redup);
		display: flex;
		flex-wrap: wrap;
		gap: 0.3rem;
		align-items: baseline;
	}
	.setup-mini-label {
		margin-right: 0.25rem;
	}
	.pisah {
		margin: 0 0.35rem;
		opacity: 0.5;
	}
	.setup-mini-nilai {
		color: var(--tinta);
		font-weight: 600;
	}
	.setup-mini-nilai.masuk {
		color: var(--mint);
	}
	.setup-mini-nilai.stop {
		color: var(--merah);
	}
	.setup-mini-nilai.target {
		color: var(--kuning);
	}
	.dim {
		color: var(--redup);
	}
	.angka {
		font-family: var(--font-mono);
		font-variant-numeric: tabular-nums;
	}
</style>
