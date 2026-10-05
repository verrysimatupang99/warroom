<script lang="ts">
	// KartuSinyalPasar — satu sinyal terbaik untuk satu pasar.
	//
	// Bahasa visual: beebots (6 Okt 2026). Yang diambil adalah disiplinnya —
	// eyebrow mono, angka tabular, bar proporsi untuk setiap besaran yang punya
	// maksimum, dan status yang selalu berpasangan glif.
	//
	// ATURAN YANG DIPEGANG KOMPONEN INI:
	// 1. Skor kosong ditampilkan "—", BUKAN 0. Nol adalah angka; "tidak ada" bukan.
	// 2. Selama `terverifikasi` false, catatan kejujuran WAJIB tampil.
	// 3. Pasar tanpa sinyal tetap tampil beserta alasannya — bukan disembunyikan.
	// 4. Skor selalu membawa skalanya (dari 100). Angka tanpa skala adalah hiasan.
	import type { SinyalPasar } from '$lib/api/types';
	import { umurDetik } from '$lib/format';
	import Bar from './Bar.svelte';

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

	// Metrik per pasar — apa adanya dari detail. Tidak dikarang bila tidak ada.
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

	// Bar kedua yang layak ditampilkan: proporsi pool layak (gmgn) atau
	// win-rate terhadap break-even (polymarket). Hanya dirender bila angkanya ada.
	// Tipe ditulis eksplisit — tanpa itu, dua cabang berbeda bentuk membuat TypeScript
	// menyimpulkan `never` dan setiap akses field jadi error.
	type Proporsi = { label: string; nilai: number; maks: number; teks: string };
	const proporsi = $derived.by((): Proporsi | null => {
		const d = (s.detail ?? {}) as Record<string, unknown>;
		if (s.pasar === 'gmgn' && typeof d.viable === 'number' && typeof d.pools === 'number') {
			return {
				label: 'Pool layak',
				nilai: d.viable,
				maks: d.pools,
				teks: `${d.viable} / ${d.pools}`
			};
		}
		if (s.pasar === 'polymarket' && typeof d.winRate === 'number') {
			// 100 sebagai maksimum: dengan begitu bar menunjukkan di mana win-rate berada
			// pada rentang penuh 0-100%, bukan hanya "berapa persen dari dirinya sendiri".
			return {
				label: 'Win-rate',
				nilai: d.winRate,
				maks: 100,
				teks: `${d.winRate.toFixed(2)}%`
			};
		}
		return null;
	});
</script>

<article
	class="kartu {utama ? 'utama' : ''} {s.ada ? '' : 'kosong'}"
	aria-label="Sinyal pasar {s.label}"
