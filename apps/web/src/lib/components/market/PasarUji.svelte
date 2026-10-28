<script lang="ts">
	// Tab Uji: hasil backtest dari endpoint quant-backtest. Sampel dan periode wajib
	// terlihat supaya angka tidak dibaca sebagai janji.
	import QuantStrategyCard from '../QuantStrategyCard.svelte';

	interface Props {
		filter?: 'all' | 'crypto' | 'forex' | 'idx' | 'gmgn';
	}
	let { filter = 'all' }: Props = $props();
</script>

<div class="space-y-3">
	<QuantStrategyCard {filter} />
	<p class="text-11 text-text-3">
		Angka di atas berasal dari backtest tersimpan, bukan hasil live. Baca kolom jumlah
		trade dan periode sebelum menyimpulkan: sampel kecil menghasilkan PF yang tidak stabil.
	</p>
</div>
