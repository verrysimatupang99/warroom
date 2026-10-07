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
		/** Bisa dilipat (revisi pemilik 7 Okt untuk "Kejadian Area"). Bila true, isi blok
		 *  disembunyikan sampai diklik — kepala tetap tampil supaya orang tahu ada apa. */
		lipat?: boolean;
		/** Awal keadaan terlipat (dipakai Kejadian yang defaultnya tertutup). */
		lipatAwal?: boolean;
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
		lipat = false,
		lipatAwal = false,
		children
	}: Props = $props();

	let terbuka = $state(!lipatAwal || !lipat);
</script>

<section class="kartu p-3" aria-label={judul} data-testid="blok">
	<header class="mb-3 flex flex-wrap items-start justify-between gap-2">
		<div>
			{#if lipat}
				<button
					type="button"
					class="flex items-center gap-2 text-left"
					aria-expanded={terbuka}
					onclick={() => (terbuka = !terbuka)}
				>
					<span class="label-mikro">{judul}</span>
					<span class="text-11 text-text-3">{terbuka ? '▾ tutup' : '▸ buka'}</span>
				</button>
			{:else}
				<h2 class="label-mikro">{judul}</h2>
			{/if}
			{#if deskripsi}<p class="mt-0.5 text-12 text-text-3">{deskripsi}</p>{/if}
		</div>
		<FreshnessBadge {status} {age_s} source={sumber} {cache} />
	</header>
	{#if lipat && !terbuka}
		{#if children}<p class="text-11 text-text-3">Terkunci rapat — klik judul untuk membuka.</p>{/if}
	{:else if memuat}
		<Skeleton baris={4} />
	{:else if galat}
		<ErrorState pesan={galat} {onulang} />
	{:else if kosong}
		<EmptyState pesan={kosongPesan} />
	{:else if children}
		{@render children()}
	{/if}
</section>