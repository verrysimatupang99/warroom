<script lang="ts">
	import JudulBagian from './JudulBagian.svelte';

	interface Props {
		sub: string;
	}
	let { sub }: Props = $props();
</script>

{#if sub === 'cockpit' || !sub}
	<JudulBagian nomor="1" judul="Cockpit Forex & Gold" tujuan="Struktur harga Gold (XAU/USD), bias EMA, status sesi pasar, dan metrik kuantitatif" ikon="◎" />
{:else if sub === 'setup'}
	<JudulBagian nomor="2" judul="Sinyal & Setup" tujuan="Setup Break & Retest XAU/USD, zona POI, jadwal sesi London/NY, dan kalender makro" ikon="◈" />
{:else if sub === 'ukur'}
	<JudulBagian nomor="3" judul="Kuantitatif / Backtest" tujuan="Validasi forward walk-forward, tuning parameter EMA/ATR 15m, dan akurasi" ikon="⚖" />
{:else if sub === 'eksekusi'}
	<JudulBagian nomor="4" judul="Eksekusi / Paper Ledger" tujuan="Forward paper trading execution ledger, forward testing, dan riwayat posisi" ikon="⇄" />
{/if}
