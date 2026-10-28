<script lang="ts">
	// Kerangka bersama semua halaman pasar: satu kepala, satu sub-nav, satu isi.
	// Tujuannya menyamakan ritme antar market: tab sama, urutan blok sama, istilah sama.
	import type { Snippet } from 'svelte';
	import { goto } from '$app/navigation';
	import type { Area } from '$lib/nav';
	import PageHeader from './PageHeader.svelte';
	import SubNav from './SubNav.svelte';

	interface Props {
		area: Area;
		aktif: string;
		judul?: string;
		eyebrow?: string;
		deskripsi?: string | null;
		tag?: string | null;
		sumber?: string | null;
		terverifikasi?: boolean | null;
		alasan?: string | null;
		/** Halaman yang sudah punya kepala sendiri (mis. Info) tidak perlu kepala ganda. */
		tanpaKepala?: boolean;
		children: Snippet;
	}

	let {
		area,
		aktif,
		judul = area.label,
		eyebrow = `War Room · ${area.label}`,
		deskripsi = null,
		tag = null,
		sumber = null,
		terverifikasi = null,
		alasan = null,
		tanpaKepala = false,
		children
	}: Props = $props();

	function pilih(slug: string) {
		if (typeof window !== 'undefined') {
			void goto(`${area.rute}?sub=${slug}`, { keepFocus: true, noScroll: true });
		}
	}
</script>

<div class="space-y-4">
	{#if !tanpaKepala}
		<PageHeader {eyebrow} title={judul} {tag} description={deskripsi} {sumber} {terverifikasi} {alasan} />
	{/if}

	{#if area.anak.length > 0}
		<SubNav {area} {aktif} onpilih={pilih} />
	{/if}

	<div>
		{@render children()}
	</div>
</div>
