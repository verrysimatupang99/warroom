<script lang="ts">
	/**
	 * OyenzaSidebar.svelte
	 * Sidebar 272px fixed kiri terinspirasi langsung dari Oyenza Trade (StockMap by Oyenza).
	 * Mengelompokkan Pasar (Markets), Sistem & Transparansi Data (1001Startup), serta status bot.
	 */
	import { page } from '$app/state';
	import { live } from '$lib/api/live.svelte';
	import { AREAS } from '$lib/nav';
	import Ikon from './Ikon.svelte';

	interface Props {
		onclose?: () => void;
	}
	let { onclose }: Props = $props();

	const jalur = $derived(page.url.pathname);
	const sub = $derived(page.url.searchParams.get('sub') ?? '');

	/**
	 * Sumber tunggal: `$lib/nav.ts` (AREAS). Sidebar TIDAK lagi menyimpan daftar
	 * rute sendiri — dulu daftarnya berbeda dari nav.ts sehingga `/riset` (550 baris
	 * isi nyata) tidak pernah muncul di menu dan tak punya satu pun tautan masuk.
	 * Yang disimpan lokal hanya dua hal kosmetik: tag status dan nomor pintasan.
	 */
	// Tag status kini dibaca dari nav.ts supaya rail dan isi halaman tidak pernah
	// berbeda. Sebelumnya daftar ini disimpan lokal dan sempat menulis "WIP" untuk
	// market yang sebenarnya cuma standby, serta "WIP" untuk Riset yang isinya ada.
	const TAG: Record<string, string> = Object.fromEntries(
		AREAS.filter((a) => a.status).map((a) => [a.rute, a.status as string])
	);
	TAG['/sistem'] = 'OPS';

	const NUM: Record<string, string> = Object.fromEntries(
		// Nomor pintasan mengikuti urutan nav, bukan daftar manual. Daftar manual
		// menyimpan rute yang sudah dialihkan (mis. /tencent) dan bisa meleset
		// setiap kali area ditambah atau dihapus.
		AREAS.map((a, i) => [a.rute, String(i + 1)])
	);

	const keItem = (a: (typeof AREAS)[number]) => ({
		rute: a.rute,
		label: a.label,
		num: NUM[a.rute] ?? '·',
		ikon: a.ikon,
		tag: TAG[a.rute]
	});

	const markets = AREAS.filter((a) => a.kategori === 'pasar').map(keItem);
	const system = AREAS.filter((a) => a.kategori !== 'pasar').map(keItem);

	function isAktif(rute: string): boolean {
		if (rute === '/') return jalur === '/';
		if (rute.includes('?sub=')) {
			const [path, query] = rute.split('?sub=');
			return jalur === path && sub === query;
		}
		return jalur.startsWith(rute);
	}
</script>

