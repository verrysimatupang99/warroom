<script lang="ts">
	// Rail nav desktop: Dikelompokkan dalam 3 kategori terstruktur (Pasar & Trading, Riset & Analisis, Operasional).
	// Memberikan kejelasan navigasi, hirarki visual, indikator aktif, dan sub-menu yang responsif saat diklik.
	import { page } from '$app/state';
	import { AREAS, areaDariJalur } from '$lib/nav';

	interface Props {
		jalur: string;
	}
	let { jalur }: Props = $props();
	const aktif = $derived(areaDariJalur(jalur));
	const subAktif = $derived(page.url.searchParams.get('sub'));

	const grupPasar = $derived(AREAS.filter((a) => a.kategori === 'pasar'));
	const grupRiset = $derived(AREAS.filter((a) => a.kategori === 'riset'));
	const grupSistem = $derived(AREAS.filter((a) => a.kategori === 'sistem'));
</script>

<nav aria-label="Navigasi area" class="flex flex-col gap-4 p-3" data-testid="rail-nav">
	<!-- Kategori 1: Pasar & Trading -->
	<div>
		<span class="label-mikro px-2 text-10 font-bold tracking-wider text-text-3/70 block mb-1.5 uppercase">
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
						<ul class="mt-1 mb-1.5 ml-4 space-y-0.5 border-l border-line-soft pl-2">
							{#each a.anak as anak, idx (anak.slug)}
								{@const isSubAktif = subAktif ? subAktif === anak.slug : idx === 0}
								<li>
									<a
										href={`${a.rute === '/' ? '/' : a.rute}?sub=${anak.slug}`}
										class="transisi block rounded-control px-2 py-1 text-11 {isSubAktif
											? 'text-accent font-bold bg-accent/10 border-l-2 border-accent pl-1.5'
											: 'text-text-3 hover:text-text hover:bg-surface-2'}"
										aria-current={isSubAktif ? 'page' : undefined}
										title={anak.catatan}
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

	<!-- Kategori 2: Riset & Analisis -->
	<div>
		<span class="label-mikro px-2 text-10 font-bold tracking-wider text-text-3/70 block mb-1.5 uppercase">
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
					{#if ini && a.anak.length}
						<ul class="mt-1 mb-1.5 ml-4 space-y-0.5 border-l border-line-soft pl-2">
							{#each a.anak as anak, idx (anak.slug)}
								{@const isSubAktif = subAktif ? subAktif === anak.slug : idx === 0}
								<li>
									<a
										href={`${a.rute}?sub=${anak.slug}`}
										class="transisi block rounded-control px-2 py-1 text-11 {isSubAktif
											? 'text-accent font-bold bg-accent/10 border-l-2 border-accent pl-1.5'
											: 'text-text-3 hover:text-text hover:bg-surface-2'}"
										aria-current={isSubAktif ? 'page' : undefined}
										title={anak.catatan}
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

	<!-- Kategori 3: Operasional -->
	<div>
		<span class="label-mikro px-2 text-10 font-bold tracking-wider text-text-3/70 block mb-1.5 uppercase">
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
						<ul class="mt-1 mb-1.5 ml-4 space-y-0.5 border-l border-line-soft pl-2">
							{#each a.anak as anak, idx (anak.slug)}
								{@const isSubAktif = subAktif ? subAktif === anak.slug : idx === 0}
								<li>
									<a
										href={`${a.rute}?sub=${anak.slug}`}
										class="transisi block rounded-control px-2 py-1 text-11 {isSubAktif
											? 'text-accent font-bold bg-accent/10 border-l-2 border-accent pl-1.5'
											: 'text-text-3 hover:text-text hover:bg-surface-2'}"
										aria-current={isSubAktif ? 'page' : undefined}
										title={anak.catatan}
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