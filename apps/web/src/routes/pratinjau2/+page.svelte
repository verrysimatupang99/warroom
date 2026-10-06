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
	import { getArea, getSinyalPerPasar } from '$lib/api/client';
	import type { AreaPayload, SinyalPasar, SinyalPayload } from '$lib/api/types';
	import { umurDetik } from '$lib/format';

	let sinyal = $state<SinyalPayload | null>(null);
	let kripto = $state<AreaPayload | null>(null);
	let galat = $state<string | null>(null);

	async function muat() {
		const [s, k] = await Promise.allSettled([getSinyalPerPasar(), getArea('crypto')]);
		if (s.status === 'fulfilled') { sinyal = s.value; galat = null; }
		else galat = s.reason instanceof Error ? s.reason.message : String(s.reason);
		if (k.status === 'fulfilled') kripto = k.value;
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
</script>

<svelte:head><title>Pratinjau — War Room</title></svelte:head>

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
	/* lint-tokens-disable — palet PRATINJAU ini sengaja nilai mentah: ia belum
	   disetujui, jadi tidak boleh masuk token global. Aksen mint dari algentis
	   (#34E39A), versi gelap. Bila arah ini dipilih, nilainya dipindah ke lapis
	   primitive app.css dan penanda ini dihapus. */
	.pratinjau {
		--mint: #34e39a;
		--kuning: #f5b83d;
		--merah: #ff6b6b;
		--latar: #0a0c0b;
		--permukaan: #111514;
		--garis: #262c29;
		--tinta: #f2f0e9;
		--redup: #8c918d;
		min-height: 100vh;
		background: var(--latar);
		color: var(--tinta);
	}

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
	/* lint-tokens-enable */
	.dim {
		color: var(--redup);
	}
	.angka {
		font-family: var(--font-mono);
		font-variant-numeric: tabular-nums;
	}
</style>