<aside class="oy-sidebar" aria-label="Navigasi Utama Oyenza">
	<!-- Top Brand Area -->
	<div class="brand-area">
		<a href="/" class="brand-link" onclick={() => onclose?.()}>
			<div class="logo-box">
				<span class="logo-char">W</span>
			</div>
			<div class="brand-text">
				<span class="brand-title">WarRoom <small>v2.0</small></span>
				<span class="brand-sub font-mono">QUANT MULTI-MARKET</span>
			</div>
		</a>
		{#if onclose}
			<button type="button" class="close-btn md:hidden" onclick={onclose} aria-label="Tutup Menu">
				✕
			</button>
		{/if}
	</div>

	<!-- Live Engine Status Badge -->
	<div class="engine-badge-strip font-mono">
		<div class="flex items-center gap-2">
			<span class="live-dot {live.status === 'live' ? 'active' : ''}"></span>
			<span class="text-11 font-bold text-text">{live.status.toUpperCase()}</span>
		</div>
		<span class="tag-status">AUTO-TRADE READY</span>
	</div>

	<!-- Navigation Group: MARKETS -->
	<div class="nav-group">
		<span class="grp-label font-mono">PASAR &amp; RADAR</span>
		<nav class="nav-list font-sans">
			{#each markets as m}
				{@const active = isAktif(m.rute)}
				<a 
					href={m.rute} 
					class="nav-item {active ? 'active' : ''}" 
					aria-current={active ? 'page' : undefined}
					onclick={() => onclose?.()}
				>
					<span class="nav-icon"><Ikon nama={m.ikon} ukuran={15} /></span>
					<span class="nav-title truncate">{m.label}</span>
					{#if m.tag}
						<span class="prop-tag font-mono">{m.tag}</span>
					{/if}
					<kbd class="nav-kbd font-mono">{m.num}</kbd>
				</a>
			{/each}
		</nav>
	</div>

	<!-- Navigation Group: AUDIT & PROVENANCE (1001Startup style) -->
	<div class="nav-group">
		<span class="grp-label font-mono">LEDGER &amp; SISTEM</span>
		<nav class="nav-list font-sans">
			{#each system as s}
				{@const active = isAktif(s.rute)}
				<a 
					href={s.rute} 
					class="nav-item {active ? 'active' : ''}" 
					aria-current={active ? 'page' : undefined}
					onclick={() => onclose?.()}
				>
					<span class="nav-icon"><Ikon nama={s.ikon} ukuran={15} /></span>
					<span class="nav-title truncate">{s.label}</span>
					<kbd class="nav-kbd font-mono">{s.num}</kbd>
				</a>
			{/each}
		</nav>
	</div>

	<!-- Sidebar Footer / Provenance Transparency Note -->
	<div class="sidebar-foot font-mono text-11">
		<div class="flex items-center justify-between text-text-3">
			<span>PROVENANCE</span>
			<span class="text-pos">1001STARTUP OK</span>
		</div>
		<p class="foot-desc font-sans text-text-3 mt-1">
			Setiap sinyal tertaut ke sumbernya sendiri: MEXC, Yahoo Finance, dan telemetri MT5.
		</p>
	</div>
</aside>

<style>
	.oy-sidebar {
		width: 272px;
		height: 100vh;
		position: sticky;
		top: 0;
		background: var(--color-surface);
		border-right: 1px solid var(--color-line);
		padding: 1.25rem 0.85rem;
		display: flex;
		flex-direction: column;
		gap: 1.25rem;
		overflow-y: auto;
		scrollbar-width: none;
		z-index: 50;
	}
	.oy-sidebar::-webkit-scrollbar {
		display: none;
	}
	.brand-area {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0 0.4rem 0.5rem;
	}
	.brand-link {
		display: flex;
		align-items: center;
		gap: 0.65rem;
		text-decoration: none;
	}
	.logo-box {
		width: 32px;
		height: 32px;
		background: var(--color-surface-2);
		border: 1px solid var(--color-line);
		border-radius: 6px;
		display: grid;
		place-items: center;
	}
	.logo-char {
		font-family: var(--font-display);
		font-weight: 700;
		font-size: 16px;
		color: var(--color-accent);
	}
	.brand-text {
		display: flex;
		flex-direction: column;
	}
	.brand-title {
		font-size: 15px;
		font-weight: 700;
		color: var(--color-text);
		line-height: 1.2;
	}
	.brand-title small {
		font-size: 10px;
		color: var(--color-text-3);
		font-weight: 500;
	}
	.brand-sub {
		font-size: 9.5px;
		color: var(--color-text-3);
		letter-spacing: 0.08em;
	}
	.close-btn {
		background: transparent;
		border: 1px solid var(--color-line);
		color: var(--color-text-3);
		border-radius: 4px;
		width: 28px;
		height: 28px;
		display: grid;
		place-items: center;
	}
	.engine-badge-strip {
		background: var(--color-surface-2);
		border: 1px solid var(--color-line);
		border-radius: 6px;
		padding: 0.45rem 0.65rem;
		display: flex;
		align-items: center;
		justify-content: space-between;
	}
	.live-dot {
		width: 7px;
		height: 7px;
		border-radius: 50%;
		background: var(--color-text-3);
	}
	.live-dot.active {
		background: var(--color-pos);
		box-shadow: 0 0 6px color-mix(in srgb, var(--color-pos) 40%, transparent);
	}
	.tag-status {
		font-size: 9px;
		font-weight: 700;
		color: var(--color-accent);
		background: color-mix(in srgb, var(--color-accent) 10%, transparent);
		border: 1px solid color-mix(in srgb, var(--color-accent) 25%, transparent);
		border-radius: 4px;
		padding: 1px 5px;
	}
	.nav-group {
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
	}
	.grp-label {
		font-size: 10px;
		font-weight: 700;
		color: var(--color-text-3);
		letter-spacing: 0.08em;
		padding-inline: 0.5rem;
		margin-bottom: 0.2rem;
	}
	.nav-list {
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
	}
	.nav-item {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		padding: 0.45rem 0.6rem;
		border-radius: 6px;
		color: var(--color-text-3);
		text-decoration: none;
		font-size: 13px;
		font-weight: 500;
		border: 1px solid transparent;
		transition: all 120ms ease-out;
		min-height: 38px;
	}
	.nav-item:hover {
		background: var(--color-surface-2);
		color: var(--color-text);
		border-color: var(--color-line-soft);
	}
	.nav-item.active {
		background: var(--color-surface-3);
		color: var(--color-text);
		border-color: var(--color-line);
		font-weight: 600;
	}
	.nav-item.active .nav-icon {
		color: var(--color-accent);
	}
	.nav-icon {
		color: var(--color-text-3);
		display: grid;
		place-items: center;
		flex-shrink: 0;
	}
	.nav-title {
		flex: 1;
	}
	.prop-tag {
		font-size: 9px;
		font-weight: 700;
		color: var(--color-pos);
		background: color-mix(in srgb, var(--color-pos) 12%, transparent);
		border: 1px solid color-mix(in srgb, var(--color-pos) 30%, transparent);
		border-radius: 3px;
		padding: 0 4px;
	}
	.nav-kbd {
		font-size: 10.5px;
		color: var(--color-text-3);
		background: var(--color-bg);
		border: 1px solid var(--color-line);
		border-radius: 4px;
		min-width: 20px;
		height: 20px;
		display: grid;
		place-items: center;
	}
	.sidebar-foot {
		margin-top: auto;
		padding-top: 0.85rem;
		border-top: 1px solid var(--color-line);
	}
	.foot-desc {
		line-height: 1.4;
		font-size: 11px;
	}
</style>
