<script lang="ts">
	// Panel "Cara membaca" — jawaban atas keluhan pemilik 7 Okt 2026:
	// "bagian ukur dan eksekusi gw ga ngeh masih, oiya strategi atau metode yang
	// sudah gw sebutkan sebelumnya ya".
	//
	// Alasan panel ini ada: halaman penuh angka tanpa satu kalimat pun yang menjelaskan
	// APA yang sedang diukur dan KENAPA. Isi panel ini ditulis dari kode (nama aturan
	// gate, alur paper, pakem), bukan dari rencana — supaya tidak berbohong.
	import type { Snippet } from 'svelte';

	interface Props {
		judul?: string;
		/** Dibuka sejak awal? Default tertutup supaya tidak mendorong angka ke bawah. */
		bukaAwal?: boolean;
		children: Snippet;
	}
	let { judul = 'Cara membaca tab ini', bukaAwal = false, children }: Props = $props();
	let terbuka = $state(bukaAwal);
</script>

<div class="rounded-card border border-line-soft bg-surface-2/40">
	<button
		type="button"
		class="flex w-full items-center justify-between gap-2 px-3 py-2 text-left"
		aria-expanded={terbuka}
		onclick={() => (terbuka = !terbuka)}
	>
		<span class="text-12 font-medium text-text-2">ⓘ {judul}</span>
		<span class="text-10 text-text-3">{terbuka ? '▲ tutup' : '▼ buka'}</span>
	</button>
	{#if terbuka}
		<div class="space-y-2 border-t border-line-soft px-3 py-2.5 text-12 text-text-2">
			{@render children()}
		</div>
	{/if}
</div>
