<script lang="ts">
	// Ubin metrik: label mikro + angka besar mono + delta + sparkline opsional.
	// Nilai hilang → `—` + alasan (tidak pernah 0).
	import { angka, umurDetik } from '$lib/format';
	import Sparkline from './Sparkline.svelte';
	import FreshnessBadge from './FreshnessBadge.svelte';

	interface Props {
		label: string;
		nilai: unknown;
		desimal?: number;
		satuan?: string | null;
		delta?: number | null;
		seri?: number[] | null;
		sumber?: string | null;
		age_s?: number | null;
		status?: string | null;
		alasanKosong?: string;
		warna?: string;
	}
	let {
		label,
		nilai,
		desimal = 2,
		satuan = null,
		delta = null,
		seri = null,
		sumber = null,
		age_s = null,
		status = null,
		alasanKosong = 'Sumber belum mengirim nilai ini.',
		warna = 'var(--color-accent-2)'
	}: Props = $props();

	const adaNilai = $derived(nilai !== null && nilai !== undefined && nilai !== '');
	const n = $derived(adaNilai ? Number(nilai) : null);
	const sah = $derived(n !== null && Number.isFinite(n));
	const nada = $derived(delta == null ? '' : delta >= 0 ? 'text-pos' : 'text-neg');
</script>

<div class="kartu transisi p-3" data-testid="metric-tile">
	<div class="flex items-start justify-between gap-2">
		<p class="label-mikro">{label}</p>
		<FreshnessBadge {status} {age_s} source={sumber} ringkas />
	</div>
	<div class="mt-1 flex items-end gap-2">
		<span class="angka text-26 text-text" aria-live="polite">
			{#if sah}{angka(n, { desimal })}{:else}—{/if}
		</span>
		{#if satuan}<span class="angka text-12 text-text-3">{satuan}</span>{/if}
		{#if delta != null}
			<span class="angka text-12 {nada}" title="perubahan"> {delta >= 0 ? '▲' : '▼'}
				{angka(Math.abs(delta), { desimal })}</span
			>
		{/if}
		<div class="ml-auto"><Sparkline {seri} {warna} judul={`seri ${label}`} /></div>
	</div>
	<p class="mt-1 text-11 text-text-3">
		{#if !sah}{alasanKosong}{:else if sumber}sumber: <span class="angka">{sumber}</span>{:else}—{/if}
		{#if sah && age_s != null}· umur {umurDetik(age_s)}{/if}
	</p>
</div>