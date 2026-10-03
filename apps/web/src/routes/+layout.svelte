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

	$effect(() => {
		if (page.url.pathname === '/masuk') return;
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

{#if page.url.pathname === '/masuk'}
	{@render children()}
{:else}
	<AppShell>{@render children()}</AppShell>
{/if}
