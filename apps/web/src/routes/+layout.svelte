<script lang="ts">
	// Guard sesi (W7): semua halaman kecuali /masuk butuh `GET /api/v1/auth/me`.
	// 401 → redirect ke /masuk?lanjut=<path>. Render klien (ssr=false), jadi tidak ada
	// kebocoran data server-side.
	import '../app.css';
	import type { Snippet } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { getAku } from '$lib/api/client';
	import AppShell from '$lib/components/AppShell.svelte';

	let { children }: { children: Snippet } = $props();

	// HAPUS SHELL PRA-HYDRATION (perbaikan 7 Okt, keluhan pemilik: "web masih terus
	// memuat, ga bisa kebuka"). Shell di app.html HANYA kerangka statis; aplikasi hidup
	// dirender di belakangnya. Tanpa baris ini shell menutupi seluruh halaman selamanya —
	// judul & DOM sudah benar, tetapi yang terlihat tetap skeleton. Ini bug yang saya
	// sendiri buat, dan tes lama tidak menangkapnya karena membaca textContent (yang
	// tetap berisi konten aplikasi), bukan yang benar-benar TERLIHAT.
	$effect(() => {
		document.getElementById('shell-muat')?.remove();
	});

	$effect(() => {
		if (page.url.pathname === '/masuk' || page.url.pathname === '/mulai') return;
		let aktif = true;
		getAku().catch(() => {
			if (aktif) {
				const lanjut = page.url.pathname + page.url.search;
				void goto(`/masuk?lanjut=${encodeURIComponent(lanjut)}`);
			}
		});
		return () => {
			aktif = false;
		};
	});
</script>

{#if page.url.pathname === '/masuk' || page.url.pathname === '/mulai'}
	{@render children()}
{:else}
	<AppShell>{@render children()}</AppShell>
{/if}
