<script lang="ts">
	// MoneyStrip: 3 segmen PERMANEN — Nyata / Paper / Warisan. Warna tetap (live/paper/inherit)
	// dan tidak pernah dicampur; nilai hilang → `—` + alasan, bukan 0.
	import { angka, umurDetik } from '$lib/format';
	import type { SegmenUang } from '$lib/uang';
	import FreshnessBadge from './FreshnessBadge.svelte';

	interface Props {
		nyata?: SegmenUang | null;
		paper?: SegmenUang | null;
		warisan?: SegmenUang | null;
		ringkas?: boolean;
	}
	let { nyata = null, paper = null, warisan = null, ringkas = false }: Props = $props();

	const segmen = $derived([
		{ kunci: 'nyata', label: 'Nyata', warna: 'var(--color-live)', border: 'border-l-live', s: nyata, kosong: 'belum ada dana terverifikasi on-chain' },
		{ kunci: 'paper', label: 'Paper', warna: 'var(--color-paper)', border: 'border-l-paper', s: paper, kosong: 'sumber paper belum mengirim angka' },
		{ kunci: 'warisan', label: 'Warisan', warna: 'var(--color-inherit)', border: 'border-l-inherit', s: warisan, kosong: 'angka UI lama belum diimpor ke API' }
	]);
</script>

<div class="flex flex-wrap gap-2" data-testid="money-strip" aria-label="pemisah uang: nyata, paper, warisan">
	{#each segmen as g (g.kunci)}
		<div
			class="permukaan-2 flex min-w-[9rem] flex-col gap-0.5 border-l-2 px-2 py-1 {g.border}"
			data-segmen={g.kunci}
		>
			<div class="flex items-center justify-between gap-2">
				<span class="label-mikro" style={`color:${g.warna}`}>{g.label}</span>
				<FreshnessBadge status={g.s?.status ?? null} age_s={g.s?.age_s ?? null} source={g.s?.sumber ?? null} ringkas />
			</div>
			<span class="angka text-15 text-text">
				{#if g.s && g.s.nilai !== null && g.s.nilai !== undefined}
					{angka(g.s.nilai)}{#if g.s.satuan}<span class="text-11 text-text-3"> {g.s.satuan}</span>{/if}
				{:else}
					—
				{/if}
			</span>
			{#if !ringkas}
				<span class="text-11 text-text-3">
					{#if g.s && g.s.nilai !== null && g.s.nilai !== undefined}
						{g.s.sumber ? `sumber ${g.s.sumber}` : 'sumber —'}{#if g.s.age_s != null} · {umurDetik(g.s.age_s)}{/if}
					{:else}
						{g.s?.keterangan ?? g.kosong}
					{/if}
				</span>
			{/if}
		</div>
	{/each}
</div>