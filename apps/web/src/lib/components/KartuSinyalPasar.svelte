<script lang="ts">
	// KartuSinyalPasar — satu sinyal terbaik untuk satu pasar (gaya A: kartu bertumpuk).
	//
	// Aturan yang dipegang komponen ini:
	// 1. Skor kosong ditampilkan "—", BUKAN 0. Nol adalah angka; "tidak ada" bukan.
	// 2. Selama `terverifikasi` false, kartu WAJIB menampilkan catatan kejujuran. Klaim
	//    eksplorasi tidak boleh terlihat sama dengan edge yang sudah lolos split beku.
	// 3. Pasar tanpa sinyal tetap tampil (redup) dengan alasan — bukan disembunyikan.
	import type { SinyalPasar } from '$lib/api/types';
	import { umurDetik } from '$lib/format';

	interface Props {
		s: SinyalPasar;
		utama?: boolean;
	}

	let { s, utama = false }: Props = $props();

	const arahWarna = $derived(
		s.arah === 'KELUAR' || s.arah === 'TAHAN'
			? 'var(--neg)'
			: s.arah === 'BELI' || s.arah === 'LONG'
				? 'var(--accent)'
				: 'var(--accent-2)'
	);

	// Metrik yang layak ditampilkan per pasar — diambil dari detail apa adanya.
	const metrik = $derived.by(() => {
		const d = (s.detail ?? {}) as Record<string, unknown>;
		const out: { label: string; nilai: string }[] = [];
		const num = (v: unknown, d2 = 2) =>
			typeof v === 'number' ? v.toLocaleString('id-ID', { maximumFractionDigits: d2 }) : null;
		const push = (label: string, v: unknown, d2 = 2) => {
			const n = num(v, d2);
			if (n !== null) out.push({ label, nilai: n });
		};
		if (s.pasar === 'crypto') {
			push('Entry', d.entry, 6);
			push('SL', d.sl, 6);
			push('TP1', d.tp1, 6);
			push('R:R', d.rr, 1);
		} else if (s.pasar === 'polymarket') {
			push('Win-rate', d.winRate, 2);
			push('Break-even', d.breakEven_pct, 2);
			push('Butuh n', d.nNeeded, 0);
		} else if (s.pasar === 'gmgn') {
			push('V/L', d.avg_vl, 2);
			if (typeof d.viable === 'number' && typeof d.pools === 'number') {
				out.push({ label: 'Pool layak', nilai: `${d.viable} / ${d.pools}` });
			}
			push('Likuiditas', d.total_liq, 0);
		} else if (s.pasar === 'lp') {
			push('Notional', d.notional, 2);
			push('Fee/hari', d.fee_hari, 4);
			push('Umur (hari)', d.umur_hari, 1);
		}
		return out;
	});
</script>

<article
	class="kartu {utama ? 'utama' : ''} {s.ada ? '' : 'kosong'}"
	aria-label="Sinyal pasar {s.label}"
