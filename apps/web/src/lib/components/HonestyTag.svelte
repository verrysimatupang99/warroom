<script lang="ts">
	// HONESTY-TAG — motif identitas produk (DESIGN-USULAN 16 Okt): setiap angka
	// membawa status kejujurannya, bukan cuma angkanya.
	//   TERUKUR              -> solid mint  + titik + sumber
	//   BELUM TERVERIFIKASI  -> dashed merah + glyph '!' + sumber
	//   kosong/tanpa status  -> '—' + alasan, tidak dikarang.
	// Aturan repo: warna TIDAK pernah satu-satunya penanda — glyph/kata selalu ada.
	interface Props {
		/** true = TERUKUR, false = BELUM TERVERIFIKASI, null = tidak ada status */
		terverifikasi: boolean | null;
		/** sumber/metode verifikasi (mis. 'walk-forward', 'CLOB WS snapshot') */
		sumber?: string | null;
		/** alasan bila tidak ada angka/status (ditampilkan sebagai '— <alasan>') */
		alasan?: string | null;
	}
	let { terverifikasi, sumber = null, alasan = null }: Props = $props();
</script>

{#if terverifikasi === true}
	<span class="honesty terukur">
		<span class="dot" aria-hidden="true"></span>
		<span class="kata">TERUKUR</span>
		{#if sumber}<span class="sumber">{sumber}</span>{/if}
	</span>
{:else if terverifikasi === false}
	<span class="honesty belum">
		<span class="glyph" aria-hidden="true">!</span>
		<span class="kata">BELUM TERVERIFIKASI</span>
		{#if sumber}<span class="sumber">{sumber}</span>{/if}
	</span>
{:else}
	<span class="honesty kosong" title={alasan ?? ''}>
		<span class="kata">—</span>
		{#if alasan}<span class="sumber">{alasan}</span>{/if}
	</span>
{/if}

<style>
	.honesty {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
		padding: 0.1rem 0.4rem;
		border-radius: 4px;
		font-family: var(--font-mono);
		font-size: 0.58rem;
		line-height: 1;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		white-space: nowrap;
		max-width: 100%;
		overflow: hidden;
	}
	.kata {
		font-weight: 700;
	}
	.sumber {
		font-size: 0.55rem;
		text-transform: none;
		letter-spacing: 0.02em;
		border-left: 1px solid var(--color-line);
		padding-left: 0.3rem;
		color: var(--color-text-2);
		overflow: hidden;
		text-overflow: ellipsis;
	}
	/* TERUKUR: solid mint — mint HANYA untuk nilai positif terukur. */
	.terukur {
		background: var(--color-surface-2);
		border: 1px solid var(--color-pos);
		color: var(--color-pos);
	}
	.terukur .dot {
		width: 6px;
		height: 6px;
		border-radius: 999px;
		background: var(--color-pos);
		flex-shrink: 0;
	}
	/* BELUM TERVERIFIKASI: dashed merah + glyph '!' — merah hanya risiko, dan
	   di sini wujudnya berupa KATA + GLYPH, bukan warna saja (aturan repo). */
	.belum {
		background: var(--color-surface);
		border: 1px dashed var(--color-neg);
		color: var(--color-neg);
	}
	.glyph {
		font-weight: 700;
		flex-shrink: 0;
	}
	/* Tanpa status: tanda '—' + alasan, tanpa meminjamkan warna apa pun. */
	.kosong {
		background: var(--color-surface-2);
		border: 1px solid var(--color-line);
		color: var(--color-text-2);
	}
</style>