>
	<div class="isi">
		<header>
			<span class="label-mikro">{s.label}</span>
			{#if s.tier}
				<span class="tier angka">{s.tier}</span>
			{/if}
			{#if s.umur_s != null}
				<span class="umur angka">· {umurDetik(s.umur_s)}</span>
			{/if}
		</header>

		{#if s.ada}
			<div class="baris">
				<span class="subjek angka">{s.subjek ?? '—'}</span>
				{#if s.arah}
					<span class="arah angka" style="--w:{arahWarna}">{s.arah}</span>
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

	<!-- Rail kanan: skor + bar proporsi. Pola rail dari beebots — angka besar di atas,
	     bar di bawahnya, label mono sebagai penanda bagian. -->
	<div class="rail">
		<span class="label-mikro">Skor</span>
		{#if s.skor != null}
			<b class="angka skor-angka" style="--w:{arahWarna}">{s.skor}<span class="dari">/100</span></b>
			<div class="skor-bar">
				<Bar nilai={s.skor} maks={100} warna={arahWarna} label="Skor sinyal" tinggi={6} />
			</div>
		{:else}
			<b class="angka kosong">—</b>
		{/if}

		{#if proporsi}
			<div class="rail-prop">
				<span class="label-mikro">{proporsi.label}</span>
				<div class="skor-bar">
					<Bar
						nilai={proporsi.nilai}
						maks={proporsi.maks}
						label={proporsi.label}
						tinggi={6}
						ambang_warn={0.75}
					/>
				</div>
				<span class="prop-teks angka">{proporsi.teks}</span>
			</div>
		{/if}
	</div>
</article>

<style>
	.kartu {
		display: grid;
		grid-template-columns: 1fr auto;
		gap: 20px;
		padding: 16px 18px;
	}
	.kartu.utama {
		border-color: color-mix(in srgb, var(--accent) 45%, transparent);
	}
	/* Kartu kosong: JANGAN pakai opacity pada seluruh kartu.
	   Diukur 6 Okt 2026 pada CSS ter-scope asli: `opacity: 0.6` menjatuhkan teks alasan
	   (--text-3, 12px) dari 8,08:1 ke 3,77:1 — di bawah ambang AA 4,5:1. Opacity
	   mengalikan SELURUH subpohon, jadi ia melemahkan semua teks sekaligus, termasuk
	   catatan kejujuran yang justru harus paling terbaca di kartu kosong. */
	.kartu.kosong {
		background: var(--bg-2);
		border-style: dashed;
		border-color: color-mix(in srgb, var(--line) 80%, transparent);
	}
	header {
		display: flex;
		align-items: center;
		gap: 8px;
		flex-wrap: wrap;
		margin-bottom: 10px;
	}
	.tier,
	.umur {
		font-size: 10px;
		color: var(--text-3);
		letter-spacing: 0.06em;
	}
	.tier {
		border: 1px solid var(--line);
		border-radius: 5px;
		padding: 2px 7px;
	}
	.baris {
		display: flex;
		align-items: baseline;
		gap: 10px;
		flex-wrap: wrap;
	}
	.subjek {
		font-size: 26px;
		font-weight: 700;
		color: var(--text);
		letter-spacing: -0.03em;
		line-height: 1;
	}
	.arah {
		font-size: 12px;
		font-weight: 700;
		letter-spacing: 0.06em;
		padding: 3px 9px;
		border-radius: 999px;
		color: var(--w);
		background: color-mix(in srgb, var(--w) 14%, transparent);
		border: 1px solid color-mix(in srgb, var(--w) 32%, transparent);
	}
	.metrik {
		display: flex;
		gap: 20px;
		margin-top: 12px;
		flex-wrap: wrap;
	}
	.metrik div {
		display: flex;
		flex-direction: column;
		gap: 2px;
	}
	.metrik b {
		font-size: 14px;
		font-weight: 600;
		color: var(--text);
	}
	.alasan {
		margin: 12px 0 0;
		font-size: 13px;
		color: var(--text-2);
	}
	.tak-ada {
		margin: 4px 0 0;
		font-size: 13px;
		color: var(--text-2);
	}
	/* Catatan kejujuran. Penanda bulat + latar tipis — BUKAN border kiri tebal, yang
	   justru pola paling generik pada UI hasil AI. Bentuk (bukan hanya warna) yang
	   membedakan "belum terverifikasi" dari "terverifikasi". */
	.jujur,
	.terverifikasi {
		margin: 12px 0 0;
		font-size: 12px;
		line-height: 1.5;
		padding: 8px 11px 8px 28px;
		border-radius: var(--radius-control);
		position: relative;
	}
	.jujur::before,
	.terverifikasi::before {
		content: '!';
		position: absolute;
		left: 9px;
		top: 9px;
		width: 13px;
		height: 13px;
		border-radius: 50%;
		font-size: 9px;
		font-weight: 700;
		line-height: 13px;
		text-align: center;
	}
	.jujur {
		color: var(--warn);
		background: color-mix(in srgb, var(--warn) 8%, transparent);
	}
	.jujur::before {
		content: '!';
		background: var(--warn);
		color: var(--bg);
	}
	.terverifikasi {
		color: var(--pos);
		background: color-mix(in srgb, var(--pos) 8%, transparent);
	}
	.terverifikasi::before {
		content: '✓';
		background: var(--pos);
		color: var(--bg);
	}
	.rail {
		text-align: right;
		min-width: 78px;
		display: flex;
		flex-direction: column;
		align-items: flex-end;
		gap: 4px;
	}
	.skor-angka {
		display: block;
		font-size: 34px;
		font-weight: 700;
		color: var(--w, var(--accent));
		line-height: 1;
		letter-spacing: -0.03em;
	}
	/* Skala skor: tanpa ini "72" tidak berarti apa-apa. Diukur 6 Okt 2026 — kartu
	   menampilkan skor tanpa penyebut dan tanpa acuan di halaman mana pun. */
	.dari {
		font-size: 13px;
		font-weight: 400;
		color: var(--text-3);
		letter-spacing: 0;
	}
	.skor-angka.kosong,
	.kosong {
		color: var(--text-3);
	}
	.skor-bar {
		width: 78px;
	}
	.rail-prop {
		display: flex;
		flex-direction: column;
		align-items: flex-end;
		gap: 3px;
		margin-top: 8px;
	}
	.prop-teks {
		font-size: 11px;
		color: var(--text-2);
	}
</style>