>
	<div class="isi">
		<header>
			<span class="nama">{s.label}</span>
			{#if s.tier}
				<span class="tier">{s.tier}</span>
			{/if}
			{#if s.umur_s != null}
				<span class="umur">· {umurDetik(s.umur_s)}</span>
			{/if}
		</header>

		{#if s.ada}
			<div class="baris">
				<span class="subjek angka">{s.subjek ?? '—'}</span>
				{#if s.arah}
					<span class="arah" style="--w:{arahWarna}">{s.arah}</span>
				{/if}
			</div>

			{#if metrik.length}
				<div class="metrik">
					{#each metrik as m (m.label)}
						<div>
							<span class="label-mikro">{m.label}</span>
							<b class="angka">{m.nilai}</b>
						</div>
					{/each}
				</div>
			{/if}

			<p class="alasan">{s.alasan}</p>

			{#if !s.terverifikasi}
				<p class="jujur" role="note">{s.catatan_kejujuran}</p>
			{:else}
				<p class="terverifikasi" role="note">✓ {s.catatan_kejujuran}</p>
			{/if}
		{:else}
			<p class="tak-ada">{s.alasan}</p>
			<p class="jujur" role="note">{s.catatan_kejujuran}</p>
		{/if}
	</div>

	<div class="skor">
		<span class="label-mikro">Skor</span>
		{#if s.skor != null}
			<b class="angka" style="--w:{arahWarna}">{s.skor}</b>
		{:else}
			<b class="angka kosong">—</b>
		{/if}
	</div>
</article>

<style>
	.kartu {
		display: grid;
		grid-template-columns: 1fr auto;
		gap: 16px;
		padding: 16px;
	}
	.kartu.utama {
		border-color: color-mix(in srgb, var(--accent) 45%, transparent);
	}
	.kartu.kosong {
		opacity: 0.6;
	}
	header {
		display: flex;
		align-items: center;
		gap: 8px;
		flex-wrap: wrap;
		margin-bottom: 8px;
	}
	.nama {
		font-size: 13px;
		color: var(--text-3);
	}
	.tier,
	.umur {
		font-family: var(--font-mono);
		font-size: 10px;
		color: var(--text-3);
	}
	.tier {
		border: 1px solid var(--line);
		border-radius: 5px;
		padding: 1px 6px;
	}
	.baris {
		display: flex;
		align-items: baseline;
		gap: 10px;
		flex-wrap: wrap;
	}
	.subjek {
		font-size: 22px;
		font-weight: 700;
		color: var(--text);
		letter-spacing: -0.01em;
	}
	.arah {
		font-family: var(--font-mono);
		font-size: 12px;
		padding: 2px 8px;
		border-radius: 6px;
		color: var(--w);
		background: color-mix(in srgb, var(--w) 14%, transparent);
		border: 1px solid color-mix(in srgb, var(--w) 30%, transparent);
	}
	.metrik {
		display: flex;
		gap: 18px;
		margin-top: 10px;
		flex-wrap: wrap;
	}
	.metrik div {
		display: flex;
		flex-direction: column;
		gap: 1px;
	}
	.metrik b {
		font-size: 13px;
		font-weight: 600;
		color: var(--text);
	}
	.alasan {
		margin: 10px 0 0;
		font-size: 12px;
		color: var(--text-2);
	}
	.tak-ada {
		margin: 4px 0 0;
		font-size: 12px;
		color: var(--text-3);
	}
	/* Catatan kejujuran + penanda terverifikasi. Bentuknya sengaja BUKAN border kiri
	   tebal: itu penanda paling khas UI hasil AI, dan di sini justru dipakai untuk hal
	   yang paling penting di produk ini. Dipakai penanda bulat + latar tipis — menonjol
	   tanpa memakai pola generik, dan bentuknya (bukan hanya warna) yang membedakan
	   "belum terverifikasi" dari "terverifikasi". */
	.jujur,
	.terverifikasi {
		margin: 10px 0 0;
		font-size: 11px;
		line-height: 1.5;
		padding: 7px 10px 7px 26px;
		border-radius: 6px;
		position: relative;
	}
	.jujur::before,
	.terverifikasi::before {
		content: '!';
		position: absolute;
		left: 9px;
		top: 8px;
		width: 12px;
		height: 12px;
		border-radius: 50%;
		font-size: 9px;
		font-weight: 700;
		line-height: 12px;
		text-align: center;
	}
	.jujur {
		color: var(--warn);
		background: color-mix(in srgb, var(--warn) 7%, transparent);
	}
	.jujur::before {
		content: '!';
		background: var(--warn);
		color: var(--bg);
	}
	.terverifikasi {
		color: var(--accent);
		background: color-mix(in srgb, var(--accent) 7%, transparent);
	}
	.terverifikasi::before {
		content: '✓';
		background: var(--accent);
		color: var(--bg);
	}
	.skor {
		text-align: right;
		min-width: 64px;
	}
	.skor b {
		display: block;
		font-size: 28px;
		font-weight: 700;
		color: var(--w, var(--accent));
		line-height: 1.1;
	}
	.skor b.kosong {
		color: var(--text-3);
	}
</style>
