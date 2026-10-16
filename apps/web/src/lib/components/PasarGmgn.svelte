<script lang="ts">
	// Cabang tampilan pasar GMGN (DEX & Memecoin).
	// Dipindah dari AreaView.svelte (Level 1 normalisasi). Isi & perilaku tidak berubah.
	import JudulBagian from './JudulBagian.svelte';

	interface Props {
		sub: string;
	}
	let { sub }: Props = $props();
</script>

{#if sub === 'radar' || !sub}
	<JudulBagian nomor="1" judul="Radar" tujuan="Kapan tiap jaringan ramai (jam ramai-nya) + Robinhood Chain vs Meteora + cek harga langsung" ikon="◉" />
{:else if sub === 'lp'}
	<JudulBagian nomor="2" judul="LP" tujuan="Menaruh dana di dua tempat: Solana (Meteora) &amp; Robinhood Chain (Uniswap) — untung fee, risiko impermanent loss, bandingkan dgn sekadar tahan" ikon="≋" />
{:else if sub === 'memecoin'}
	<JudulBagian nomor="3" judul="Memecoin" tujuan="Token baru dari GMGN/FOMO: bot uji coba, saringan keamanan, pantauan pemain besar — eksplorasi, bukan rekomendasi" ikon="✦" />
{/if}
