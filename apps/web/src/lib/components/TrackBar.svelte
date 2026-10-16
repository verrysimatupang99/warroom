<script lang="ts">
	// TRACK BAR — komponen warisan pola bar proporsi (track + fill) yang sudah
	// teruji di app.css (kelas .bar/.bar-isi, beebots 6 Okt). DESIGN-USULAN 16 Okt
	// memilihnya kembali sebagai komponen untuk membandingkan besaran ber-maksimum
	// (skor 0-100, meter, bobot). Diciptakan sebagai komponen karena pola itu kini
	// dibutuhkan lintas halaman dengan kop label + ambang yang seragam.
	//
	// Aturan kejujuran: nilai kosong -> render '—' + alasan, JANGAN bar 0%.
	import Ikon from './Ikon.svelte';

	interface Props {
		label: string;
		/** nilai 0..maks; null/undefined -> tanda '—' tanpa bar */
		nilai?: number | null;
		maks?: number;
		/** ambang yang menyatakan batas keputusan (ditulis sebagai kata, bukan warna) */
		ambang?: number | null;
		/** teks status di sisi ambang, mis. 'AMBANG: 75' atau 'DI BAWAH' */
		teksAmbang?: string | null;
		/** nada visual; isi bar tetap disertai kata di pemanggil */
		nada?: 'terkukur' | 'warn' | 'bahaya' | 'netral';
		ikon?: string | null;
		alasan?: string | null;
	}
	let {
		label,
		nilai = null,
		maks = 100,
		ambang = null,
		teksAmbang = null,
		nada = 'netral',
		ikon = null,
		alasan = null
	}: Props = $props();

	const persen = $derived(
		typeof nilai === 'number' && Number.isFinite(nilai) && maks > 0
			? Math.max(0, Math.min(100, (nilai / maks) * 100))
			: null
	);
	const diBawah = $derived(persen !== null && ambang !== null && nilai! < ambang);
</script>

<div class="track" data-testid="track-bar">
	<div class="kepala">
		<span class="label label-mikro">
			{#if ikon}<span class="ikon" aria-hidden="true"><Ikon nama={ikon} ukuran={13} /></span>{/if}
			{label}
		</span>
		<span class="nilai angka" class:risiko={nada === 'bahaya'} class:kosong={persen === null}>
			{#if persen !== null}
				{Number.isInteger(nilai!) ? nilai : nilai!.toLocaleString('id-ID')}<span class="dari">/{maks}</span>
			{:else}
				—
			{/if}
		</span>
	</div>
	{#if persen !== null}
		<div class="bar">
			<div class="bar-isi {nada === 'netral' ? '' : nada}" style:width={`${persen}%`} role="presentation"></div>
		</div>
	{:else if alasan}
		<p class="alasan">{alasan}</p>
	{/if}
	{#if ambang !== null || teksAmbang}
		<div class="kaki label-mikro">
			<span>0</span>
			<span class:negatif={diBawah || nada === 'bahaya'} class:positif={nada === 'terkukur'}>
				{teksAmbang ?? `AMBANG: ${ambang}`}
			</span>
			<span>{maks}</span>
		</div>
	{/if}
</div>

<style>
	.track {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}
	.kepala {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
	}
	.label {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
		min-width: 0;
	}
	.ikon {
		display: inline-flex;
		flex-shrink: 0;
	}
	.nilai {
		font-weight: 700;
		color: var(--color-text);
		white-space: nowrap;
	}
	.nilai.kosong {
		color: var(--color-text-2);
	}
	/* Merah hanya risiko — dan selalu bersama kata (label/teks ambang). */
	.nilai.risiko {
		color: var(--color-neg);
	}
	.dari {
		font-weight: 400;
		color: var(--color-text-2);
	}
	.alasan {
		margin: 0;
		font-size: 0.72rem;
		color: var(--color-text-2);
		line-height: 1.4;
	}
	.kaki {
		display: flex;
		justify-content: space-between;
		font-size: 0.55rem;
	}
	.kaki .positif {
		color: var(--color-pos);
	}
	.kaki .negatif {
		color: var(--color-neg);
	}
</style>
