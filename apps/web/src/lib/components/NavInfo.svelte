<script lang="ts">
	// NavInfo — strip navigasi untuk empat halaman penjelas (Catatan, Berita,
	// Cara kerja, Bantuan) diselaraskan dengan ritme dan styling SubNav terpadu.
	import { page } from '$app/state';

	const tautan = [
		{ rute: '/catatan', label: 'Catatan', catatan: 'Dokumentasi proyek dari repo' },
		{ rute: '/berita', label: 'Berita', catatan: 'RSS publik: Cointelegraph, Decrypt' },
		{ rute: '/cara-kerja', label: 'Cara kerja', catatan: 'Aliran domain → worker → API → web' },
		{ rute: '/bantuan', label: 'Bantuan', catatan: 'Tanya-jawab dari perilaku nyata' }
	];
	const aktif = $derived(page.url.pathname.replace(/\/$/, '') || '/');
</script>

<nav aria-label="Navigasi Dokumen & Informasi">
	<div class="flex flex-wrap gap-1">
		{#each tautan as t (t.rute)}
			<a
				href={t.rute}
				class="label-mikro transisi min-h-[44px] flex items-center rounded-control border px-2.5 {aktif === t.rute
					? 'border-accent text-accent'
					: 'border-line text-text-3 hover:border-accent-2 hover:text-text'}"
				aria-current={aktif === t.rute ? 'page' : undefined}
				title={t.catatan}
			>
				{t.label}
			</a>
		{/each}
	</div>
</nav>
