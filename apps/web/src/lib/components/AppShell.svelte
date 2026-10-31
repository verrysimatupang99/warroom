<script lang="ts">
	/**
	 * AppShell.svelte
	 * Shell 2-Kolom Oyenza Trade (Fixed Sidebar 272px Desktop + Responsive Mobile Drawer).
	 */
	import type { Snippet } from 'svelte';
	import { live } from '$lib/api/live.svelte';
	import OyenzaSidebar from './OyenzaSidebar.svelte';
	import KeyboardShortcutsModal from './KeyboardShortcutsModal.svelte';
	import Ikon from './Ikon.svelte';

	let { children }: { children: Snippet } = $props();

	// State untuk drawer mobile & shortcuts modal
	let mobileDrawerBuka = $state(false);
	let modalShortcutsBuka = $state(false);

	function handleGlobalKeys(e: KeyboardEvent) {
		if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
		if (e.key === '?') {
			e.preventDefault();
			modalShortcutsBuka = !modalShortcutsBuka;
		}
	}

	$effect(() => {
		live.mulai();
		return () => live.hentikan();
	});
</script>

<svelte:window onkeydown={handleGlobalKeys} />

<div class="app-layout">
	<!-- DESKTOP SIDEBAR: Fixed 272px -->
	<div class="hidden md:block">
		<OyenzaSidebar />
	</div>

	<!-- MOBILE TOPBAR & DRAWER -->
	<div class="md:hidden mobile-header">
		<div class="flex items-center gap-2">
			<button 
				type="button" 
				class="menu-toggle-btn" 
				onclick={() => (mobileDrawerBuka = !mobileDrawerBuka)}
				aria-label="Toggle Menu Navigasi"
			>
				<span class="bar"></span>
				<span class="bar"></span>
				<span class="bar"></span>
			</button>
			<span class="mobile-brand font-display">War<span>Room</span></span>
		</div>

		<div class="flex items-center gap-2 font-mono text-11">
			<span class="live-pill {live.status === 'live' ? 'pos' : 'warn'}">
				<span class="dot"></span> {live.status.toUpperCase()}
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
			<OyenzaSidebar onclose={() => (mobileDrawerBuka = false)} />
		</div>
	{/if}

	<!-- FLUID MAIN CANVAS -->
	<main id="konten" class="main-canvas" data-app-siap tabindex="-1">
		{@render children()}
	</main>

	<!-- KEYBOARD SHORTCUTS MODAL -->
	<KeyboardShortcutsModal open={modalShortcutsBuka} onclose={() => (modalShortcutsBuka = false)} />
</div>

<style>
	.app-layout {
		display: flex;
		min-height: 100vh;
		background: var(--color-bg);
		color: var(--color-text);
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
		padding: 0 1rem;
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
	.menu-toggle-btn .bar {
		width: 16px;
		height: 2px;
		background: var(--color-text);
		border-radius: 2px;
	}
	.mobile-brand {
		font-weight: 700;
		font-size: 16px;
		letter-spacing: -0.02em;
	}
	.mobile-brand span {
		color: var(--color-accent);
	}
	.live-pill {
		font-size: 10px;
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
		border-color: color-mix(in srgb, var(--color-pos) 25%, transparent);
	}
	.live-pill.warn {
		background: color-mix(in srgb, var(--color-warn) 12%, transparent);
		color: var(--color-warn);
		border-color: color-mix(in srgb, var(--color-warn) 25%, transparent);
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
		background: color-mix(in srgb, var(--color-bg) 70%, transparent);
		backdrop-filter: blur(2px);
		z-index: 60;
	}
	.mobile-drawer {
		position: fixed;
		top: 0;
		bottom: 0;
		left: 0;
		width: 280px;
		z-index: 70;
		box-shadow: 4px 0 24px color-mix(in srgb, var(--color-bg) 80%, transparent);
		animation: slide-right 200ms cubic-bezier(0, 0, 0.2, 1);
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
		padding: 1.25rem 1rem 3rem;
	}
	@media (max-width: 767px) {
		.main-canvas {
			padding-top: 60px;
		}
	}
	@media (min-width: 768px) {
		.main-canvas {
			padding: 1.5rem 2rem 4rem;
			max-width: calc(100vw - 272px);
		}
		/* Bar mobile tidak relevan di desktop: sidebar sudah permanen.
		   Tanpa ini bar 48px menimpa 24px awal konten (main-canvas padding 1.5rem). */
		.mobile-header {
			display: none;
		}
	}
</style>
