<script lang="ts">
	// Berita — padanan /news algentis, sumber RSS publik (Cointelegraph, Decrypt).
	// Hanya judul + tautan + waktu + sumber. Ringkasan TIDAK disalin utuh (hak cipta
	// penerbit) — kita menautkan ke artikel aslinya.
	import { getArea } from '$lib/api/client';
	import type { AreaPayload, Fact } from '$lib/api/types';
	import { umurDetik, waktuWIB } from '$lib/format';
	import NavInfo from '$lib/components/NavInfo.svelte';
	import Skeleton from '$lib/components/Skeleton.svelte';
	import ErrorState from '$lib/components/ErrorState.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';

	let forex = $state<AreaPayload | null>(null);
	let galat = $state<string | null>(null);
	let memuat = $state(true);

	async function muat() {
		try {
			forex = await getArea('forex');
			galat = null;
		} catch (e) {
			galat = e instanceof Error ? e.message : String(e);
		}
		memuat = false;
	}
	$effect(() => {
		void muat();
		const t = setInterval(() => void muat(), 60000);
		return () => clearInterval(t);
	});

	const fakta = (key: string): Fact | null => forex?.facts.find((f) => f.key === key) ?? null;
	type NewsBagian = {
		tersedia?: boolean;
		sumber_data?: string;
		jumlah?: number;
		feed?: string[];
		items?: { judul: string; tautan: string; sumber: string; ts: number; umur_s: number }[];
	};
	const news = $derived(
		((fakta('bagian')?.value as { news?: NewsBagian } | undefined)?.news ?? null)
	);
	const items = $derived(news?.items ?? []);
</script>

<svelte:head><title>Berita — War Room</title></svelte:head>

<div class="berita">
	<header class="kepala">
		<h1>Berita</h1>
		<p class="dim">
			Judul + tautan dari feed publik. Ringkasan tidak disalin — klik untuk baca di sumbernya.
		</p>
	</header>

	<NavInfo />

	{#if galat && !forex}
		<ErrorState pesan={galat} onulang={muat} />
	{:else if memuat && !forex}
		<Skeleton baris={8} />
	{:else}
		<section class="kartu">
			<h2 class="judul">
				Feed
				<span class="dim">
					{news?.jumlah ?? 0} item · {news?.sumber_data ?? '—'}
					{#if news?.feed}· {news.feed.join(' + ')}{/if}
				</span>
			</h2>
			{#if items.length}
				<ul class="daftar">
					{#each items as it (it.tautan)}
						<li>
							<a href={it.tautan} target="_blank" rel="noopener noreferrer">
								<span class="judul-item">{it.judul}</span>
								<span class="meta">
									<span class="sumber">{it.sumber}</span>
									<span class="angka dim">{umurDetik(it.umur_s)} lalu</span>
									<span class="angka dim">{waktuWIB(new Date(it.ts * 1000).toISOString())}</span>
								</span>
							</a>
						</li>
					{/each}
				</ul>
			{:else}
				<EmptyState
					judul="Belum ada berita"
					pesan={news?.sumber_data ?? 'Feed belum mengirim item.'}
					onulang={muat}
					aksilabel="Muat ulang"
					ringkas
				/>
			{/if}
		</section>
	{/if}
</div>

<style>
	.berita {
		display: flex;
		flex-direction: column;
		gap: var(--grid-gap);
	}
	.kepala h1 {
		margin: 0;
		font-family: var(--font-display);
		font-size: var(--text-26);
		font-weight: 700;
		letter-spacing: -0.02em;
	}
	.kepala p {
		margin: 0.15rem 0 0;
		font-size: var(--text-13);
	}
	.kartu {
		background: var(--color-surface);
		border: 1px solid var(--color-line);
		border-radius: var(--radius-card);
		padding: var(--card-pad);
	}
	.judul {
		margin: 0 0 0.6rem;
		font-size: var(--text-14);
		font-weight: 700;
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		gap: 0.6rem;
		flex-wrap: wrap;
	}
	.daftar {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
	}
	.daftar li {
		border-bottom: 1px solid var(--color-line-soft);
	}
	.daftar li:last-child {
		border-bottom: 0;
	}
	.daftar a {
		display: flex;
		flex-direction: column;
		gap: 0.2rem;
		padding: 0.55rem 0.35rem;
		text-decoration: none;
		color: var(--color-text);
		border-radius: var(--radius-control);
		transition: background-color 160ms var(--ease-out);
	}
	.daftar a:hover {
		background: var(--color-surface-2);
	}
	.daftar a:focus-visible {
		outline: var(--focus-ring);
		outline-offset: 2px;
	}
	.judul-item {
		font-size: var(--text-14);
		font-weight: 500;
		line-height: 1.4;
	}
	.daftar a:hover .judul-item {
		color: var(--color-accent);
	}
	.meta {
		display: flex;
		gap: 0.75rem;
		font-size: var(--text-11);
		flex-wrap: wrap;
	}
	.sumber {
		color: var(--color-accent);
		font-weight: 600;
	}
	.dim {
		color: var(--color-text-3);
		font-weight: 400;
	}
	.angka {
		font-family: var(--font-mono);
		font-variant-numeric: tabular-nums;
	}
</style>
