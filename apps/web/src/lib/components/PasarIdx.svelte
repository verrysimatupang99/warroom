<script lang="ts">
	// Cabang tampilan pasar IDX (bandarmologi / BSJP).
	// Dipindah dari AreaView.svelte (Level 1 normalisasi). Isi & perilaku tidak berubah.
	import JudulBagian from './JudulBagian.svelte';

	interface Props {
		sub: string;
	}
	let { sub }: Props = $props();
</script>

{#if sub === 'sinyal' || !sub}
	<JudulBagian nomor="1" judul="Sinyal" tujuan="Bandarmologi + BSJP + ARA: siapa yang bergerak, dan sinyal apa yang keluar" ikon="◈" />
{:else if sub === 'bandarmologi'}
	<JudulBagian nomor="2" judul="Bandarmologi" tujuan="Aliran broker per emiten (ATS, frekuensi, no-sell) + skor 0–100" ikon="⚖" />
{:else if sub === 'bsjp'}
	<JudulBagian nomor="3" judul="BSJP" tujuan="Beli Sore Jual Pagi: kandidat tahan semalam, dari walk-forward (bukan karangan)" ikon="☾" />
{:else if sub === 'aliran'}
	<JudulBagian nomor="4" judul="Aliran" tujuan="Peta modal: asing vs lokal, akumulasi senyap, konflik distribusi" ikon="⇄" />
{/if}
