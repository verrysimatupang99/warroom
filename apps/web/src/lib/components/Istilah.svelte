<script lang="ts">
	// <Istilah> — tanda tanya kecil yang menjelaskan satu istilah teknis dalam bahasa manusia.
	//
	// Pakai: <Istilah k="gate" /> atau <Istilah k="gate" teks="pemeriksaan" />
	//   - k    : kunci di kamus ($lib/bahasa.ts)
	//   - teks : teks yang tampil (default = versi manusia dari kamus)
	//
	// Kenapa tombol, bukan `title=` saja: tooltip `title` tak terbaca di layar sentuh dan
	// tak ramah keyboard. Ini tombol yang benar-benar bisa ditekan/di-tab, menampilkan
	// penjelasan sebagai teks yang bisa diseleksi.
	import { arti } from '$lib/bahasa';
	import type { Snippet } from 'svelte';

	interface Props {
		k: string;
		teks?: string;
		children?: Snippet;
	}
	let { k, teks, children }: Props = $props();
	const it = $derived(arti(k));
	const label = $derived(teks ?? it?.manusia ?? k);
	let terbuka = $state(false);
</script>

<span class="istilah">
	{#if children}
		{@render children()}
	{:else}
		{label}
	{/if}
	{#if it}
		<button
			type="button"
			class="tanda"
			aria-expanded={terbuka}
			aria-label="apa artinya {it.manusia}?"
			onclick={(e) => { e.preventDefault(); e.stopPropagation(); terbuka = !terbuka; }}
		>?</button>
		{#if terbuka}
			<span class="penjelas" role="note">
				{it.artinya}
				{#if it.teknis}<span class="teknis">istilah teknis: <code>{it.teknis}</code></span>{/if}
			</span>
		{/if}
	{/if}
</span>

<style>
	.istilah { display: inline-flex; align-items: baseline; gap: 0.25rem; position: relative; }
	.tanda {
		display: inline-flex; align-items: center; justify-content: center;
		width: 15px; height: 15px; border-radius: 999px; flex: 0 0 auto;
		border: 1px solid var(--color-line); background: var(--color-surface-2);
		color: var(--color-text-3); font-size: 9px; font-weight: 700; line-height: 1;
		cursor: pointer; padding: 0;
	}
	.tanda:hover, .tanda[aria-expanded='true'] { border-color: var(--color-accent); color: var(--color-accent); }
	.penjelas {
		display: block; position: absolute; left: 0; top: calc(100% + 4px); z-index: 40;
		width: min(22rem, 80vw); padding: 0.5rem 0.7rem;
		background: var(--color-surface-3); border: 1px solid var(--color-accent);
		border-radius: 0.6rem; font-size: 0.75rem; line-height: 1.45;
		color: var(--color-text); font-weight: 400;
	}
	.teknis { display: block; margin-top: 0.3rem; color: var(--color-text-3); font-size: 0.68rem; }
	.teknis code { font-family: var(--font-mono); }
</style>
