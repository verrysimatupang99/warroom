<script lang="ts">
	import JudulBagian from './JudulBagian.svelte';

	interface Props {
		sub: string;
	}
	let { sub }: Props = $props();
</script>

{#if sub === 'cockpit' || !sub}
	<JudulBagian nomor="1" judul="Cockpit IDX" tujuan="Overview pasar modal domestik, skor akumulasi bandar, dan status sesi reguler" ikon="◎" />
{:else if sub === 'setup'}
	<JudulBagian nomor="2" judul="Sinyal & Setup" tujuan="Emiten lolos saringan: Sinyal BSJP, ARA Hunter, dan Broker Summary" ikon="◈" />
{:else if sub === 'ukur'}
	<JudulBagian nomor="3" judul="Kuantitatif / Backtest" tujuan="Uji statistik BSJP, akurasi aturan bandarmologi, dan backtest emiten" ikon="⚖" />
{:else if sub === 'eksekusi'}
	<JudulBagian nomor="4" judul="Eksekusi / Paper Ledger" tujuan="Simulasi paper portofolio saham IDX (Rp 10 jt) dan riwayat transaksi" ikon="⇄" />
{/if}
