<script lang="ts">
	// DECISION CARD — kartu keputusan (DESIGN-USULAN 16 Okt): halaman dibangun dari
	// "kartu keputusan" (satu kesimpulan per kartu), bukan dinding widget maupun
	// bento-grid. Isi: judul, deskripsi satu kalimat, honesty-tag, satu baris
	// "METRIK UTAMA" (angka mono), dan opsional track bar + tautan.
	//
	// Aturan repo: kartu TIDAK PERNAH menghitung apa pun — angka dikirim dari halaman
	// (yang membacanya dari tabel facts/API) apa adanya; nilai kosong = '—' + alasan.
	import HonestyTag from './HonestyTag.svelte';
	import TrackBar from './TrackBar.svelte';

	interface Props {
		judul: string;
		/** deskripsi satu-dua kalimat dari API, bukan kesimpulan UI */
		deskripsi?: string | null;
		terverifikasi: boolean | null;
		sumber?: string | null;
		alasan?: string | null;
		/** baris metrik utama: { label, nilai, nada } — nilai string sudah terformat */
		metrik?: { label: string; nilai: string; nada?: 'pos' | 'neg' | 'netral' } | null;
		/** opsional: skor untuk track bar */
		skor?: number | null;
		maksSkor?: number;
		teksAmbang?: string | null;
		href?: string | null;
		teksLink?: string | null;
	}
	let {
		judul,
		deskripsi = null,
		terverifikasi,
		sumber = null,
		alasan = null,
		metrik = null,
		skor = null,
		maksSkor = 100,
		teksAmbang = null,
		href = null,
		teksLink = null
	}: Props = $props();

	const nadaNama = $derived(
		metrik?.nada === 'pos' ? 'terkukur' : metrik?.nada === 'neg' ? 'bahaya' : 'netral'
	);
</script>

<article class="kartu-keputusan" data-testid="decision-card">
	<header class="kepala">
		<h3>{judul}</h3>
		<HonestyTag {terverifikasi} {sumber} {alasan} />
	</header>

	{#if deskripsi}
		<p class="deskripsi">{deskripsi}</p>
	{/if}

	{#if metrik}
		<div class="metrik">
			<span class="metrik-label label-mikro">{metrik.label}</span>
			<span class="metrik-nada {nadaNama}">
				{#if nadaNama === 'bahaya'}<span aria-hidden="true">▼</span>{/if}
				{#if nadaNama === 'terkukur'}<span aria-hidden="true">▲</span>{/if}
				<span class="angka metrik-nilai">{metrik.nilai}</span>
				{#if nadaNama !== 'netral'}
					<span class="metrik-kata">{metrik.nada === 'pos' ? 'POSITIF' : 'RISIKO'}</span>
				{/if}
			</span>
		</div>
	{:else if alasan}
		<div class="metrik metrik-kosong">
			<span class="metrik-label label-mikro">METRIK UTAMA</span>
			<span class="angka kosong">—</span>
			<p class="alasan">{alasan}</p>
		</div>
	{/if}

	{#if typeof skor === 'number'}
		<TrackBar label="SKOR VALIDASI" nilai={skor} maks={maksSkor} nada={nadaNama === 'bahaya' ? 'bahaya' : nadaNama === 'terkukur' ? 'terkukur' : 'netral'} />
	{/if}

	{#if href}
		<a class="tautan" href={href}>{teksLink ?? 'Buka'} →</a>
	{/if}
</article>

<style>
	/* FLAT: dokumen berbatas hairline (R-31). Satu elemen fokus boleh diberi border
	   amber — itu tugas halaman (via prop class/section), bukan bawaan kartu. */
	.kartu-keputusan {
		display: flex;
		flex-direction: column;
		background: var(--color-surface);
		border: 1px solid var(--color-line);
		border-radius: var(--radius-card);
		padding: 0.75rem;
	}
	.kepala {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 0.5rem;
		margin-bottom: 0.35rem;
	}
	.kepala h3 {
		margin: 0;
		font-size: 1rem;
		font-weight: 600;
		color: var(--color-text);
		letter-spacing: -0.005em;
	}
	.deskripsi {
		margin: 0 0 0.5rem;
		font-size: 0.82rem;
		color: var(--color-text-2);
		line-height: 1.45;
	}
	.metrik {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: 0.5rem;
		background: var(--color-surface-2);
		border: 1px solid var(--color-line);
		border-radius: 4px;
		padding: 0.4rem 0.5rem;
		margin-bottom: 0.5rem;
		flex-wrap: wrap;
	}
	.metrik-kosong {
		flex-direction: column;
		align-items: stretch;
		gap: 0.25rem;
	}
	.metrik-label {
		font-size: 0.68rem;
	}
	.metrik-nada {
		display: inline-flex;
		align-items: baseline;
		gap: 0.25rem;
		font-size: 0.9rem;
	}
	.metrik-nilai {
		font-weight: 700;
		font-size: 1rem;
		color: var(--color-text);
	}
	.metrik-nada.terkukur .metrik-nilai {
		color: var(--color-pos);
	}
	.metrik-nada.bahaya .metrik-nilai {
		color: var(--color-neg);
	}
	.metrik-kata {
		font-family: var(--font-mono);
		font-size: 0.58rem;
		font-weight: 700;
		letter-spacing: 0.08em;
		color: inherit;
	}
	.metrik-nada.terkukur {
		color: var(--color-pos);
	}
	.metrik-nada.bahaya {
		color: var(--color-neg);
	}
	.kosong {
		color: var(--color-text-2);
		font-weight: 700;
	}
	.alasan {
		margin: 0;
		font-size: 0.68rem;
		color: var(--color-text-2);
		border-top: 1px solid var(--color-line);
		padding-top: 0.25rem;
		line-height: 1.35;
	}
	.tautan {
		margin-top: auto;
		align-self: flex-start;
		display: inline-flex;
		align-items: center;
		min-height: 44px;
		font-size: 0.75rem;
		color: var(--color-accent);
		text-decoration: none;
		padding: 0 0.25rem;
	}
	.tautan:hover {
		text-decoration: underline;
	}
</style>
