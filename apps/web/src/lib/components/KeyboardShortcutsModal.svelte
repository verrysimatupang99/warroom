<script lang="ts">
	/**
	 * KeyboardShortcutsModal.svelte
	 * Modal pop-up bantuan shortcut keyboard ala terminal pro (Oyenza & Bloomberg style).
	 * Muncul saat user menekan '?' atau tombol bantuan di sidebar.
	 */
	interface Props {
		open: boolean;
		onclose: () => void;
	}
	let { open = $bindable(false), onclose }: Props = $props();

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape' && open) {
			onclose();
		}
	}
</script>

<svelte:window onkeydown={handleKeydown} />

{#if open}
	<div 
		class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-xs p-4" 
		role="dialog"
		aria-modal="true"
	>
		<button
			type="button"
			class="fixed inset-0 w-full h-full cursor-default bg-transparent border-0"
			onclick={() => onclose()}
			aria-label="Tutup modal"
		></button>
		<div 
			class="relative w-full max-w-md rounded-card border border-line bg-surface p-5 shadow-2xl space-y-4 z-10" 
		>
			<div class="flex items-center justify-between border-b border-line pb-3">
				<div class="flex items-center gap-2">
					<span class="rounded bg-accent/15 px-2 py-0.5 text-12 font-mono font-bold text-accent">KEYBOARD SHORTCUTS</span>
					<span class="text-11 text-text-3">Terminal Nav</span>
				</div>
				<button class="text-text-3 hover:text-text text-13 font-mono cursor-pointer" onclick={() => onclose()}>✕ Esc</button>
			</div>

			<div class="space-y-3 font-mono text-12">
				<div class="text-11 text-text-3 font-sans uppercase font-bold tracking-wider">Pasar Utama (Direct Jump)</div>
				<div class="grid grid-cols-2 gap-2">
					<div class="flex items-center justify-between p-2 rounded bg-surface-2 border border-line">
						<span class="text-text-2">Home / Overview</span>
						<kbd class="px-1.5 py-0.5 rounded bg-canvas border border-line text-accent font-bold">1</kbd>
					</div>
					<div class="flex items-center justify-between p-2 rounded bg-surface-2 border border-line">
						<span class="text-text-2">Gold & Forex (XAU)</span>
						<kbd class="px-1.5 py-0.5 rounded bg-canvas border border-line text-accent font-bold">2</kbd>
					</div>
					<div class="flex items-center justify-between p-2 rounded bg-surface-2 border border-line">
						<span class="text-text-2">Crypto (BTC & SOL)</span>
						<kbd class="px-1.5 py-0.5 rounded bg-canvas border border-line text-accent font-bold">3</kbd>
					</div>
					<div class="flex items-center justify-between p-2 rounded bg-surface-2 border border-line">
						<span class="text-text-2">Polymarket CLOB</span>
						<kbd class="px-1.5 py-0.5 rounded bg-canvas border border-line text-accent font-bold">4</kbd>
					</div>
					<div class="flex items-center justify-between p-2 rounded bg-surface-2 border border-line">
						<span class="text-text-2">IDX Saham Indo</span>
						<kbd class="px-1.5 py-0.5 rounded bg-canvas border border-line text-accent font-bold">5</kbd>
					</div>
					<div class="flex items-center justify-between p-2 rounded bg-surface-2 border border-line">
						<span class="text-text-2">GMGN Solana Radar</span>
						<kbd class="px-1.5 py-0.5 rounded bg-canvas border border-line text-accent font-bold">6</kbd>
					</div>
				</div>

				<div class="text-11 text-text-3 font-sans uppercase font-bold tracking-wider pt-1">Sistem & Audit</div>
				<div class="grid grid-cols-2 gap-2">
					<div class="flex items-center justify-between p-2 rounded bg-surface-2 border border-line">
						<span class="text-text-2">Kinerja & Bukti</span>
						<kbd class="px-1.5 py-0.5 rounded bg-canvas border border-line text-accent font-bold">7</kbd>
					</div>
					<div class="flex items-center justify-between p-2 rounded bg-surface-2 border border-line">
						<span class="text-text-2">Leaderboard</span>
						<kbd class="px-1.5 py-0.5 rounded bg-canvas border border-line text-accent font-bold">8</kbd>
					</div>
					<div class="flex items-center justify-between p-2 rounded bg-surface-2 border border-line">
						<span class="text-text-2">Status Sistem</span>
						<kbd class="px-1.5 py-0.5 rounded bg-canvas border border-line text-accent font-bold">9</kbd>
					</div>
					<div class="flex items-center justify-between p-2 rounded bg-surface-2 border border-line">
						<span class="text-text-2">Bantuan ini</span>
						<kbd class="px-1.5 py-0.5 rounded bg-canvas border border-line text-accent font-bold">?</kbd>
					</div>
				</div>
			</div>

			<div class="pt-2 text-center text-11 text-text-3 font-sans">
				Tekan tombol angka kapan saja di luar form input untuk berpindah instrumen seketika.
			</div>
		</div>
	</div>
{/if}
