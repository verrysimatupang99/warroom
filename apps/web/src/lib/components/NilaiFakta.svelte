<script lang="ts">
	// Render satu fakta secara generik: angka → ubin, array/objek-of-objek → tabel, sisanya →
	// nilai mentah di drawer. Tidak ada nilai turunan yang dikarang.
	import type { Fact } from '$lib/api/types';
	import { tilesDari, tabelDari, seriDari, ringkasNilai } from '$lib/nilai';
	import { waktuWIB } from '$lib/format';
	import MetricTile from './MetricTile.svelte';
	import DataTable from './DataTable.svelte';
	import Drawer from './Drawer.svelte';

	interface Props {
		fakta: Fact;
		filterKunci?: string;
	}
	let { fakta, filterKunci }: Props = $props();

	const tiles = $derived.by(() => {
		const raw = tilesDari(fakta.value);
		if (!filterKunci || fakta.key !== 'bagian') return raw;
		return raw.filter((t) => t.jalur.toLowerCase().startsWith(filterKunci.toLowerCase()));
	});

	const tabel = $derived.by(() => {
		const raw = tabelDari(fakta.value);
		if (!filterKunci || fakta.key !== 'bagian') return raw;
		return raw.filter((t) => {
			const j = t.judul.toLowerCase();
			if (filterKunci === 'idx') return j.includes('idx') || j.includes('bandar') || j.includes('arjum');
			if (filterKunci === 'crypto') return j.includes('crypto');
			if (filterKunci === 'forex') return j.includes('forex') || j.includes('macro');
			if (filterKunci === 'gmgn') return j.includes('gmgn') || j.includes('memecoin') || j.includes('radar');
			return j.includes(filterKunci.toLowerCase());
		});
	});

	const seri = $derived(seriDari(fakta.key, fakta.value));
	const kosong = $derived(tiles.length === 0 && tabel.length === 0);
	let drawer = $state(false);
</script>

<div>
	{#if tiles.length}
		<div class="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
			{#each tiles as t, i (t.jalur)}
				<MetricTile
					label={t.label}
					nilai={t.nilai}
					seri={i === 0 && seri.length >= 2 ? seri : null}
					sumber={fakta.source}
					age_s={fakta.age_s}
					status={fakta.status}
				/>
			{/each}
		</div>
	{/if}

	{#each tabel as t (t.judul)}
		<div class="mt-3">
			<p class="label-mikro mb-1">{t.judul}</p>
			<DataTable
				kolom={t.kolom}
				baris={t.baris}
				cari={`cari di ${t.judul}…`}
				ekspor={`${fakta.key}-${t.judul}.csv`}
				padat
			/>
		</div>
	{/each}

	{#if kosong}
		<p class="text-13 text-text-2">
			Nilai ada tetapi tidak berbentuk angka atau tabel — bukan nol, hanya bentuk lain:
		</p>
		<pre class="angka mt-1 max-h-40 overflow-auto rounded-control border border-line bg-surface-2 p-2 text-12 whitespace-pre-wrap">{ringkasNilai(
				fakta.value
			).slice(0, 600)}</pre>
	{/if}

	<button
		type="button"
		class="target-44 transisi mt-2 rounded-control border border-line px-3 text-12 text-text-3 hover:border-accent-2 hover:text-text"
		onclick={() => (drawer = true)}
	>
		Lihat nilai mentah
	</button>

	<Drawer
		terbuka={drawer}
		judul={`${fakta.kind}/${fakta.key}`}
		ontutup={() => (drawer = false)}
	>
		<pre class="angka text-12 whitespace-pre-wrap">{ringkasNilai(fakta.value)}</pre>
		<p class="mt-3 text-12 text-text-3">
			fact_id <span class="angka">{fakta.fact_id}</span> · sumber <span class="angka"
				>{fakta.source}</span
			> · {waktuWIB(fakta.observed_at)} · TTL <span class="angka">{fakta.ttl_s}s</span> · status
			{fakta.status}
		</p>
	</Drawer>
</div>