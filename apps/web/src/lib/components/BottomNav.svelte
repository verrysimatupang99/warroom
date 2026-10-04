<script lang="ts">
	// Bottom tab mobile: 5 utama + "Lainnya" untuk IDX/Forex (blueprint §4).
	import { AREAS, TAB_MOBILE } from '$lib/nav';

	interface Props {
		jalur: string;
	}
	let { jalur }: Props = $props();

	let lain = $state(false);
	const lainRute = $derived(AREAS.filter((a) => !TAB_MOBILE.includes(a.rute) && a.rute !== '/'));
	const aktifLain = $derived(lainRute.some((a) => jalur.startsWith(a.rute)));
</script>

<nav
	aria-label="Navigasi utama (mobile)"
	class="fixed inset-x-0 bottom-0 z-40 border-t border-line bg-bg-2 pb-[env(safe-area-inset-bottom)] md:hidden"
	data-testid="bottom-nav"
>
	{#if lain}
		<div class="flex gap-1 border-b border-line-soft p-1">
			{#each lainRute as a (a.kunci)}
				<a
					href={a.rute}
					class="transisi flex min-h-[44px] flex-1 items-center justify-center gap-1 rounded-control text-12 {jalur.startsWith(
						a.rute
					)
						? 'text-accent'
						: 'text-text-3'}"
				>
					<span aria-hidden="true">{a.ikon}</span>{a.label}
				</a>
			{/each}
		</div>
	{/if}
	<div class="flex">
		{#each AREAS.filter((a) => TAB_MOBILE.includes(a.rute)) as a (a.kunci)}
			{@const ini = a.rute === '/' ? jalur === '/' : jalur.startsWith(a.rute)}
			<a
				href={a.rute}
				class="transisi flex min-h-[56px] flex-1 flex-col items-center justify-center gap-0.5 {ini
					? 'text-accent'
					: 'text-text-3'}"
				aria-current={ini ? 'page' : undefined}
			>
				<span class="text-15" aria-hidden="true">{a.ikon}</span>
				<span class="label-mikro">{a.label}</span>
			</a>
		{/each}
		<button
			type="button"
			class="transisi flex min-h-[56px] flex-1 flex-col items-center justify-center gap-0.5 {lain ||
			aktifLain
				? 'text-accent'
				: 'text-text-3'}"
			aria-expanded={lain}
			onclick={() => (lain = !lain)}
		>
			<span class="text-15" aria-hidden="true">⋯</span>
			<span class="label-mikro">Lainnya</span>
		</button>
	</div>
</nav>