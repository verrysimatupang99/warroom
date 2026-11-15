<script lang="ts">
	// Komponen Header Halaman Terpadu: Penyeragam ritme kepala seluruh halaman War Room.
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

	const tagTone = $derived.by(() => {
		const t = (tag ?? '').toUpperCase();
		if (t === 'LIVE' || t === 'AKTIF') return 'border-pos/35 bg-pos/10 text-pos';
		if (t === 'PAPER') return 'border-warn/35 bg-warn/10 text-warn';
		return 'border-line bg-surface-2 text-accent';
	});
</script>

<header
	class="flex flex-wrap items-start justify-between gap-3 border-b border-line pb-3.5"
	data-testid="page-header"
>
	<div class="min-w-0">
		<span class="label-mikro text-text-3 font-mono block">{eyebrow.toUpperCase()}</span>
		<div class="flex flex-wrap items-center gap-2 mt-1">
			<h1 class="text-20 sm:text-24 font-bold tracking-tight text-text font-display leading-tight">
				{title}
			</h1>
			{#if tag}
				<span class="rounded px-2 py-0.5 text-10 font-mono font-bold uppercase border {tagTone}">
					{tag}
				</span>
			{/if}
			{#if terverifikasi !== undefined && (sumber || alasan || terverifikasi !== null)}
				<HonestyTag {terverifikasi} {sumber} {alasan} />
			{/if}
		</div>
		{#if description}
			<p class="text-12 text-text-2 mt-1 max-w-3xl leading-relaxed">{description}</p>
		{/if}
	</div>

	{#if action}
		<div class="flex items-center gap-2 shrink-0">
			{@render action()}
		</div>
	{/if}
</header>
