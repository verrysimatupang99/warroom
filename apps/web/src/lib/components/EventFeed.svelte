<script lang="ts">
	// Feed kejadian bertipe dengan filter. Waktu ditampilkan WIB; payload dipadatkan.
	import type { Kejadian } from '$lib/api/types';
	import { teksNilai, waktuWIB } from '$lib/format';
	import EmptyState from './EmptyState.svelte';
	import Skeleton from './Skeleton.svelte';

	interface Props {
		kejadian: Kejadian[];
		memuat?: boolean;
		galat?: string | null;
		onulang?: (() => void) | null;
		prefiksAwal?: string[];
	}
	let { kejadian, memuat = false, galat = null, onulang = null, prefiksAwal = [] }: Props = $props();

	// `prefiksAwal` dibaca sekali saat mount sebagai nilai awal filter. `$props()`
	// sudah non-reaktif untuk pembacaan di top-level; `structuredClone` memutus
	// rujukan supaya Svelte tidak memperingatkan penangkapan nilai reaktif lokal.
	const awal: string[] = JSON.parse(JSON.stringify(prefiksAwal ?? []));
	let pilih = $state<string[]>(awal);

	const grup = $derived.by(() => {
		const s = new Set<string>();
		for (const k of kejadian) s.add(k.type.split('.')[0] || k.type);
		return [...s].sort();
	});
	const terlihat = $derived(
		pilih.length ? kejadian.filter((k) => pilih.includes(k.type.split('.')[0] || k.type)) : kejadian
	);

	function toggel(g: string) {
		pilih = pilih.includes(g) ? pilih.filter((x) => x !== g) : [...pilih, g];
	}

	const warnaSev = (sev: string | null) =>
		sev === 'error' || sev === 'critical'
			? 'text-neg border-neg/40'
			: sev === 'warn' || sev === 'warning'
				? 'text-warn border-warn/40'
				: 'text-text-3 border-line';
</script>

<div>
	{#if grup.length > 1}
		<!-- Filter hanya muncul bila ada LEBIH DARI SATU tipe. Sebelumnya selalu dirender;
		     saat feed cuma memuat satu tipe (umum di panel area), tombolnya tak bisa
		     mengubah apa pun — pemilik membacanya sebagai "3 tombol tidak berfungsi". -->
		<div class="mb-2 flex flex-wrap gap-1" role="group" aria-label="Filter tipe kejadian">
			<button
				type="button"
				class="label-mikro transisi min-h-[44px] rounded-control border px-2 {pilih.length === 0
					? 'border-accent-2 text-accent-2'
					: 'border-line text-text-3 hover:text-text'}"
				aria-pressed={pilih.length === 0}
				onclick={() => (pilih = [])}
			>
				semua
			</button>
			{#each grup as g (g)}
				<button
					type="button"
					class="label-mikro transisi min-h-[44px] rounded-control border px-2 {pilih.includes(g)
						? 'border-accent-2 text-accent-2'
						: 'border-line text-text-3 hover:text-text'}"
					aria-pressed={pilih.includes(g)}
					onclick={() => toggel(g)}
				>
					{g}
				</button>
			{/each}
		</div>
	{/if}

	{#if galat}
		<div class="rounded-control border border-neg/40 bg-neg/10 p-3" role="alert">
			<p class="text-13 text-text">{galat}</p>
			{#if onulang}
				<button
					type="button"
					class="target-44 transisi mt-2 rounded-control border border-line px-3 text-13 hover:border-accent-2"
					onclick={() => onulang?.()}>Coba lagi</button
				>
			{/if}
		</div>
	{:else if memuat && kejadian.length === 0}
		<Skeleton baris={4} />
	{:else if terlihat.length === 0}
		<EmptyState
			judul="Belum ada kejadian"
			pesan="Feed kosong: belum ada event yang cocok dengan filter ini."
			ringkas
		/>
	{:else}
		<ol class="space-y-1" aria-live="polite">
			{#each terlihat.slice(0, 40) as k (k.id)}
				<li class="flex items-start gap-2 rounded-control border border-line-soft bg-surface-2/40 p-2">
					<span class="angka shrink-0 text-11 text-text-3">{k.id}</span>
					<span class="label-mikro shrink-0 rounded-control border px-1 {warnaSev(k.severity)}">
						{k.type}
					</span>
					<span class="min-w-0 flex-1 text-12 text-text-2">
						<span class="angka">{teksNilai(k.payload).slice(0, 160)}</span>
					</span>
					<span class="angka shrink-0 text-11 text-text-3">{waktuWIB(k.created_at)}</span>
				</li>
			{/each}
		</ol>
	{/if}
</div>