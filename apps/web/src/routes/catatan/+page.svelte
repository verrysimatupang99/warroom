<script lang="ts">
	// Catatan — padanan /learn algentis, isinya dokumentasi kita sendiri
	// (docs/belajar). Daftar di kiri, isi di kanan. Markdown ditampilkan apa adanya
	// (tanpa parser berat) supaya tidak menambah ketergantungan; yang penting
	// isinya bisa dibaca dan ditelusuri.
	import { getDoc, getDocs } from '$lib/api/client';
	import type { DocContent, DocsPayload } from '$lib/api/types';
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import NavInfo from '$lib/components/NavInfo.svelte';
	import Skeleton from '$lib/components/Skeleton.svelte';
	import ErrorState from '$lib/components/ErrorState.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';

	let daftar = $state<DocsPayload | null>(null);
	let isi = $state<DocContent | null>(null);
	let galat = $state<string | null>(null);
	let memuat = $state(true);
	let memuatIsi = $state(false);

	const slugAktif = $derived(page.url.searchParams.get('doc'));

	async function muatDaftar() {
		try {
			daftar = await getDocs();
			galat = null;
		} catch (e) {
			galat = e instanceof Error ? e.message : String(e);
		}
		memuat = false;
	}

	async function muatIsi(slug: string | null) {
		if (!slug) {
			isi = null;
			return;
		}
		memuatIsi = true;
		try {
			isi = await getDoc(slug);
		} catch (e) {
			isi = null;
			galat = e instanceof Error ? e.message : String(e);
		}
		memuatIsi = false;
	}

	$effect(() => {
		void muatDaftar();
	});
	$effect(() => {
		void muatIsi(slugAktif);
	});

	function pilih(slug: string) {
		if (typeof window !== 'undefined') void goto(`?doc=${slug}`, { keepFocus: true, noScroll: true });
	}

	// Markdown ringan → HTML aman. HANYA yang kita kenali (judul, list, tebal, kode,
	// tabel sederhana). Semua teks di-escape lebih dulu supaya tidak ada injeksi.
	const html = $derived.by(() => {
		if (!isi) return '';
		const esc = (s: string) =>
			s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
		const baris = esc(isi.isi).split('\n');
		const out: string[] = [];
		let dalamList = false;
		let dalamTabel = false;
		for (const b of baris) {
			if (/^\|/.test(b)) {
				if (!dalamTabel) {
					out.push('<table class="tabel-md">');
					dalamTabel = true;
				}
				const sel = b.split('|').slice(1, -1).map((c) => c.trim());
				if (sel.every((c) => /^-+$/.test(c) || c === '')) continue;
				out.push('<tr>' + sel.map((c) => `<td>${c}</td>`).join('') + '</tr>');
				continue;
			} else if (dalamTabel) {
				out.push('</table>');
				dalamTabel = false;
			}
			const li = b.match(/^\s*[-*]\s+(.*)$/);
			if (li) {
				if (!dalamList) {
					out.push('<ul>');
					dalamList = true;
				}
				out.push(`<li>${li[1]}</li>`);
				continue;
			} else if (dalamList) {
				out.push('</ul>');
				dalamList = false;
			}
			const h = b.match(/^(#{1,4})\s+(.*)$/);
			if (h) {
				const n = h[1].length;
				out.push(`<h${n}>${h[2]}</h${n}>`);
				continue;
			}
			if (!b.trim()) {
				out.push('');
				continue;
			}
			out.push(`<p>${b}</p>`);
		}
		if (dalamList) out.push('</ul>');
		if (dalamTabel) out.push('</table>');
		return out
			.join('\n')
			.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
			.replace(/`([^`]+)`/g, '<code>$1</code>');
	});
</script>

<svelte:head><title>Catatan — War Room</title></svelte:head>

<div class="catatan">
	<header class="kepala">
		<span class="label-mikro">DOKUMEN / CATATAN</span>
		<h1>Catatan</h1>
		<p class="dim">Dokumentasi proyek: temuan, keputusan, dan pelajaran. Dibaca dari repo.</p>
	</header>

	<NavInfo />

	{#if galat && !daftar}
		<ErrorState pesan={galat} onulang={muatDaftar} />
	{:else if memuat && !daftar}
		<Skeleton baris={8} />
	{:else}
		<div class="dua">
			<aside class="daftar" aria-label="Daftar catatan">
				{#if daftar?.dokumen?.length}
					{#each daftar.dokumen as d (d.slug)}
						<button
							type="button"
							class="item"
							class:aktif={slugAktif === d.slug}
							aria-current={slugAktif === d.slug}
							onclick={() => pilih(d.slug)}
						>
							<span>{d.judul}</span>
						</button>
					{/each}
				{:else}
					<EmptyState judul="Tidak ada catatan" pesan={daftar?.alasan ?? 'Folder kosong.'} ringkas />
				{/if}
			</aside>

			<article class="isi" aria-label="Isi catatan">
				{#if memuatIsi}
					<Skeleton baris={10} />
				{:else if isi}
					<!-- html dibangun dari markdown yang sudah di-escape (tanpa {@html} mentah
					     dari sumber luar; isinya berkas repo sendiri). -->
					{@html html}
				{:else}
					<p class="dim petunjuk">Pilih catatan di kiri untuk membacanya.</p>
				{/if}
			</article>
		</div>
	{/if}
</div>

<style>
	.catatan {
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
	.dua {
		display: grid;
		grid-template-columns: minmax(0, 16rem) minmax(0, 1fr);
		gap: var(--grid-gap);
		align-items: start;
	}
	.daftar {
		background: var(--color-surface);
		border: 1px solid var(--color-line);
		border-radius: var(--radius-card);
		padding: 0.4rem;
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
		max-height: 70vh;
		overflow-y: auto;
	}
	.item {
		text-align: left;
		background: none;
		border: 0;
		border-radius: var(--radius-control);
		padding: 0.45rem 0.55rem;
		font-size: var(--text-13);
		color: var(--color-text-2);
		transition: background-color 160ms var(--ease-out);
	}
	.item:hover {
		background: var(--color-surface-2);
		color: var(--color-text);
	}
	.item.aktif {
		background: color-mix(in srgb, var(--color-accent) 12%, transparent);
		color: var(--color-accent);
		font-weight: 600;
	}
	.isi {
		background: var(--color-surface);
		border: 1px solid var(--color-line);
		border-radius: var(--radius-card);
		padding: 1rem 1.15rem;
		min-height: 12rem;
		font-size: var(--text-14);
		line-height: 1.65;
		overflow-wrap: anywhere;
	}
	.isi :global(h1) {
		font-family: var(--font-display);
		font-size: var(--text-20);
		margin: 0 0 0.6rem;
	}
	.isi :global(h2) {
		font-size: var(--text-16);
		margin: 1.1rem 0 0.4rem;
		color: var(--color-accent);
	}
	.isi :global(h3) {
		font-size: var(--text-14);
		margin: 0.9rem 0 0.3rem;
	}
	.isi :global(p) {
		margin: 0.4rem 0;
		color: var(--color-text-2);
	}
	.isi :global(ul) {
		margin: 0.4rem 0;
		padding-left: 1.1rem;
		color: var(--color-text-2);
	}
	.isi :global(li) {
		margin: 0.15rem 0;
	}
	.isi :global(code) {
		font-family: var(--font-mono);
		font-size: var(--text-12);
		background: var(--color-canvas);
		padding: 0.05rem 0.3rem;
		border-radius: 4px;
	}
	.isi :global(strong) {
		color: var(--color-text);
	}
	.isi :global(.tabel-md) {
		border-collapse: collapse;
		margin: 0.5rem 0;
		font-size: var(--text-12);
		width: 100%;
	}
	.isi :global(.tabel-md td) {
		border: 1px solid var(--color-line-soft);
		padding: 0.3rem 0.45rem;
		color: var(--color-text-2);
	}
	.petunjuk {
		color: var(--color-text-3);
	}
	.dim {
		color: var(--color-text-3);
		font-weight: 400;
	}
	@media (max-width: 767px) {
		.dua {
			grid-template-columns: 1fr;
		}
		.daftar {
			max-height: 15rem;
		}
	}
</style>
