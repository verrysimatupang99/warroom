<script lang="ts">
	// NavBar — navigasi horizontal (rombak total 6 Okt 2026).
	//
	// Menggantikan rail kiri 240px. Alasan: rail memakan 1/6 lebar layar untuk
	// 7 tautan, dan di lebar sedang ia terpaksa bertumpuk sehingga Home dan halaman
	// area terlihat seperti dua produk berbeda. Navigasi horizontal membebaskan
	// seluruh lebar untuk data (panduan data-dense: maksimalkan visibilitas data)
	// dan menyamakan tata letak di semua lebar.
	import { page } from '$app/state';
	import { AREAS, areaDariJalur } from '$lib/nav';

	const aktif = $derived(areaDariJalur(page.url.pathname));
	import Ikon from './Ikon.svelte';
</script>

<nav class="navbar" aria-label="Navigasi area">
	<div class="gulir">
		{#each AREAS as a (a.kunci)}
			{@const ini = aktif?.kunci === a.kunci}
			<a
				href={a.rute}
				class="tautan"
				class:aktif={ini}
				aria-current={ini ? 'page' : undefined}
				title={a.anak.map((x) => x.label).join(' · ')}
			>
				<span class="ikon"><Ikon nama={a.ikon} ukuran={15} /></span>
				<span>{a.label}</span>
			</a>
		{/each}
	</div>
</nav>

<style>
	.navbar {
		position: sticky;
		top: 2.35rem;
		z-index: 20;
		border-bottom: 1px solid var(--color-line);
		background: color-mix(in srgb, var(--color-bg) 84%, transparent);
	}
	/* Di ponsel nav-horizontal DISEMBUNYIKAN: BottomNav sudah jadi navigasi
	   ponsel yang benar. Menampilkan keduanya = dua navigasi untuk 7 tautan
	   yang sama (temuan 6 Okt). Muncul mulai >=768px. */
	@media (max-width: 767px) {
		.navbar {
			display: none;
		}
	}
	.gulir {
		display: flex;
		gap: 0.15rem;
		padding: 0.3rem 0.6rem;
		overflow-x: auto;
		scrollbar-width: none;
	}
	.gulir::-webkit-scrollbar {
		display: none;
	}
	.tautan {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		/* Target sentuh ≥44 px (audit QA 7 Okt: "top navigation sekitar 32 px tinggi").
		   Ikon boleh kecil, AREA KLIK-nya yang harus besar. */
		min-height: 44px;
		padding: 0.35rem 0.75rem;
		border-radius: var(--radius-control);
		font-size: var(--text-13);
		font-weight: 500;
		color: var(--color-text-3);
		text-decoration: none;
		white-space: nowrap;
		border: 1px solid transparent;
		transition: color 160ms var(--ease-out), background-color 160ms var(--ease-out), border-color 160ms var(--ease-out), box-shadow 160ms var(--ease-out);
	}
	.tautan:hover {
		color: var(--color-text);
		background: var(--color-surface-2);
		border-color: var(--color-line-soft);
	}
	.tautan.aktif {
		color: var(--color-accent);
		background: color-mix(in srgb, var(--color-accent) 14%, transparent);
		border-color: color-mix(in srgb, var(--color-accent) 30%, transparent);
		/* Glow aksen dihapus (FLAT, design 16 Okt). */
		font-weight: 600;
	}
	.ikon {
		font-size: var(--text-14);
		opacity: 0.9;
	}
</style>
