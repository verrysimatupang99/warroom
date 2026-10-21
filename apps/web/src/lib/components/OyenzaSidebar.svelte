<script lang="ts">
	/**
	 * OyenzaSidebar.svelte
	 * Sidebar 272px fixed kiri terinspirasi langsung dari Oyenza Trade (StockMap by Oyenza).
	 * Mengelompokkan Pasar (Markets), Sistem & Transparansi Data (1001Startup), serta status bot.
	 */
	import { page } from '$app/state';
	import { live } from '$lib/api/live.svelte';
	import Ikon from './Ikon.svelte';

	interface Props {
		onclose?: () => void;
	}
	let { onclose }: Props = $props();

	const jalur = $derived(page.url.pathname);
	const sub = $derived(page.url.searchParams.get('sub') ?? '');

	const markets = [
		{ rute: '/', label: 'Overview / Home', num: '1', ikon: 'home' },
		{ rute: '/forex', label: 'Gold & Forex (XAUUSD)', num: '2', ikon: 'forex', tag: 'PROP' },
		{ rute: '/crypto', label: 'Crypto (BTC & SOL)', num: '3', ikon: 'crypto' },
		{ rute: '/polymarket', label: 'Polymarket CLOB', num: '4', ikon: 'polymarket' },
		{ rute: '/idx', label: 'IDX Saham Indonesia', num: '5', ikon: 'idx' },
		{ rute: '/gmgn', label: 'GMGN Solana Radar', num: '6', ikon: 'gmgn' }
	];

	const system = [
		{ rute: '/tencent', label: 'Server Tencent (Tailscale)', num: '7', ikon: 'mesin', tag: 'NODE' },
		{ rute: '/riset?sub=bukti', label: 'Kinerja & Bukti Ledger', num: '8', ikon: 'riset' },
		{ rute: '/riset?sub=leaderboard', label: 'Strategy Leaderboard', num: '9', ikon: 'riset' },
		{ rute: '/sistem', label: 'Layanan & Kesegaran Data', num: '0', ikon: 'sistem' },
		{ rute: '/catatan', label: 'Catatan & Alur Engine', num: 'K', ikon: 'info' }
	];

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
			Setiap sinyal tertaut langsung ke feed real-time TVC, CLOB, dan Tencent Cron tanpa angka karangan.
		</p>
	</div>
</aside>

<style>
	.oy-sidebar {
		width: 272px;
		height: 100vh;
		position: sticky;
		top: 0;
		background: #121314;
		border-right: 1px solid #232629;
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
		background: #1c1f22;
		border: 1px solid #2f3337;
		border-radius: 6px;
		display: grid;
		place-items: center;
	}
	.logo-char {
		font-family: var(--font-display);
		font-weight: 700;
		font-size: 16px;
		color: #f5b83d;
	}
	.brand-text {
		display: flex;
		flex-direction: column;
	}
	.brand-title {
		font-size: 15px;
		font-weight: 700;
		color: #ededec;
		line-height: 1.2;
	}
	.brand-title small {
		font-size: 10px;
		color: #787d84;
		font-weight: 500;
	}
	.brand-sub {
		font-size: 9.5px;
		color: #787d84;
		letter-spacing: 0.08em;
	}
	.close-btn {
		background: transparent;
		border: 1px solid #232629;
		color: #a6aab0;
		border-radius: 4px;
		width: 28px;
		height: 28px;
		display: grid;
		place-items: center;
	}
	.engine-badge-strip {
		background: #16181a;
		border: 1px solid #232629;
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
		background: #787d84;
	}
	.live-dot.active {
		background: #3cc76b;
		box-shadow: 0 0 6px rgba(60, 199, 107, 0.4);
	}
	.tag-status {
		font-size: 9px;
		font-weight: 700;
		color: #f5b83d;
		background: rgba(245, 184, 61, 0.1);
		border: 1px solid rgba(245, 184, 61, 0.25);
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
		color: #787d84;
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
		color: #a6aab0;
		text-decoration: none;
		font-size: 13px;
		font-weight: 500;
		border: 1px solid transparent;
		transition: all 120ms ease-out;
		min-height: 38px;
	}
	.nav-item:hover {
		background: #1c1f22;
		color: #ededec;
		border-color: #232629;
	}
	.nav-item.active {
		background: #1b1e21;
		color: #ededec;
		border-color: #2f3337;
		font-weight: 600;
	}
	.nav-item.active .nav-icon {
		color: #f5b83d;
	}
	.nav-icon {
		color: #787d84;
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
		color: #3cc76b;
		background: rgba(60, 199, 107, 0.12);
		border: 1px solid rgba(60, 199, 107, 0.3);
		border-radius: 3px;
		padding: 0 4px;
	}
	.nav-kbd {
		font-size: 10.5px;
		color: #787d84;
		background: #0c0d0e;
		border: 1px solid #232629;
		border-radius: 4px;
		min-width: 20px;
		height: 20px;
		display: grid;
		place-items: center;
	}
	.sidebar-foot {
		margin-top: auto;
		padding-top: 0.85rem;
		border-top: 1px solid #232629;
	}
	.foot-desc {
		line-height: 1.4;
		font-size: 11px;
	}
</style>
