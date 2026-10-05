<script lang="ts">
	// MoneyStrip: Bar status ekuitas 3 segmen (Nyata / Paper / Warisan).
	// Didesain elegan, ringkas, dan selaras dengan tema War Room.
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
		{
			kunci: 'nyata',
			label: 'Nyata',
			warna: 'text-live',
			titik: 'titik-live',
			s: nyata,
			kosong: 'belum ada dana terverifikasi on-chain'
		},
		{
			kunci: 'paper',
			label: 'Paper',
			warna: 'text-paper',
			titik: 'titik-paper',
			s: paper,
			kosong: 'sumber paper belum mengirim angka'
		},
		{
			kunci: 'warisan',
			label: 'Warisan',
			warna: 'text-inherit',
			titik: 'titik-inherit',
			s: warisan,
			kosong: 'angka UI lama belum diimpor ke API'
		}
	]);
</script>

<div
	class="flex flex-wrap items-center gap-2"
	data-testid="money-strip"
	aria-label="pemisah uang: nyata, paper, warisan"
>
	{#each segmen as g (g.kunci)}
		<div
			class="rounded-control bg-surface border border-line px-2.5 py-1 flex items-baseline gap-2 text-11 shadow-sm"
			data-segmen={g.kunci}
		>
			<div class="flex items-center gap-1.5">
				<!-- Penanda jenis uang: titik berwarna, bukan border kiri tebal.
				     Border kiri = penanda paling khas UI hasil AI, dan di sini justru
				     dipakai untuk hal yang penting (nyata vs paper vs warisan). -->
				<span class="titik {g.titik}" aria-hidden="true"></span>
				<span class="label-mikro font-bold {g.warna}">{g.label}</span>
				<FreshnessBadge status={g.s?.status ?? null} age_s={g.s?.age_s ?? null} source={g.s?.sumber ?? null} ringkas />
			</div>

			<div class="flex items-baseline gap-1">
				<span class="angka text-13 font-bold text-text">
					{#if g.s && g.s.nilai !== null && g.s.nilai !== undefined}
						{angka(g.s.nilai)}{#if g.s.satuan}<span class="text-10 text-text-3 font-mono"> {g.s.satuan}</span>{/if}
					{:else}
						—
					{/if}
				</span>

				{#if !ringkas}
					<span class="text-10 text-text-3 truncate max-w-[130px]">
						{#if g.s && g.s.nilai !== null && g.s.nilai !== undefined}
							{g.s.sumber ? `${g.s.sumber}` : ''}{#if g.s.age_s != null} · {umurDetik(g.s.age_s)}{/if}
						{:else}
							{g.s?.keterangan ?? g.kosong}
						{/if}
					</span>
				{/if}
			</div>
		</div>
	{/each}
</div>

<style>
	/* Titik penanda jenis uang. Bentuknya ikut membedakan, bukan hanya warna —
	   supaya tetap terbaca oleh pengguna yang sulit membedakan warna. */
	.titik {
		width: 7px;
		height: 7px;
		flex: 0 0 auto;
		display: inline-block;
	}
	.titik-live {
		background: var(--live);
		border-radius: 1px;
	}
	.titik-paper {
		background: var(--paper);
		border-radius: 50%;
	}
	.titik-inherit {
		background: transparent;
		border: 1.5px solid var(--inherit);
		border-radius: 50%;
	}
</style>