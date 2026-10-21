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
		background: #0c0d0e;
		color: #ededec;
	}
	.mobile-header {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		height: 48px;
		background: #121314;
		border-bottom: 1px solid #232629;
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0 1rem;
		z-index: 40;
	}
	.menu-toggle-btn {
		width: 34px;
		height: 34px;
		background: #1c1f22;
		border: 1px solid #2f3337;
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
		background: #ededec;
		border-radius: 2px;
	}
	.mobile-brand {
		font-weight: 700;
		font-size: 16px;
		letter-spacing: -0.02em;
	}
	.mobile-brand span {
		color: #f5b83d;
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
		background: rgba(60, 199, 107, 0.12);
		color: #3cc76b;
		border-color: rgba(60, 199, 107, 0.25);
	}
	.live-pill.warn {
		background: rgba(245, 184, 61, 0.12);
		color: #f5b83d;
		border-color: rgba(245, 184, 61, 0.25);
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
		background: rgba(0, 0, 0, 0.7);
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
		box-shadow: 4px 0 24px rgba(0, 0, 0, 0.8);
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
	}
</style>
