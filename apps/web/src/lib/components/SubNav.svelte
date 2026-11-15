<script lang="ts">
	import type { Area } from '$lib/nav';

	interface Props {
		area: Area;
		aktif: string;
		onpilih: (slug: string) => void;
	}
	let { area, aktif, onpilih }: Props = $props();
</script>

<nav aria-label={`Sub-navigasi ${area.label}`}>
	<div
		class="inline-flex flex-wrap gap-1 rounded-card border border-line bg-surface p-1"
		role="tablist"
	>
		{#each area.anak as a (a.slug)}
			<button
				type="button"
				role="tab"
				class="label-mikro transisi min-h-[34px] rounded-control border px-3 py-1 {aktif === a.slug
					? 'border-accent/60 bg-surface-2 text-accent'
					: 'border-transparent text-text-3 hover:border-line hover:bg-surface-2/60 hover:text-text'}"
				aria-selected={aktif === a.slug}
				title={a.catatan}
				onclick={() => onpilih(a.slug)}
			>
				{a.label}
			</button>
		{/each}
	</div>
</nav>
