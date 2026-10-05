<script lang="ts">
	// KolomPasar — satu kolom penuh untuk satu pasar (adaptasi BeeColumn beebots).
	//
	// Bentuknya mengikuti BeeColumn: kepala (identitas + peringkat), nilai besar,
	// papan status, kotak sinyal, bar proporsi, meter, dan baris biaya. Yang
	// berbeda hanya ISI-nya, karena tiap pasar punya bentuk data sendiri:
	//
	//   beebots                  ->  di sini
	//   portrait + nama bee      ->  nama pasar + gaya (SMC/bandarmologi/BSJP)
	//   equity bee               ->  skor pasar (atau "—" bila tidak ada sinyal)
	//   cap-banner (BENCHED)     ->  catatan kejujuran (belum terverifikasi)
	//   posisi ▲ LONG BTC        ->  arah + subjek sinyal
	//   entry->mark->stop        ->  metrik pasar (Entry/SL/TP1, win-rate, dll)
	//   grafik ekuitas           ->  bar proporsi (skor, pool layak, win-rate)
	//   meter trades/fee         ->  meter besaran yang punya maksimum
	//   fees|funding|Jev|calls   ->  biaya | sampel | verifikasi | umur
	//
	// ATURAN YANG TIDAK BOLEH HILANG saat memindahkan bentuk:
	// 1. Skor kosong tampil "—", BUKAN 0.
	// 2. Selama `terverifikasi` false, catatan kejujuran WAJIB tampil — di sini ia
	//    mendapat tempat sebesar papan status, bukan catatan kaki kecil.
	import type { SinyalPasar } from '$lib/api/types';
	import { umurDetik } from '$lib/format';
	import Bar from './Bar.svelte';

	interface Props {
		s: SinyalPasar | null;
		/** Indeks tampilan (1-based) untuk penanda peringkat. */
		peringkat?: number;
	}

	let { s, peringkat = 1 }: Props = $props();

	const arahKelas = $derived.by(() => {
		const a = (s?.arah ?? '').toLowerCase();
		if (a === 'long' || a === 'beli') return 'long';
		if (a === 'short' || a === 'keluar') return 'keluar';
		return 'tahan';
	});

	const gayaPasar: Record<string, string> = {
		crypto: 'SMC · struktur & likuiditas',
		polymarket: 'Pasar prediksi · favorit 5m',
		gmgn: 'DEX · memecoin & likuiditas',
		lp: 'LP · IL & fee',
		idx: 'IDX · bandarmologi & BSJP',
		forex: 'Forex · agenda makro'
	};

	// Metrik per pasar — apa adanya dari detail. Tidak dikarang bila tidak ada.
	// Tipe eksplisit: dua cabang berbeda bentuk membuat TypeScript menyimpulkan
	// `never` dan setiap akses field jadi error.
	type Metrik = { label: string; nilai: string };
	const metrik = $derived.by((): Metrik[] => {
		const d = (s?.detail ?? {}) as Record<string, unknown>;
		const out: Metrik[] = [];
		const num = (v: unknown, d2 = 2) =>
			typeof v === 'number' ? v.toLocaleString('id-ID', { maximumFractionDigits: d2 }) : null;
		const push = (label: string, v: unknown, d2 = 2) => {
			const n = num(v, d2);
			if (n !== null) out.push({ label, nilai: n });
		};
		const p = s?.pasar;
		if (p === 'crypto') {
			push('Entry', d.entry, 6);
			push('SL', d.sl, 6);
			push('TP1', d.tp1, 6);
			push('R:R', d.rr, 1);
		} else if (p === 'polymarket') {
			push('Win-rate', d.winRate, 2);
			push('Break-even', d.breakEven_pct, 2);
			push('Butuh n', d.nNeeded, 0);
		} else if (p === 'gmgn') {
			push('V/L', d.avg_vl, 2);
			if (typeof d.viable === 'number' && typeof d.pools === 'number') {
				out.push({ label: 'Pool layak', nilai: `${d.viable} / ${d.pools}` });
			}
			push('Likuiditas', d.total_liq, 0);
		} else if (p === 'lp') {
			push('Notional', d.notional, 2);
			push('Fee/hari', d.fee_hari, 4);
			push('Umur (hari)', d.umur_hari, 1);
		}
		return out;
	});

	type Proporsi = { label: string; nilai: number; maks: number; teks: string };
	const proporsi = $derived.by((): Proporsi | null => {
		const d = (s?.detail ?? {}) as Record<string, unknown>;
		if (typeof s?.skor === 'number') {
			return { label: 'Skor sinyal', nilai: s.skor, maks: 100, teks: `${s.skor}/100` };
		}
		if (s?.pasar === 'gmgn' && typeof d.viable === 'number' && typeof d.pools === 'number') {
			return { label: 'Pool layak', nilai: d.viable, maks: d.pools, teks: `${d.viable}/${d.pools}` };
		}
		if (s?.pasar === 'polymarket' && typeof d.winRate === 'number') {
			return { label: 'Win-rate', nilai: d.winRate, maks: 100, teks: `${d.winRate.toFixed(2)}%` };
		}
		return null;
	});
