<script lang="ts">
	// Pemuat area: satu tempat untuk state memuat/galat/kosong + polling fallback 15 dtk
	// ketika SSE putus. Anak menerima payload mentah dari API.
	import type { Snippet } from 'svelte';
	import type { AreaPayload } from '$lib/api/types';
	import { getArea } from '$lib/api/client';
	import Skeleton from './Skeleton.svelte';
	import ErrorState from './ErrorState.svelte';
	import EmptyState from './EmptyState.svelte';

	interface Props {
		area: string;
		intervalMs?: number;
		/** Laporkan status pemuatan ke induk (untuk honesty-tag header). */
		onstatus?: (status: 'memuat' | 'ok' | 'galat') => void;
		children: Snippet<[AreaPayload]>;
	}
	let { area, intervalMs = 15000, onstatus, children }: Props = $props();

	let data = $state<AreaPayload | null>(null);
	let galat = $state<string | null>(null);
	let memuat = $state(true);

	async function muat() {
		try {
			data = await getArea(area);
			galat = null;
			onstatus?.('ok');
		} catch (e) {
			galat = e instanceof Error ? e.message : String(e);
			onstatus?.('galat');
		} finally {
			memuat = false;
		}
	}

	$effect(() => {
		// `area` dibaca sengaja: ganti area → ganti basis data, bukan menumpuk.
		const a = area;
		memuat = true;
		void a;
		void muat();
		const t = setInterval(() => void muat(), intervalMs);
		return () => clearInterval(t);
	});
</script>

{#if memuat && !data}
	<Skeleton baris={8} />
{:else if galat && !data}
	<ErrorState pesan={galat} onulang={muat} />
{:else if data && !data.dikenal}
	<EmptyState
		judul="Area tidak dikenal"
		pesan={`API tidak mengenal area “${area}”.`}
		langkah={data.areas?.length ? `Area yang ada: ${data.areas.join(', ')}` : null}
	/>
{:else if data}
	{#if galat}
		<p class="mb-2 text-12 text-warn" role="status">
			refresh terakhir gagal: {galat}, menampilkan data terakhir.
		</p>
	{/if}
	{@render children(data)}
{/if}