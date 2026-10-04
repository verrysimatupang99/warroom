<script lang="ts">
	// Blok baku: judul + badge kesegaran + state kosong/basi/error. Semua blok halaman wajib
	// lewat sini supaya tidak ada blok tanpa penanganan state.
	import type { Snippet } from 'svelte';
	import FreshnessBadge from './FreshnessBadge.svelte';
	import Skeleton from './Skeleton.svelte';
	import ErrorState from './ErrorState.svelte';
	import EmptyState from './EmptyState.svelte';

	interface Props {
		judul: string;
		deskripsi?: string;
		memuat?: boolean;
		galat?: string | null;
		kosong?: boolean;
		kosongPesan?: string;
		sumber?: string | null;
		age_s?: number | null;
		status?: string | null;
		cache?: boolean;
		onulang?: (() => void) | null;
		children?: Snippet;
	}
	let {
		judul,
		deskripsi = '',
		memuat = false,
		galat = null,
		kosong = false,
		kosongPesan = 'Belum ada data untuk blok ini.',
		sumber = null,
		age_s = null,
		status = null,
		cache = false,
		onulang = null,
		children
	}: Props = $props();
</script>

<section class="kartu p-3" aria-label={judul} data-testid="blok">
	<header class="mb-3 flex flex-wrap items-start justify-between gap-2">
		<div>
			<h2 class="label-mikro">{judul}</h2>
			{#if deskripsi}<p class="mt-0.5 text-12 text-text-3">{deskripsi}</p>{/if}
		</div>
		<FreshnessBadge {status} {age_s} source={sumber} {cache} />
	</header>
	{#if memuat}
		<Skeleton baris={4} />
	{:else if galat}
		<ErrorState pesan={galat} {onulang} />
	{:else if kosong}
		<EmptyState pesan={kosongPesan} />
	{:else if children}
		{@render children()}
	{/if}
</section>