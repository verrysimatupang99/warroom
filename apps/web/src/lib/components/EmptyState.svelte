<script lang="ts">
	import type { Snippet } from 'svelte';

	interface Props {
		judul?: string;
		pesan?: string;
		langkah?: string | null;
		ringkas?: boolean;
	}
	let {
		judul = 'Belum ada data',
		pesan = 'Sumber belum mengirim angka untuk blok ini.',
		langkah = null,
		ringkas = false
	}: Props = $props();
</script>

<div
	class="flex items-start gap-3 rounded-control border border-dashed border-line bg-surface-2/50 p-3"
	role="status"
	data-testid="empty-state"
>
	<span class="angka text-19 text-text-3" aria-hidden="true">—</span>
	<div>
		<p class="label-mikro">{judul}</p>
		{#if !ringkas}<p class="mt-0.5 text-13 text-text-2">{pesan}</p>{/if}
		{#if langkah}<p class="mt-0.5 text-12 text-text-3">Langkah: {langkah}</p>{/if}
	</div>
</div>