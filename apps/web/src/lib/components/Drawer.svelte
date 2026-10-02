<script lang="ts">
	// Drawer detail samping: Escape menutup, fokus dipindah ke panel saat dibuka.
	import type { Snippet } from 'svelte';

	interface Props {
		terbuka: boolean;
		judul: string;
		ontutup: () => void;
		children: Snippet;
	}
	let { terbuka, judul, ontutup, children }: Props = $props();
	let panel = $state<HTMLDivElement | null>(null);

	$effect(() => {
		if (!terbuka) return;
		const onKey = (e: KeyboardEvent) => {
			if (e.key === 'Escape') ontutup();
		};
		window.addEventListener('keydown', onKey);
		panel?.focus();
		return () => window.removeEventListener('keydown', onKey);
	});
</script>

{#if terbuka}
	<div class="fixed inset-0 z-50 flex justify-end" role="presentation">
		<button
			type="button"
			class="absolute inset-0 bg-bg/70"
			aria-label="Tutup detail"
			onclick={ontutup}
		></button>
		<div
			bind:this={panel}
			tabindex="-1"
			role="dialog"
			aria-modal="true"
			aria-label={judul}
			class="relative flex h-full w-full max-w-xl flex-col border-l border-line bg-surface shadow-2xl"
		>
			<header class="flex items-center justify-between border-b border-line px-4 py-3">
				<h2 class="text-15 text-text">{judul}</h2>
				<button
					type="button"
					class="target-44 transisi inline-flex items-center rounded-control border border-line px-3 text-13 text-text-2 hover:border-accent-2"
					onclick={ontutup}
				>
					Tutup
				</button>
			</header>
			<div class="min-h-0 flex-1 overflow-auto p-4">{@render children()}</div>
		</div>
	</div>
{/if}