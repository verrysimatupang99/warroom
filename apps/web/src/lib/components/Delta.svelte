<script lang="ts">
	// Delta — perubahan nilai (naik/turun). Pola dari beebots: glif + tanda + angka mono.
	//
	// ATURAN YANG DIKODEKAN: warna TIDAK pernah jadi satu-satunya penanda. Glif ▲/▼ dan
	// tanda +/− menyatakan hal yang sama dalam bentuk dan karakter, jadi tetap terbaca
	// kalau warnanya hilang (buta warna, cetak hitam-putih, mode kontras tinggi).
	interface Props {
		/** Perubahan. `null`/`undefined` = tidak ada angka. */
		nilai?: number | null;
		/** Perubahan persen, opsional. */
		persen?: number | null;
		/** Awalan satuan, mis. "$" atau "Rp". */
		awalan?: string;
		/** Jumlah desimal. */
		desimal?: number;
	}
	let { nilai = null, persen = null, awalan = '', desimal = 2 }: Props = $props();

	// Disiapkan di sini, bukan di dalam template: ekspresi `as` di blok `#if` tidak
	// bisa di-parse oleh kompilator Svelte, dan itu menghasilkan error yang menyesatkan.
	const angka = $derived.by(() => {
		if (nilai === null || nilai === undefined || !Number.isFinite(nilai)) return null;
		return nilai;
	});
	const persenAda = $derived(
		persen !== null && persen !== undefined && Number.isFinite(persen) ? persen : null
	);
	const naik = $derived(angka === null ? true : angka >= 0);

	function bulat(x: number): string {
		return Math.abs(x).toLocaleString('id-ID', {
			minimumFractionDigits: desimal,
			maximumFractionDigits: desimal
		});
	}
</script>

{#if angka === null}
	<span class="delta" style="color: var(--color-text-3)">—</span>
{:else}
	<span class="delta {naik ? 'delta-naik' : 'delta-turun'}">
		<span aria-hidden="true">{naik ? '▲' : '▼'}</span>
		<!-- Tanda +/− bukan hiasan: ia menyampaikan arah dalam bentuk teks, sehingga
		     maknanya tidak bergantung pada warna maupun glif. -->
		<span>{naik ? '+' : '−'}{awalan}{bulat(angka)}</span>
		{#if persenAda !== null}
			<span style="color: var(--color-text-3)">({bulat(persenAda)}%)</span>
		{/if}
	</span>
{/if}
