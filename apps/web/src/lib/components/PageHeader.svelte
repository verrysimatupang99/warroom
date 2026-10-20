<script lang="ts">
	// Komponen Header Halaman Terpadu: Penyeragam ritme kepala seluruh 14 halaman War Room.
	// Anatomi: Eyebrow mono uppercase + Judul H1 font-display + Badge Area + HonestyTag + Deskripsi.
	import type { Snippet } from 'svelte';
	import HonestyTag from './HonestyTag.svelte';

	interface Props {
		eyebrow: string;
		title: string;
		tag?: string | null;
		description?: string | null;
		terverifikasi?: boolean | null;
		sumber?: string | null;
		alasan?: string | null;
		action?: Snippet;
	}

	let {
		eyebrow,
		title,
		tag = null,
		description = null,
		terverifikasi = null,
		sumber = null,
		alasan = null,
		action
	}: Props = $props();
</script>

<header class="flex flex-wrap items-center justify-between gap-3 border-b border-line pb-3" data-testid="page-header">
	<div class="min-w-0">
		<span class="label-mikro text-text-3 font-mono block">{eyebrow.toUpperCase()}</span>
		<div class="flex flex-wrap items-center gap-2 mt-0.5">
			<h1 class="text-22 sm:text-26 font-bold tracking-tight text-text font-display">{title}</h1>
			{#if tag}
				<span class="rounded bg-surface px-2 py-0.5 text-11 font-mono uppercase text-accent border border-line">
					{tag}
				</span>
			{/if}
			{#if terverifikasi !== undefined && (sumber || alasan || terverifikasi !== null)}
				<HonestyTag {terverifikasi} {sumber} {alasan} />
			{/if}
		</div>
		{#if description}
			<p class="text-12 text-text-3 mt-1 max-w-2xl leading-relaxed">{description}</p>
		{/if}
	</div>

	{#if action}
		<div class="flex items-center gap-2 shrink-0">
			{@render action()}
		</div>
	{/if}
</header>
