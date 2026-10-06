<script lang="ts">
	// NavInfo — strip navigasi untuk empat halaman penjelas (Catatan, Berita,
	// Cara kerja, Bantuan). Mereka rute TERPISAH (bukan tab `?sub=`), jadi SubNav
	// tidak cocok. Tanpa komponen ini, tiga dari empat halaman jadi yatim: ada
	// rutenya, tapi tak ada jalan menuju ke sana dari UI.
	import { page } from '$app/state';

	const tautan = [
		{ rute: '/catatan', label: 'Catatan' },
		{ rute: '/berita', label: 'Berita' },
		{ rute: '/cara-kerja', label: 'Cara kerja' },
		{ rute: '/bantuan', label: 'Bantuan' }
	];
	const aktif = $derived(page.url.pathname.replace(/\/$/, '') || '/');
</script>

<nav class="nav-info" aria-label="Navigasi Info">
	{#each tautan as t (t.rute)}
		<a href={t.rute} class="tautan" class:aktif={aktif === t.rute} aria-current={aktif === t.rute ? 'page' : undefined}>
			{t.label}
		</a>
	{/each}
</nav>

<style>
	.nav-info {
		display: flex;
		gap: 0.3rem;
		flex-wrap: wrap;
	}
	.tautan {
		padding: 0.3rem 0.7rem;
		border-radius: var(--radius-control);
		border: 1px solid var(--color-line);
		font-size: var(--text-12);
		font-weight: 500;
		color: var(--color-text-3);
		text-decoration: none;
		transition: color 160ms var(--ease-out), border-color 160ms var(--ease-out);
	}
	.tautan:hover {
		color: var(--color-text);
		border-color: var(--color-line-soft);
	}
	.tautan.aktif {
		color: var(--color-accent);
		border-color: color-mix(in srgb, var(--color-accent) 45%, transparent);
		background: color-mix(in srgb, var(--color-accent) 10%, transparent);
		font-weight: 600;
	}
</style>
