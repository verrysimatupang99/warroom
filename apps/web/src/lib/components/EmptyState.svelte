<script lang="ts">
	import type { Snippet } from 'svelte';

	interface Props {
		judul?: string;
		pesan?: string;
		langkah?: string | null;
		ringkas?: boolean;
		/** Tindakan lanjutan opsional. Panduan ux: empty state harus memandu, bukan
		 *  layar kosong — sediakan jalan keluar saat memang ada yang bisa dilakukan. */
		onulang?: (() => void) | null;
		aksilabel?: string;
	}
	let {
		judul = 'Belum ada data',
		pesan = 'Sumber belum mengirim angka untuk blok ini.',
		langkah = null,
		ringkas = false,
		onulang = null,
		aksilabel = 'Muat ulang'
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
		{#if onulang}
			<button
				type="button"
				class="target-44 transisi mt-2 inline-flex items-center rounded-control border border-line px-3 text-13 text-text-2 hover:border-accent hover:text-text"
				onclick={() => onulang?.()}
			>
				{aksilabel}
			</button>
		{/if}
	</div>
</div>