<script lang="ts">
	// OpenMarket — cakupan venue, tipe data, dan pasar lewat satu API.
	// Sumber: /api/v1/openmarket/cakupan (statis + status aktivasi).
	import { onMount } from 'svelte';
	import { urlApi } from '$lib/api/client';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import Skeleton from '$lib/components/Skeleton.svelte';

	interface Pasar {
		nama?: string;
		cakupan?: string;
	}
	interface Cakupan {
		tersedia?: boolean;
		alasan?: string | null;
		venue?: string[];
		jumlah_venue?: number;
		tipe_data?: string[];
		interval?: string[];
		pasar?: Pasar[];
		catatan?: string;
		sumber?: string;
	}

	let data = $state<Cakupan | null>(null);
	let memuat = $state(true);
	let galat = $state<string | null>(null);

	async function muat() {
		memuat = true;
		galat = null;
		try {
			const r = await fetch(urlApi('/api/v1/openmarket/cakupan'), { credentials: 'include' });
			const isi = await r.json().catch(() => null);
			if (!r.ok) {
				galat = isi?.error?.message ?? isi?.detail ?? `HTTP ${r.status}`;
				return;
			}
			data = isi;
		} catch (e) {
			galat = e instanceof Error ? e.message : 'gagal menghubungi API';
		} finally {
			memuat = false;
		}
	}
	onMount(muat);

	const jumlahVenue = $derived(data?.venue?.length ?? 0);
	const jumlahTipe = $derived(data?.tipe_data?.length ?? 0);
	const jumlahPasar = $derived(data?.pasar?.length ?? 0);
	const jumlahInterval = $derived(data?.interval?.length ?? 0);
</script>

<PageHeader
	eyebrow="Riset · data"
	title="OpenMarket"
	description="Satu API untuk 40+ venue: crypto, saham US, futures, options, forex, prediction markets, economic data."
/>

{#if memuat}
	<div class="grid gap-3 md:grid-cols-3">
		<Skeleton />
		<Skeleton />
		<Skeleton />
	</div>
{:else if galat}
	<EmptyState judul="Gagal memuat cakupan" pesan={galat} onulang={muat} />
{:else if data}
	{#if !data.tersedia}
		<div class="mb-4 rounded-card border border-warn bg-surface p-4">
			<div class="text-13 font-600 text-warn">Belum aktif</div>
			<p class="mt-1 text-13 text-text-2">{data.alasan ?? 'OPENMARKET_API_KEY belum di-set.'}</p>
		</div>
	{/if}

	<div class="grid gap-3 md:grid-cols-3">
		<div class="rounded-card border border-line bg-surface p-4">
			<div class="label-mikro font-mono text-text-3">VENUE</div>
			<div class="mt-1 font-mono text-17 font-700 text-text">
				{jumlahVenue} / {data.jumlah_venue ?? 21}
			</div>
			<div class="mt-1 text-12 text-text-3">Venue data (subset utama)</div>
		</div>
		<div class="rounded-card border border-line bg-surface p-4">
			<div class="label-mikro font-mono text-text-3">TIPE DATA</div>
			<div class="mt-1 font-mono text-17 font-700 text-text">{jumlahTipe}</div>
			<div class="mt-1 text-12 text-text-3">Candle, funding, OI, liquidations</div>
		</div>
		<div class="rounded-card border border-line bg-surface p-4">
			<div class="label-mikro font-mono text-text-3">PASAR</div>
			<div class="mt-1 font-mono text-17 font-700 text-text">{jumlahPasar}</div>
			<div class="mt-1 text-12 text-text-3">Kelas aset · {jumlahInterval} interval</div>
		</div>
	</div>

	{#if data.pasar && data.pasar.length}
		<section class="mt-6">
			<h2 class="text-14 font-600 text-text">Kelas aset</h2>
			<div class="mt-2 grid gap-2 md:grid-cols-2">
				{#each data.pasar as p (p.nama)}
					<div
						class="flex items-center justify-between rounded-card border border-line bg-surface p-3"
					>
						<span class="text-13 font-600 text-text">{p.nama ?? '—'}</span>
						<span class="text-12 text-text-3">{p.cakupan ?? '—'}</span>
					</div>
				{/each}
			</div>
		</section>
	{/if}

	{#if data.venue && data.venue.length}
		<section class="mt-6">
			<h2 class="text-14 font-600 text-text">Venue</h2>
			<div class="mt-2 flex flex-wrap gap-2">
				{#each data.venue as v (v)}
					<span class="rounded-control border border-line bg-surface px-2 py-1 font-mono text-11 text-text-2"
						>{v}</span
					>
				{/each}
			</div>
		</section>
	{/if}

	{#if data.tipe_data && data.tipe_data.length}
		<section class="mt-6">
			<h2 class="text-14 font-600 text-text">Tipe data</h2>
			<div class="mt-2 flex flex-wrap gap-2">
				{#each data.tipe_data as t (t)}
					<span class="rounded-control border border-line bg-surface px-2 py-1 font-mono text-11 text-text-2"
						>{t}</span
					>
				{/each}
			</div>
		</section>
	{/if}

	{#if data.catatan}
		<p class="mt-6 text-12 text-text-3">{data.catatan} · Sumber: {data.sumber ?? '—'}</p>
	{/if}
{:else}
	<EmptyState judul="Cakupan kosong" pesan="API tidak mengembalikan data." onulang={muat} />
{/if}
