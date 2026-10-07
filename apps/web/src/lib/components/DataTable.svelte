<script lang="ts">
	// Tabel data: sort per kolom, filter teks, ekspor CSV. Header memakai <button> supaya
	// keyboard penuh dan `aria-sort` jujur soal arah urutan.
	import { keCSV, teksNilai, unduhTeks, bulat } from '$lib/format';
	import EmptyState from './EmptyState.svelte';

	export interface KolomTabel {
		kunci: string;
		label: string;
		numerik?: boolean;
	}

	interface Props {
		kolom: KolomTabel[];
		baris: Record<string, unknown>[];
		/** placeholder pencarian; null = sembunyikan kotak cari */
		cari?: string | null;
		/** nama berkas ekspor; null = sembunyikan tombol */
		ekspor?: string | null;
		padat?: boolean;
		kosongPesan?: string;
	}
	let {
		kolom,
		baris,
		cari = 'cari…',
		ekspor = null,
		padat = false,
		kosongPesan = 'Tidak ada baris untuk filter ini.'
	}: Props = $props();

	let kueri = $state('');
	let urut = $state<string | null>(null);
	let naik = $state(true);

	const terlihat = $derived.by(() => {
		const q = kueri.trim().toLowerCase();
		let r = q
			? baris.filter((b) => kolom.some((k) => teksNilai(b[k.kunci]).toLowerCase().includes(q)))
			: baris;
		if (urut) {
			const k = kolom.find((c) => c.kunci === urut);
			const arah = naik ? 1 : -1;
			r = [...r].sort((a, b) => {
				const va = a[urut as string];
				const vb = b[urut as string];
				const na = typeof va === 'number';
				const nb = typeof vb === 'number';
				if (k?.numerik || (na && nb)) {
					const fa = na ? (va as number) : Number(va);
					const fb = nb ? (vb as number) : Number(vb);
					const xa = Number.isFinite(fa) ? fa : -Infinity;
					const xb = Number.isFinite(fb) ? fb : -Infinity;
					return (xa - xb) * arah;
				}
				return teksNilai(va).localeCompare(teksNilai(vb), 'id') * arah;
			});
		}
		return r;
	});

	function toggel(kunci: string) {
		if (urut === kunci) naik = !naik;
		else {
			urut = kunci;
			naik = true;
		}
	}

	function eksporSekarang() {
		if (!ekspor) return;
		const kepala = kolom.map((k) => k.label);
		const isi = terlihat.map((b) => kolom.map((k) => b[k.kunci]));
		unduhTeks(ekspor, keCSV(kepala, isi));
	}

	const ariaUrut = (kunci: string) =>
		urut === kunci ? (naik ? 'ascending' : 'descending') : ('none' as const);
</script>

<div class="w-full">
	<div class="mb-2 flex flex-wrap items-center gap-2">
		{#if cari !== null}
			<label class="flex items-center gap-2">
				<span class="label-mikro">Filter</span>
				<input
					type="search"
					bind:value={kueri}
					placeholder={cari}
					class="target-44 angka rounded-control border border-line bg-surface-2 px-2 text-13 text-text placeholder:text-text-3"
				/>
			</label>
		{/if}
		<span class="angka text-12 text-text-3">{bulat(terlihat.length)}/{bulat(baris.length)} baris</span>
		{#if ekspor}
			<button
				type="button"
				class="target-44 transisi ml-auto rounded-control border border-line px-3 text-13 text-text-2 hover:border-accent-2 hover:text-text"
				onclick={eksporSekarang}
			>
				Ekspor CSV
			</button>
		{/if}
	</div>

	{#if baris.length === 0}
		<EmptyState judul="Tabel kosong" pesan={kosongPesan} ringkas />
	{:else}
		<div class="overflow-auto rounded-control border border-line">
			<table class="w-full border-collapse text-13">
				<thead>
					<tr class="bg-surface-2">
						{#each kolom as k (k.kunci)}
							<th
								scope="col"
								aria-sort={ariaUrut(k.kunci)}
								class="sticky top-0 z-10 border-b border-line bg-surface-2 p-0 text-left"
							>
								<!-- Temuan pemindai aksesibilitas (QA 7 Okt): kolom berlabel "#" membuat
								     nama aksesibel tombol hanya "# ↕" — pembaca layar tidak tahu ini
								     tombol URUT. aria-label menyebut fungsi + keadaan + kolomnya. -->
								<button
									type="button"
									class="label-mikro transisi flex min-h-[44px] w-full items-center gap-1 px-2 hover:text-text"
									aria-label={`urutkan berdasarkan ${k.label || k.kunci}${
										urut === k.kunci ? (naik ? ' (menaik)' : ' (menurun)') : ''
									}`}
									onclick={() => toggel(k.kunci)}
								>
									{k.label}
									<span aria-hidden="true" class="text-accent-2">
										{#if urut === k.kunci}{naik ? '▲' : '▼'}{:else}↕{/if}
									</span>
								</button>
							</th>
						{/each}
					</tr>
				</thead>
				<tbody>
					{#each terlihat as b, i (i)}
						<tr class="border-b border-line-soft last:border-0 hover:bg-surface-2/60">
							{#each kolom as k (k.kunci)}
								{@const t = teksNilai(b[k.kunci])}
								<td
									class="px-2 {padat ? 'py-1' : 'py-2'} {k.numerik
										? 'angka text-right'
										: 'max-w-[38ch] break-words text-text-2'}"
									title={t.length > 90 ? t : undefined}
								>
									{t.length > 90 ? t.slice(0, 90) + '…' : t}
								</td>
							{/each}
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
</div>