</script>

<section class="bee" aria-label="Pasar {s?.label ?? '—'}">
	<header class="bee-head">
		<div class="bee-id">
			<div class="bee-name">{s?.label ?? '—'}</div>
			<div class="bee-tag">
				{gayaPasar[s?.pasar ?? ''] ?? '—'}
				{#if s?.tier}<span class="bee-style"> · {s.tier}</span>{/if}
			</div>
		</div>
		{#if s?.skor != null}
			<div class="rank">
				<div class="rank-n">#{peringkat}</div>
				<div class="rank-gap dim">dari {peringkat > 1 ? 'bawah' : 'teratas'}</div>
			</div>
		{/if}
	</header>

	<!-- Nilai utama: skor pasar. Kosong = "—", bukan 0. -->
	<div class="equity">
		{#if s?.skor != null}
			<div class="equity-value">{s.skor}<span class="dari">/100</span></div>
		{:else}
			<div class="equity-value" style="color: var(--text-3)">—</div>
			<span class="dim">tidak ada skor</span>
		{/if}
		{#if s?.umur_s != null}
			<span class="dim angka">· {umurDetik(s.umur_s)}</span>
		{/if}
	</div>

	<!-- Papan status: catatan kejujuran mendapat tempat sebesar status, bukan
	     catatan kaki. Ini blok yang paling menentukan produk ini jujur. -->
	{#if s?.catatan_kejujuran}
		<div class="cap-banner" class:aman={s.terverifikasi} role="status">
			<div class="cap-title">
				{s.terverifikasi ? '✓ Terverifikasi' : '! Belum terverifikasi'}
			</div>
			<div class="cap-detail">{s.catatan_kejujuran}</div>
		</div>
	{/if}

	<!-- Kotak sinyal (padanan kotak posisi). -->
	<div class="position {s?.ada ? 'ada' : 'flat'}">
		{#if s?.ada}
			<div class="pos-main">
				<span class="side {arahKelas}">
					{arahKelas === 'long' ? '▲' : arahKelas === 'keluar' ? '▼' : '■'}
					{s.arah ?? 'TAHAN'}
				</span>
				<span class="pos-coin">{s.subjek ?? '—'}</span>
			</div>
			{#if s.alasan}
				<div class="pos-px">{s.alasan}</div>
			{/if}
		{:else}
			<div class="pos-main">
				<span class="side flat">■ BELUM ADA SINYAL</span>
			</div>
			{#if s?.alasan}
				<div class="pos-px">{s.alasan}</div>
			{/if}
		{/if}
	</div>

	<!-- Metrik pasar: bentuknya berbeda per pasar, dan itu ditampilkan apa adanya. -->
	{#if metrik.length}
		<div class="meters">
			{#each metrik as m (m.label)}
				<div>
					<div class="meter-head"><span>{m.label}</span></div>
					<div class="num angka" style="font-size:1.05rem;font-weight:700">{m.nilai}</div>
				</div>
			{/each}
		</div>
	{/if}

	<!-- Bar proporsi -->
	{#if proporsi}
		<div>
			<div class="meter-head">
				<span>{proporsi.label}</span>
				<span class="num angka">{proporsi.teks}</span>
			</div>
			<Bar
				nilai={proporsi.nilai}
				maks={proporsi.maks}
				label={proporsi.label}
				tinggi={8}
				ambang_warn={0.75}
			/>
		</div>
	{/if}

	<!-- Baris penutup: biaya | sampel | verifikasi | umur. Padanan costs beebots. -->
	<div class="costs">
		<div>
			<span class="eyebrow">Pasar</span>
			<span class="angka">{s?.pasar ?? '—'}</span>
		</div>
		<div>
			<span class="eyebrow">Verifikasi</span>
			<span class="angka" class:good={s?.terverifikasi} class:bad={s ? !s.terverifikasi : false}>
				{s ? (s.terverifikasi ? 'ya' : 'belum') : '—'}
			</span>
		</div>
		<div>
			<span class="eyebrow">Sinyal</span>
			<span class="angka">{s?.ada ? 'ada' : 'tidak'}</span>
		</div>
		<div>
			<span class="eyebrow">Umur</span>
			<span class="angka">{s?.umur_s != null ? umurDetik(s.umur_s) : '—'}</span>
		</div>
	</div>
</section>

<style>
	.dari {
		font-size: 1.1rem;
		font-weight: 400;
		color: var(--text-3);
		letter-spacing: 0;
	}
</style>
