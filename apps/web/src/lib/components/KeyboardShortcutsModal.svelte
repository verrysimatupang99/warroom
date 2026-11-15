<script lang="ts">
	/**
	 * KeyboardShortcutsModal.svelte
	 * Modal pop-up bantuan shortcut keyboard ala terminal pro (Oyenza & Bloomberg style).
	 * Daftar pintasan 1–9 diambil langsung dari AREAS ($lib/nav.ts) agar selalu selaras.
	 */
	import { AREAS } from '$lib/nav';

	interface Props {
		open: boolean;
		onclose: () => void;
	}
	let { open = $bindable(false), onclose }: Props = $props();

	const pintasan = AREAS.slice(0, 9).map((a, i) => ({
		num: String(i + 1),
		label: a.label,
		kategori: a.kategori
	}));

	const floorShortcuts = pintasan.filter((p) => p.kategori === 'floor' || p.kategori === 'pasar');
	const intelShortcuts = pintasan.filter((p) => p.kategori !== 'floor' && p.kategori !== 'pasar');

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape' && open) {
			onclose();
		}
	}
</script>

<svelte:window onkeydown={handleKeydown} />

{#if open}
	<div
		class="fixed inset-0 z-50 flex items-center justify-center bg-bg/80 backdrop-blur-xs p-4"
		role="dialog"
		aria-modal="true"
		aria-label="Pintasan keyboard"
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
					<span class="rounded bg-accent/15 px-2 py-0.5 text-11 font-mono font-bold text-accent"
						>KEYBOARD SHORTCUTS</span
					>
					<span class="text-11 text-text-3 font-mono">Terminal Nav</span>
				</div>
				<button
					type="button"
					class="text-text-3 hover:text-text text-12 font-mono cursor-pointer px-1.5 py-0.5 rounded border border-transparent hover:border-line"
					onclick={() => onclose()}>✕ Esc</button
				>
			</div>

			<div class="space-y-3 font-mono text-12">
				<div class="label-mikro">Trading Floor (1–{floorShortcuts.length})</div>
				<div class="grid grid-cols-2 gap-1.5">
					{#each floorShortcuts as p (p.num)}
						<div class="flex items-center justify-between px-2.5 py-1.5 rounded bg-surface-2 border border-line">
							<span class="text-text-2 truncate pr-2 font-sans text-12">{p.label}</span>
							<kbd class="px-1.5 py-0.5 rounded bg-canvas border border-line text-accent font-bold text-11"
								>{p.num}</kbd
							>
						</div>
					{/each}
				</div>

				<div class="label-mikro pt-1">Intelligence &amp; Kontrol</div>
				<div class="grid grid-cols-2 gap-1.5">
					{#each intelShortcuts as p (p.num)}
						<div class="flex items-center justify-between px-2.5 py-1.5 rounded bg-surface-2 border border-line">
							<span class="text-text-2 truncate pr-2 font-sans text-12">{p.label}</span>
							<kbd class="px-1.5 py-0.5 rounded bg-canvas border border-line text-accent font-bold text-11"
								>{p.num}</kbd
							>
						</div>
					{/each}
					<div class="flex items-center justify-between px-2.5 py-1.5 rounded bg-surface-2 border border-line">
						<span class="text-text-2 truncate pr-2 font-sans text-12">Bantuan ini</span>
						<kbd class="px-1.5 py-0.5 rounded bg-canvas border border-line text-accent font-bold text-11"
							>?</kbd
						>
					</div>
				</div>
			</div>

			<div class="pt-2 border-t border-line-soft text-center text-11 text-text-3 font-sans">
				Tekan tombol angka kapan saja di luar form input untuk berpindah halaman seketika.
			</div>
		</div>
	</div>
{/if}
