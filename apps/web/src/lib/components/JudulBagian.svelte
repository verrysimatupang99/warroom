<script lang="ts">
	/**
	 * Pemisah bagian (7 Okt): pemilik mengeluh tiap halaman terasa "SPA" — semua blok
	 * mengalir tanpa batas yang jelas. Komponen ini memberi TEKS + GARIS + TUJUAN tiap
	 * kelompok blok, sehingga jelas: bagian ini untuk apa, dan bedanya dengan bagian lain.
	 */
	interface Props {
		nomor?: string;
		judul: string;
		tujuan?: string;
		ikon?: string;
	}
	let { nomor, judul, tujuan, ikon }: Props = $props();
</script>

<div class="mb-3 mt-1 flex items-start gap-2.5 border-b border-line pb-1.5">
	{#if nomor}
		<span class="mt-0.5 rounded bg-surface border border-line px-1.5 py-0.5 text-10 font-bold font-mono text-accent">{nomor}</span>
	{/if}
	<div class="min-w-0">
		<h2 class="text-13 font-bold uppercase tracking-wide text-text">
			{#if ikon}<span class="mr-1">{ikon}</span>{/if}{judul}
		</h2>
		{#if tujuan}
			<p class="text-11 text-text-3">{tujuan}</p>
		{/if}
	</div>
</div>
