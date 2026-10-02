<script lang="ts">
	// Blok gagal tidak pernah menyembunyikan sebabnya: pesan asli dari API ditampilkan apa adanya.
	interface Props {
		pesan: string;
		onulang?: (() => void) | null;
	}
	let { pesan, onulang = null }: Props = $props();
</script>

<div
	class="rounded-control border border-neg/40 bg-neg/10 p-3"
	role="alert"
	data-testid="error-state"
>
	<p class="label-mikro text-neg">Gagal memuat</p>
	<p class="mt-0.5 text-13 text-text">{pesan}</p>
	{#if onulang}
		<button
			type="button"
			class="target-44 transisi mt-2 inline-flex items-center rounded-control border border-line px-3 text-13 text-text-2 hover:border-accent-2 hover:text-text"
			onclick={() => onulang?.()}
		>
			Coba lagi
		</button>
	{/if}
</div>