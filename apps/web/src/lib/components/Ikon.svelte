<script lang="ts">
	/**
	 * Ikon SVG — SATU set, satu ketebalan garis, satu ukuran (audit QA 7 Okt, prioritas 4).
	 *
	 * Kenapa diganti: UI memakai simbol unicode (⌂ ₿ ◎ ▦ ⇄ ⚡ ⚙ ⌁ ▤ ⚠ 🔔). Masalahnya:
	 * - tampil BEDA di tiap platform (emoji vs teks vs glyph kotak),
	 * - tidak bisa diwarnai konsisten (sebagian emoji berwarna sendiri),
	 * - terlihat seperti prototipe, bukan produk.
	 *
	 * Semua ikon di sini: viewBox 24, stroke 1.6, tanpa fill, `currentColor` — jadi
	 * mengikuti warna teks di sekitarnya (termasuk saat item nav aktif).
	 */
	interface Props {
		/** Nama ikon; tidak dikenal → tidak menggambar apa pun (jangan tebak). */
		nama: string;
		/** Ukuran piksel (default 16). */
		ukuran?: number;
		/** Kelas tambahan dari pemanggil. */
		kelas?: string;
	}
	let { nama, ukuran = 16, kelas = '' }: Props = $props();

	// Setiap ikon = daftar path pada grid 24×24. Sengaja tanpa fill supaya konsisten.
	const JALUR: Record<string, string[]> = {
		home: ['M4 10.5 12 4l8 6.5', 'M6 10v9h12v-9'],
		crypto: ['M12 4v16', 'M8.5 7.5h5a2.5 2.5 0 0 1 0 5h-5', 'M8.5 12.5h5.5a2.5 2.5 0 0 1 0 5H8.5'],
		polymarket: ['M12 3.5a8.5 8.5 0 1 0 0 17 8.5 8.5 0 0 0 0-17z', 'M12 8v4l2.5 2.5'],
		idx: ['M4 19h16', 'M7 19V9', 'M12 19V5', 'M17 19v-7'],
		forex: ['M5 8h11l-3-3', 'M19 16H8l3 3'],
		gmgn: ['M13 3 5 13h5l-1 8 8-10h-5l1-8z'],
		sistem: [
			'M12 9.5a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5z',
			'M12 4v2.2M12 17.8V20M4 12h2.2M17.8 12H20M6.3 6.3l1.6 1.6M16.1 16.1l1.6 1.6M17.7 6.3l-1.6 1.6M7.9 16.1l-1.6 1.6'
		],
		riset: ['M10.5 4a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13z', 'M15.5 15.5 20 20'],
		info: ['M12 3.5a8.5 8.5 0 1 0 0 17 8.5 8.5 0 0 0 0-17z', 'M12 11v5', 'M12 8h.01'],
		// status & aksi
		peringatan: ['M12 4 3.5 19h17L12 4z', 'M12 10v4', 'M12 16.5h.01'],
		lonceng: ['M7 17h10', 'M9 17V11a3 3 0 0 1 6 0v6', 'M11 20h2'],
		tutup: ['M6 6l12 12', 'M18 6 6 18'],
		panah_buka: ['M6 9l6 6 6-6'],
		panah_tutup: ['M6 15l6-6 6 6'],
		cek: ['M5 13l4 4 10-10'],
		silang: ['M6 6l12 12', 'M18 6 6 18'],
		urut: ['M8 9l4-4 4 4', 'M8 15l4 4 4-4'],
		keluar: ['M9 5H5v14h4', 'M13 8l4 4-4 4', 'M17 12H9']
	};

	const jalur = $derived(JALUR[nama] ?? []);
</script>

{#if jalur.length}
	<svg
		class={kelas}
		width={ukuran}
		height={ukuran}
		viewBox="0 0 24 24"
		fill="none"
		stroke="currentColor"
		stroke-width="1.6"
		stroke-linecap="round"
		stroke-linejoin="round"
		aria-hidden="true"
		focusable="false"
	>
		{#each jalur as d (d)}
			<path {d} />
		{/each}
	</svg>
{/if}
