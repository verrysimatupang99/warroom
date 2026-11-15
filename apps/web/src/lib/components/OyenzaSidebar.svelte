<script lang="ts">
	/**
	 * OyenzaSidebar.svelte
	 * Sidebar 260px fixed kiri terinspirasi langsung dari Oyenza Trade (StockMap by Oyenza).
	 * Mengelompokkan Pasar (Markets), Sistem & Transparansi Data (1001Startup), serta status bot.
	 */
	import { page } from '$app/state';
	import { live } from '$lib/api/live.svelte';
	import { AREAS } from '$lib/nav';
	import Ikon from './Ikon.svelte';

	interface Props {
		onclose?: () => void;
		onshortcuts?: () => void;
	}
	let { onclose, onshortcuts }: Props = $props();

	const jalur = $derived(page.url.pathname);
	const sub = $derived(page.url.searchParams.get('sub') ?? '');

	/**
	 * Sumber tunggal: `$lib/nav.ts` (AREAS). Sidebar TIDAK lagi menyimpan daftar
	 * rute sendiri — dulu daftarnya berbeda dari nav.ts sehingga `/riset` (550 baris
	 * isi nyata) tidak pernah muncul di menu dan tak punya satu pun tautan masuk.
	 * Yang disimpan lokal hanya dua hal kosmetik: tag status dan nomor pintasan.
	 */
	const TAG: Record<string, string> = Object.fromEntries(
		AREAS.filter((a) => a.status).map((a) => [a.rute, a.status as string])
	);
	TAG['/sistem'] = 'OPS';

	const NUM: Record<string, string> = Object.fromEntries(
		AREAS.map((a, i) => [a.rute, i < 9 ? String(i + 1) : '·'])
	);

	const keItem = (a: (typeof AREAS)[number]) => ({
		rute: a.rute,
		label: a.label,
		num: NUM[a.rute] ?? '·',
		ikon: a.ikon,
		tag: TAG[a.rute],
		eksternal: a.eksternal ?? false
	});

	const floor = AREAS.filter((a) => a.kategori === 'floor' || a.kategori === 'pasar').map(keItem);
	const intel = AREAS.filter((a) => a.kategori === 'intel').map(keItem);
	const audit = AREAS.filter((a) => a.kategori === 'audit').map(keItem);
	const system = AREAS.filter((a) => a.kategori === 'system' || a.kategori === 'sistem').map(keItem);

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
			<div class="logo-box" aria-hidden="true">
				<span class="logo-char">W</span>
			</div>
			<div class="brand-text">
				<span class="brand-title">War<span class="brand-accent">Room</span> <small>v2.0</small></span>
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
		<div class="flex items-center gap-1.5">
			<span class="live-dot {live.status === 'live' ? 'active' : ''}" aria-hidden="true"></span>
			<span class="text-10 font-bold text-text">{live.status.toUpperCase()}</span>
		</div>
		<span class="tag-status">FOREX LIVE · POLY PAPER</span>
	</div>

	<!-- Pilar 1: TRADING FLOOR -->
	<div class="nav-group">
		<span class="grp-label font-mono">TRADING FLOOR</span>
		<nav class="nav-list font-sans" aria-label="Trading Floor">
			{#each floor as m}
				{@const active = isAktif(m.rute)}
				<a
					href={m.rute}
					class="nav-item {active ? 'active' : ''}"
					aria-current={active ? 'page' : undefined}
					data-sveltekit-reload={m.eksternal ? '' : undefined}
					rel={m.eksternal ? 'external' : undefined}
					onclick={() => onclose?.()}
				>
					<span class="nav-icon"><Ikon nama={m.ikon} ukuran={14} /></span>
					<span class="nav-title truncate">{m.label}</span>
					{#if m.tag}
						<span class="prop-tag tag-{m.tag.toLowerCase()} font-mono">{m.tag}</span>
					{/if}
					<kbd class="nav-kbd font-mono">{m.num}</kbd>
				</a>
			{/each}
		</nav>
	</div>

	<!-- Pilar 2: INTELLIGENCE -->
	<div class="nav-group">
		<span class="grp-label font-mono">INTELLIGENCE</span>
		<nav class="nav-list font-sans" aria-label="Intelligence">
			{#each intel as m}
				{@const active = isAktif(m.rute)}
				<a
					href={m.rute}
					class="nav-item {active ? 'active' : ''}"
					aria-current={active ? 'page' : undefined}
					data-sveltekit-reload={m.eksternal ? '' : undefined}
					rel={m.eksternal ? 'external' : undefined}
					onclick={() => onclose?.()}
				>
					<span class="nav-icon"><Ikon nama={m.ikon} ukuran={14} /></span>
					<span class="nav-title truncate">{m.label}</span>
					{#if m.tag}
						<span class="prop-tag tag-{m.tag.toLowerCase()} font-mono">{m.tag}</span>
					{/if}
					<kbd class="nav-kbd font-mono">{m.num}</kbd>
				</a>
			{/each}
		</nav>
	</div>

	<!-- Pilar 3: AUDIT & LEDGER -->
	<div class="nav-group">
		<span class="grp-label font-mono">AUDIT &amp; LEDGER</span>
		<nav class="nav-list font-sans" aria-label="Audit dan Ledger">
			{#each audit as m}
				{@const active = isAktif(m.rute)}
				<a
					href={m.rute}
					class="nav-item {active ? 'active' : ''}"
					aria-current={active ? 'page' : undefined}
					data-sveltekit-reload={m.eksternal ? '' : undefined}
					rel={m.eksternal ? 'external' : undefined}
					onclick={() => onclose?.()}
				>
					<span class="nav-icon"><Ikon nama={m.ikon} ukuran={14} /></span>
					<span class="nav-title truncate">{m.label}</span>
					{#if m.tag}
						<span class="prop-tag tag-{m.tag.toLowerCase()} font-mono">{m.tag}</span>
					{/if}
					<kbd class="nav-kbd font-mono">{m.num}</kbd>
				</a>
			{/each}
		</nav>
	</div>

	<!-- Pilar 4: KONTROL SISTEM -->
	<div class="nav-group">
		<span class="grp-label font-mono">KONTROL SISTEM</span>
		<nav class="nav-list font-sans" aria-label="Kontrol Sistem">
			{#each system as s}
				{@const active = isAktif(s.rute)}
				<a
					href={s.rute}
					class="nav-item {active ? 'active' : ''}"
					aria-current={active ? 'page' : undefined}
					data-sveltekit-reload={s.eksternal ? '' : undefined}
					rel={s.eksternal ? 'external' : undefined}
					onclick={() => onclose?.()}
				>
					<span class="nav-icon"><Ikon nama={s.ikon} ukuran={14} /></span>
					<span class="nav-title truncate">{s.label}</span>
					{#if s.tag}
						<span class="prop-tag tag-{s.tag.toLowerCase()} font-mono">{s.tag}</span>
					{/if}
					<kbd class="nav-kbd font-mono">{s.num}</kbd>
				</a>
			{/each}
		</nav>
	</div>

	<!-- Sidebar Footer / Provenance Transparency Note -->
	<div class="sidebar-foot font-mono text-10">
		<div class="flex items-center justify-between text-text-3">
			<span>PROVENANCE</span>
			<div class="flex items-center gap-2">
				<span class="text-pos font-semibold">1001STARTUP OK</span>
				{#if onshortcuts}
					<button
						type="button"
						class="shortcut-btn"
						onclick={() => onshortcuts?.()}
						aria-label="Pintasan keyboard (?)"
						title="Pintasan keyboard (?)"
					>
						?
					</button>
				{/if}
			</div>
		</div>
	</div>
</aside>

<style>
	.oy-sidebar {
		width: var(--rail-w, 260px);
		height: 100dvh;
		position: sticky;
		top: 0;
		background: var(--color-surface);
		border-right: 1px solid var(--color-line);
		padding: 0.65rem 0.7rem;
		display: flex;
		flex-direction: column;
		gap: 0.45rem;
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
		padding: 0.1rem 0.35rem 0.25rem;
	}
	.brand-link {
		display: flex;
		align-items: center;
		gap: 0.55rem;
		text-decoration: none;
	}
	.logo-box {
		width: 28px;
		height: 28px;
		background: var(--color-surface-2);
		border: 1px solid var(--color-line);
		border-radius: 6px;
		display: grid;
		place-items: center;
	}
	.logo-char {
		font-family: var(--font-display);
		font-weight: 700;
		font-size: 15px;
		color: var(--color-accent);
	}
	.brand-text {
		display: flex;
		flex-direction: column;
	}
	.brand-title {
		font-size: 14px;
		font-weight: 700;
		color: var(--color-text);
		line-height: 1.15;
		letter-spacing: -0.02em;
	}
	.brand-accent {
		color: var(--color-accent);
	}
	.brand-title small {
		font-size: 10px;
		color: var(--color-text-3);
		font-weight: 500;
		margin-left: 2px;
	}
	.brand-sub {
		font-size: 9px;
		color: var(--color-text-3);
		letter-spacing: 0.08em;
		margin-top: 1px;
	}
	.close-btn {
		background: var(--color-surface-2);
		border: 1px solid var(--color-line);
		color: var(--color-text-2);
		border-radius: 5px;
		width: 28px;
		height: 28px;
		display: grid;
		place-items: center;
	}
	.engine-badge-strip {
		background: var(--color-surface-2);
		border: 1px solid var(--color-line);
		border-radius: 6px;
		padding: 0.32rem 0.55rem;
		display: flex;
		align-items: center;
		justify-content: space-between;
	}
	.live-dot {
		width: 6px;
		height: 6px;
		border-radius: 50%;
		background: var(--color-text-3);
	}
	.live-dot.active {
		background: var(--color-pos);
	}
	.tag-status {
		font-size: 8.5px;
		font-weight: 700;
		color: var(--color-accent);
		background: color-mix(in srgb, var(--color-accent) 10%, transparent);
		border: 1px solid color-mix(in srgb, var(--color-accent) 28%, transparent);
		border-radius: 4px;
		padding: 1px 5px;
		letter-spacing: 0.03em;
	}
	.nav-group {
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
	}
	.grp-label {
		font-size: 9.5px;
		font-weight: 700;
		color: var(--color-text-3);
		letter-spacing: 0.09em;
		padding-inline: 0.45rem;
		margin-bottom: 0.05rem;
	}
	.nav-list {
		display: flex;
		flex-direction: column;
		gap: 1px;
	}
	.nav-item {
		position: relative;
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.25rem 0.5rem;
		border-radius: 5px;
		color: var(--color-text-2);
		text-decoration: none;
		font-size: 12.5px;
		font-weight: 500;
		border: 1px solid transparent;
		transition:
			background-color 120ms ease-out,
			color 120ms ease-out,
			border-color 120ms ease-out;
		min-height: 30px;
	}
	.nav-item:hover {
		background: var(--color-surface-2);
		color: var(--color-text);
		border-color: var(--color-line-soft);
	}
	.nav-item.active {
		background: var(--color-surface-2);
		color: var(--color-text);
		border-color: var(--color-line);
		border-left: 2px solid var(--color-accent);
		padding-left: calc(0.5rem - 1px);
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
		font-size: 8.5px;
		font-weight: 700;
		color: var(--color-pos);
		background: color-mix(in srgb, var(--color-pos) 12%, transparent);
		border: 1px solid color-mix(in srgb, var(--color-pos) 30%, transparent);
		border-radius: 3px;
		padding: 0 4px;
		line-height: 1.4;
		letter-spacing: 0.03em;
	}
	.prop-tag.tag-paper {
		color: var(--color-warn);
		background: color-mix(in srgb, var(--color-warn) 12%, transparent);
		border-color: color-mix(in srgb, var(--color-warn) 30%, transparent);
	}
	.prop-tag.tag-standby {
		color: var(--color-text-3);
		background: var(--color-surface-2);
		border-color: var(--color-line);
	}
	.prop-tag.tag-ops {
		color: var(--color-text-2);
		background: var(--color-surface-2);
		border-color: var(--color-line);
	}
	.nav-kbd {
		font-size: 10px;
		color: var(--color-text-3);
		background: var(--color-bg);
		border: 1px solid var(--color-line);
		border-radius: 4px;
		min-width: 18px;
		height: 18px;
		display: grid;
		place-items: center;
	}
	.nav-item.active .nav-kbd {
		color: var(--color-accent);
		border-color: color-mix(in srgb, var(--color-accent) 35%, var(--color-line));
	}
	.sidebar-foot {
		margin-top: auto;
		padding-top: 0.45rem;
		border-top: 1px solid var(--color-line);
	}
	.shortcut-btn {
		font-family: var(--font-mono);
		font-size: 10px;
		font-weight: 700;
		color: var(--color-text-3);
		background: var(--color-surface-2);
		border: 1px solid var(--color-line);
		border-radius: 4px;
		width: 18px;
		height: 18px;
		display: inline-grid;
		place-items: center;
		padding: 0;
	}
	.shortcut-btn:hover {
		color: var(--color-accent);
		border-color: var(--color-accent);
	}
</style>
