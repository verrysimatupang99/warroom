<script lang="ts">
	// Rail nav desktop: Dikelompokkan dalam kategori (Pasar, Riset, Sistem).
	// Memberikan kejelasan navigasi, hirarki visual, dan kemudahan akses.
	import { AREAS, areaDariJalur, type Area } from '$lib/nav';

	interface Props {
		jalur: string;
	}
	let { jalur }: Props = $props();
	const aktif = $derived(areaDariJalur(jalur));

	const grupPasar = $derived(AREAS.filter((a) => a.kategori === 'pasar'));
	const grupRiset = $derived(AREAS.filter((a) => a.kategori === 'riset'));
	const grupSistem = $derived(AREAS.filter((a) => a.kategori === 'sistem'));
</script>

<nav aria-label="Navigasi area" class="flex flex-col gap-4 p-3" data-testid="rail-nav">
	<!-- Kategori: Pasar & Trading -->
	<div>
		<span class="label-mikro px-2 text-10 font-bold tracking-wider text-text-3/70 block mb-1.5">
			Pasar &amp; Trading
		</span>
		<div class="space-y-0.5">
			{#each grupPasar as a (a.kunci)}
				{@const ini = aktif?.kunci === a.kunci}
				<div>
					<a
						href={a.rute}
						class="transisi flex min-h-[38px] items-center gap-2.5 rounded-control px-2.5 text-13 font-medium {ini
							? 'bg-accent/15 text-accent font-semibold border border-accent/30'
							: 'text-text-2 hover:bg-surface-2 hover:text-text'}"
						aria-current={ini ? 'page' : undefined}
					>
						<span class="w-4 text-center text-14 font-mono" aria-hidden="true">{a.ikon}</span>
						<span>{a.label}</span>
					</a>
					{#if ini && a.anak.length}
						<ul class="mt-1 mb-1.5 ml-4 space-y-0.5 border-l border-line-soft pl-2.5">
							{#each a.anak as anak (anak.slug)}
								<li>
									<a
										href={`${a.rute}?sub=${anak.slug}`}
										class="transisi block rounded-control px-2 py-1 text-11 {jalur.includes('?sub=') &&
										jalur.includes(anak.slug)
											? 'text-accent font-bold'
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
		</div>
	</div>

	<!-- Kategori: Riset & Analisis -->
	<div>
		<span class="label-mikro px-2 text-10 font-bold tracking-wider text-text-3/70 block mb-1.5">
			Riset &amp; Analisis
		</span>
		<div class="space-y-0.5">
			{#each grupRiset as a (a.kunci)}
				{@const ini = aktif?.kunci === a.kunci}
				<div>
					<a
						href={a.rute}
						class="transisi flex min-h-[36px] items-center gap-2.5 rounded-control px-2.5 text-12 font-medium {ini
							? 'bg-accent/15 text-accent font-semibold border border-accent/30'
							: 'text-text-3 hover:bg-surface-2 hover:text-text'}"
						aria-current={ini ? 'page' : undefined}
					>
						<span class="w-4 text-center text-13 font-mono" aria-hidden="true">{a.ikon}</span>
						<span>{a.label}</span>
					</a>
				</div>
			{/each}
		</div>
	</div>

	<!-- Kategori: Operasional -->
	<div>
		<span class="label-mikro px-2 text-10 font-bold tracking-wider text-text-3/70 block mb-1.5">
			Operasional
		</span>
		<div class="space-y-0.5">
			{#each grupSistem as a (a.kunci)}
				{@const ini = aktif?.kunci === a.kunci}
				<div>
					<a
						href={a.rute}
						class="transisi flex min-h-[38px] items-center gap-2.5 rounded-control px-2.5 text-13 font-medium {ini
							? 'bg-accent/15 text-accent font-semibold border border-accent/30'
							: 'text-text-2 hover:bg-surface-2 hover:text-text'}"
						aria-current={ini ? 'page' : undefined}
					>
						<span class="w-4 text-center text-14 font-mono" aria-hidden="true">{a.ikon}</span>
						<span>{a.label}</span>
					</a>
					{#if ini && a.anak.length}
						<ul class="mt-1 mb-1.5 ml-4 space-y-0.5 border-l border-line-soft pl-2.5">
							{#each a.anak as anak (anak.slug)}
								<li>
									<a
										href={`${a.rute}?sub=${anak.slug}`}
										class="transisi block rounded-control px-2 py-1 text-11 {jalur.includes('?sub=') &&
										jalur.includes(anak.slug)
											? 'text-accent font-bold'
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
		</div>
	</div>
</nav>