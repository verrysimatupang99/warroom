<script lang="ts">
	import JudulBagian from './JudulBagian.svelte';

	interface Props {
		sub: string;
	}
	let { sub }: Props = $props();
</script>

{#if sub === 'cockpit' || !sub}
	<JudulBagian nomor="1" judul="Cockpit GMGN" tujuan="Radar likuiditas DEX & Memecoin on-chain, status scanner pool, dan metrik smart money" ikon="◎" />
{:else if sub === 'setup'}
	<JudulBagian nomor="2" judul="Sinyal & Setup" tujuan="Scanner token baru, sinyal pump.fun / FOMO, dan filter keamanan koin" ikon="◈" />
{:else if sub === 'ukur'}
	<JudulBagian nomor="3" judul="Kuantitatif / Backtest" tujuan="Simulasi LP Meteora vs Uniswap, Impermanent Loss vs HODL, dan yield pool" ikon="⚖" />
{:else if sub === 'eksekusi'}
	<JudulBagian nomor="4" judul="Eksekusi / Paper Ledger" tujuan="Paper runner GMGN, transaksi pool tercatat, dan posisi on-chain" ikon="⇄" />
{/if}
