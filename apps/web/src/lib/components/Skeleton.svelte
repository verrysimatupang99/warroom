<script lang="ts">
	interface Props {
		baris?: number;
		tinggi?: number;
	}
	let { baris = 3, tinggi = 12 }: Props = $props();
	const daftar = $derived(Array.from({ length: Math.max(1, baris) }, (_, i) => i));
</script>

<div class="space-y-2" aria-hidden="true" data-testid="skeleton">
	{#each daftar as i (i)}
		<div
			class="animate-pulse rounded-control bg-surface-3"
			style={`height:${tinggi}px; width:${i === daftar.length - 1 ? '60%' : '100%'}`}
		></div>
	{/each}
</div>