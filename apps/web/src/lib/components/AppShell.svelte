<script lang="ts">
	/**
	 * AppShell.svelte
	 * Shell 2-Kolom Oyenza Trade (Sticky Sidebar 260px Desktop + Responsive Mobile Drawer).
	 */
	import type { Snippet } from 'svelte';
	import { live } from '$lib/api/live.svelte';
	import { AREAS } from '$lib/nav';
	import OyenzaSidebar from './OyenzaSidebar.svelte';
	import KeyboardShortcutsModal from './KeyboardShortcutsModal.svelte';
	import { goto } from '$app/navigation';
	import InfraBanner from './InfraBanner.svelte';

	let { children }: { children: Snippet } = $props();

	// State untuk drawer mobile & shortcuts modal
	let mobileDrawerBuka = $state(false);
	let modalShortcutsBuka = $state(false);

	// Peta pintasan 1–9 diturunkan dari AREAS ($lib/nav.ts) agar selalu selaras
	// dengan badge kbd di OyenzaSidebar.
	const routeMap: Record<string, { rute: string; eksternal: boolean }> = Object.fromEntries(
		AREAS.slice(0, 9).map((a, i) => [
			String(i + 1),
			{ rute: a.rute, eksternal: Boolean(a.eksternal) }
		])
	);

	function handleGlobalKeys(e: KeyboardEvent) {
		if (
			e.target instanceof HTMLInputElement ||
			e.target instanceof HTMLTextAreaElement ||
			e.target instanceof HTMLSelectElement
		) {
			return;
		}
		if (e.key === 'Escape' && mobileDrawerBuka) {
			e.preventDefault();
			mobileDrawerBuka = false;
			return;
		}
		if (e.key === '?') {
			e.preventDefault();
			modalShortcutsBuka = !modalShortcutsBuka;
			return;
		}
		if (e.ctrlKey || e.metaKey || e.altKey) return;
		const tujuan = routeMap[e.key];
		if (tujuan) {
			e.preventDefault();
			if (tujuan.eksternal && typeof window !== 'undefined') {
				window.location.href = tujuan.rute;
			} else {
				void goto(tujuan.rute);
			}
		}
	}

	$effect(() => {
		live.mulai();
		return () => live.hentikan();
	});
</script>

<a class="skip-link" href="#konten">Lompat ke konten</a>

<svelte:window onkeydown={handleGlobalKeys} />

