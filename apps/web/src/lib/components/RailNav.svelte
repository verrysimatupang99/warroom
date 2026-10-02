<script lang="ts">
	// Rail nav desktop: 7 area + sub-nav kontekstual untuk area aktif. Garis amber = aktif.
	import { AREAS, areaDariJalur } from '$lib/nav';

	interface Props {
		jalur: string;
	}
	let { jalur }: Props = $props();
	const aktif = $derived(areaDariJalur(jalur));
</script>

<nav aria-label="Navigasi area" class="flex flex-col gap-1 p-2" data-testid="rail-nav">
	{#each AREAS as a (a.kunci)}
		{@const ini = aktif?.kunci === a.kunci}
		<div>
			<a
				href={a.rute}
				class="transisi flex min-h-[44px] items-center gap-2 rounded-control border-l-2 px-2 text-13 {ini
					? 'border-l-accent bg-surface-2 text-text'
					: 'border-l-transparent text-text-3 hover:bg-surface-2 hover:text-text'}"
				aria-current={ini ? 'page' : undefined}
			>
				<span class="angka w-4 text-center text-15" aria-hidden="true">{a.ikon}</span>
				<span class="label-mikro">{a.label}</span>
			</a>
			{#if ini && a.anak.length}
				<ul class="mt-1 mb-1 ml-3 space-y-0.5 border-l border-line-soft pl-2">
					{#each a.anak as anak (anak.slug)}
						<li>
							<a
								href={`${a.rute}?sub=${anak.slug}`}
								class="transisi block rounded-control px-2 py-1 text-12 {jalur.includes('?sub=') &&
								jalur.includes(anak.slug)
									? 'text-accent'
									: 'text-text-3 hover:text-text'}"
							>
								{anak.label}
							</a>
						</li>
					{/each}
				</ul>
			{/if}
		</div>
	{/each}
</nav>