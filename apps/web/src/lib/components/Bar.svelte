<script lang="ts">
	// Bar — bar proporsi bersama (pola diambil dari beebots: meter-track / board-bar /
	// prob-track, tiga nama untuk satu geometri yang sama).
	//
	// ATURAN YANG DIKODEKAN DI SINI:
	// 1. Nilai kosong (null/undefined) → TIDAK merender bar 0%. Bar 0% berarti "besarnya
	//    nol", sedangkan "tidak ada angkanya" bukan nol. Yang dirender: tanda "—".
	//    Ini prinsip yang sama dengan skor kartu pasar.
	// 2. Warna status TIDAK pernah jadi satu-satunya penanda. Pemanggil bisa memberi
	//    `label` yang menyatakan hal yang sama dalam kata, dan ambang warna di sini hanya
	//    menguatkan — bukan menggantikan — makna itu.
	interface Props {
		/** Nilai sekarang. `null`/`undefined` = tidak ada angka (bukan nol). */
		nilai?: number | null;
		/** Maksimum; pembagi. Kalau <= 0, bar tidak digambar. */
		maks?: number | null;
		/** Warna isi. Kosong = aksen tema. */
		warna?: string | null;
		/** Nama pembaca layar; wajib kalau bar ini bukan hiasan. */
		label?: string;
		/** Tinggi bar dalam px (bawaan 7, sama dengan .bar di app.css). */
		tinggi?: number;
		/** Ambang peringatan/bahaya sebagai pecahan 0..1 (mis. 0.75). */
		ambang_warn?: number | null;
		ambang_bahaya?: number | null;
	}
	let {
		nilai = null,
		maks = null,
		warna = null,
		label = '',
		tinggi = 7,
		ambang_warn = null,
		ambang_bahaya = null
	}: Props = $props();

	// Pecahan 0..1, atau null kalau tidak bisa dihitung.
	const pecahan = $derived.by(() => {
		if (nilai === null || nilai === undefined) return null;
		if (maks === null || maks === undefined || maks <= 0) return null;
		return Math.max(0, Math.min(1, nilai / maks));
	});

	const kelas_status = $derived.by(() => {
		if (pecahan === null) return '';
		if (ambang_bahaya !== null && pecahan >= ambang_bahaya) return 'bahaya';
		if (ambang_warn !== null && pecahan >= ambang_warn) return 'warn';
		return '';
	});
</script>

{#if pecahan === null}
	<!-- Tidak ada angka: tampilkan ketiadaan sebagai ketiadaan, bukan bar kosong. -->
	<span class="bar-kosong angka" title={label}>{label ? `${label}: ` : ''}—</span>
{:else}
	<div
		class="bar"
		style="height:{tinggi}px"
		role="img"
		aria-label={label ? `${label}: ${Math.round(pecahan * 100)}%` : undefined}
	>
		<span
			class="bar-isi {kelas_status}"
			style="transform:scaleX({pecahan}){warna ? `;background:${warna}` : ''}"
		></span>
	</div>
{/if}

<style>
	.bar-kosong {
		font-size: 11px;
		color: var(--color-text-3);
		letter-spacing: 0.02em;
	}
</style>