<div class="app-layout">
	<!-- DESKTOP SIDEBAR: Sticky 260px -->
	<div class="desktop-sidebar-slot hidden md:block">
		<OyenzaSidebar onshortcuts={() => (modalShortcutsBuka = true)} />
	</div>

	<!-- MOBILE TOPBAR & DRAWER -->
	<div class="md:hidden mobile-header">
		<div class="flex items-center gap-2.5">
			<button
				type="button"
				class="menu-toggle-btn"
				onclick={() => (mobileDrawerBuka = !mobileDrawerBuka)}
				aria-label="Toggle Menu Navigasi"
				aria-expanded={mobileDrawerBuka}
			>
				<span class="bar"></span>
				<span class="bar"></span>
				<span class="bar"></span>
			</button>
			<a href="/" class="mobile-brand font-display">War<span>Room</span></a>
		</div>

		<div class="flex items-center gap-2 font-mono text-11">
			<span class="live-pill {live.status === 'live' ? 'pos' : 'warn'}">
				<span class="dot" aria-hidden="true"></span> {live.status.toUpperCase()}
			</span>
		</div>
	</div>

	<!-- Mobile Drawer Backdrop & Menu -->
	{#if mobileDrawerBuka}
		<div
			class="mobile-backdrop md:hidden"
			onclick={() => (mobileDrawerBuka = false)}
			role="presentation"
		></div>
		<div class="mobile-drawer md:hidden">
			<OyenzaSidebar
				onclose={() => (mobileDrawerBuka = false)}
				onshortcuts={() => {
					mobileDrawerBuka = false;
					modalShortcutsBuka = true;
				}}
			/>
		</div>
	{/if}

	<!-- FLUID MAIN CANVAS -->
	<main id="konten" class="main-canvas" data-app-siap tabindex="-1">
		<div class="canvas-inner">
			<InfraBanner />
			{@render children()}
		</div>
	</main>

	<!-- KEYBOARD SHORTCUTS MODAL -->
	<KeyboardShortcutsModal open={modalShortcutsBuka} onclose={() => (modalShortcutsBuka = false)} />
</div>

<style>
	.app-layout {
		display: flex;
		align-items: flex-start;
		min-height: 100vh;
		background: var(--color-bg);
		color: var(--color-text);
	}
	.desktop-sidebar-slot {
		position: sticky;
		top: 0;
		height: 100dvh;
		flex-shrink: 0;
		z-index: 50;
	}
	.mobile-header {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		height: 48px;
		background: var(--color-surface);
		border-bottom: 1px solid var(--color-line);
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0 0.85rem;
		z-index: 40;
	}
	.menu-toggle-btn {
		width: 34px;
		height: 34px;
		background: var(--color-surface-2);
		border: 1px solid var(--color-line);
		border-radius: 6px;
		display: flex;
		flex-direction: column;
		justify-content: center;
		align-items: center;
		gap: 4px;
		padding: 0;
	}
	.menu-toggle-btn:hover {
		border-color: var(--color-accent);
	}
	.menu-toggle-btn .bar {
		width: 15px;
		height: 1.5px;
		background: var(--color-text);
		border-radius: 2px;
	}
	.mobile-brand {
		font-weight: 700;
		font-size: 15px;
		letter-spacing: -0.02em;
		color: var(--color-text);
		text-decoration: none;
	}
	.mobile-brand span {
		color: var(--color-accent);
	}
	.live-pill {
		font-size: 9.5px;
		font-weight: 700;
		padding: 2px 7px;
		border-radius: 999px;
		display: inline-flex;
		align-items: center;
		gap: 4px;
		border: 1px solid transparent;
	}
	.live-pill.pos {
		background: color-mix(in srgb, var(--color-pos) 12%, transparent);
		color: var(--color-pos);
		border-color: color-mix(in srgb, var(--color-pos) 28%, transparent);
	}
	.live-pill.warn {
		background: color-mix(in srgb, var(--color-warn) 12%, transparent);
		color: var(--color-warn);
		border-color: color-mix(in srgb, var(--color-warn) 28%, transparent);
	}
	.live-pill .dot {
		width: 6px;
		height: 6px;
		border-radius: 50%;
		background: currentColor;
	}
	.mobile-backdrop {
		position: fixed;
		inset: 0;
		background: color-mix(in srgb, var(--color-bg) 75%, transparent);
		backdrop-filter: blur(2px);
		z-index: 60;
	}
	.mobile-drawer {
		position: fixed;
		top: 0;
		bottom: 0;
		left: 0;
		width: 268px;
		z-index: 70;
		box-shadow: 4px 0 24px color-mix(in srgb, var(--color-bg) 80%, transparent);
		animation: slide-right 180ms cubic-bezier(0, 0, 0.2, 1);
	}
	@keyframes slide-right {
		from {
			transform: translateX(-100%);
		}
		to {
			transform: translateX(0);
		}
	}
	.main-canvas {
		flex: 1;
		min-width: 0;
		padding: 1rem 0.9rem 2.5rem;
	}
	.canvas-inner {
		max-width: 1480px;
		margin: 0 auto;
		width: 100%;
	}
	@media (max-width: 767px) {
		.main-canvas {
			padding-top: 60px;
		}
	}
	@media (min-width: 768px) {
		.main-canvas {
			padding: 1.25rem 1.75rem 3.5rem;
			max-width: calc(100vw - var(--rail-w, 260px));
		}
		/* Bar mobile tidak relevan di desktop: sidebar sudah permanen. */
		.mobile-header {
			display: none;
		}
	}
</style>
