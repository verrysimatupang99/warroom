<script lang="ts">
	import JudulBagian from './JudulBagian.svelte';

	interface Props {
		sub: string;
	}
	let { sub }: Props = $props();
</script>

{#if sub === 'cockpit' || !sub}
	<JudulBagian nomor="1" judul="Cockpit Polymarket" tujuan="Ringkasan pasar binary, Arm B favorit 0.70-0.95, akurasi, dan dompet paper" ikon="◎" />
{:else if sub === 'setup'}
	<JudulBagian nomor="2" judul="Sinyal & Setup" tujuan="Sinyal aktif: Favorit 0,70–0,95 (Arm B) + PolyBTC 5m momentum" ikon="◈" />
{:else if sub === 'ukur'}
	<JudulBagian nomor="3" judul="Kuantitatif / Backtest" tujuan="Dataset historis, parity/drift analysis, dan katalog replay pengujian kuantitatif" ikon="⚖" />
{:else if sub === 'eksekusi'}
	<JudulBagian nomor="4" judul="Eksekusi / Paper Ledger" tujuan="Paper trade ledger, status arming 3-way, dan eksekusi binary CLOB" ikon="⇄" />
{/if}
