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
	<div class="flex flex-wrap gap-1" role="tablist">
		{#each area.anak as a (a.slug)}
			<button
				type="button"
				role="tab"
				class="label-mikro transisi min-h-[44px] rounded-control border px-2.5 {aktif === a.slug
					? 'border-accent text-accent'
					: 'border-line text-text-3 hover:border-accent-2 hover:text-text'}"
				aria-selected={aktif === a.slug}
				title={a.catatan}
				onclick={() => onpilih(a.slug)}
			>
				{a.label}
			</button>
		{/each}
	</div>
</nav>