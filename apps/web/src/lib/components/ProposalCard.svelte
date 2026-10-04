<script lang="ts">
	// ProposalCard (P5-T4): usulan parameter learner — dari→ke, alasan, bukti, gate, status.
	// Tombol terapkan/rollback hanya muncul untuk peran owner (API tetap penjaga terakhir: 403/409).
	// Angka ditampilkan apa adanya; bukti yang bukan angka tampil sebagai teks mentah.
	import type { Proposal } from '$lib/api/types';
	import { teksNilai, waktuWIB } from '$lib/format';
	import EmptyState from './EmptyState.svelte';

	interface Props {
		proposals: Proposal[] | null;
		memuat?: boolean;
		galat?: string | null;
		peran?: string | null;
		onexec?: ((id: number, aksi: 'apply' | 'rollback') => Promise<void> | void) | null;
	}
	let { proposals, memuat = false, galat = null, peran = null, onexec = null }: Props = $props();

	const bolehAksi = $derived(peran === 'owner');

	const nadaStatus: Record<string, string> = {
		diterapkan: 'text-pos border-pos/40 bg-pos/10',
		ditolak: 'text-neg border-neg/40 bg-neg/10',
		butuh_manusia: 'text-warn border-warn/40 bg-warn/10',
		dibatalkan: 'text-text-3 border-line bg-surface-2',
		menunggu: 'text-accent border-accent/40 bg-accent/10'
	};

	// Ringkas bukti menjadi baris-baris kunci=nilai pendek; struktur bersarang tetap JSON pendek.
	function ringkasBukti(bukti: unknown): string[] {
		if (bukti == null || typeof bukti !== 'object') return [];
		return Object.entries(bukti as Record<string, unknown>)
			.slice(0, 8)
			.map(([k, v]) => `${k}=${teksNilai(v)}`);
	}
</script>

{#if galat}
	<p class="text-13 text-neg">{galat}</p>
{:else if memuat && !proposals}
	<p class="text-13 text-text-3">memuat usulan…</p>
{:else if !proposals || proposals.length === 0}
	<EmptyState
		judul="Belum ada usulan parameter"
		pesan="Learner menulis usulan ke tabel proposals; belum ada yang tercatat."
	/>
{:else}
	<div class="space-y-2" data-testid="proposal-list">
		{#each proposals as p (p.id)}
			<article class="rounded-control border border-line bg-surface-2/40 p-3" data-testid="proposal-card">
				<div class="flex flex-wrap items-center gap-2">
					<span class="angka text-12 text-text">{p.parameter}</span>
					<span class="label-mikro rounded-control border px-2 py-0.5 {nadaStatus[p.status] ?? 'text-text-3 border-line'}">
						{p.status}
					</span>
					{#if p.gate}<span class="label-mikro rounded-control border border-line px-2 py-0.5 text-text-3">gate {p.gate}</span>{/if}
					<span class="angka ml-auto text-11 text-text-3">
						#{p.id}{#if p.dibuat} · {waktuWIB(p.dibuat)}{/if}
					</span>
				</div>

				<p class="angka mt-2 text-13 text-text-2">
					{teksNilai(p.dari)} <span class="text-text-3">→</span> <span class="text-accent">{teksNilai(p.ke)}</span>
				</p>
				<p class="mt-1 text-12 text-text-2">{p.alasan || '—'}</p>

				{#if ringkasBukti(p.bukti).length}
					<p class="angka mt-1 flex flex-wrap gap-x-3 gap-y-1 text-11 text-text-3">
						{#each ringkasBukti(p.bukti) as b}<span>{b}</span>{/each}
					</p>
				{/if}

				{#if p.ditolak_karena}
					<p class="mt-1 text-11 text-neg">ditolak: {p.ditolak_karena}</p>
				{/if}
				{#if p.diputuskan_oleh}
					<p class="mt-1 text-11 text-text-3">
						diputuskan oleh <span class="angka">{p.diputuskan_oleh}</span>
						{#if p.diterapkan_pada}· {waktuWIB(p.diterapkan_pada)}{/if}
					</p>
				{/if}

				{#if bolehAksi && onexec}
					<div class="mt-2 flex flex-wrap gap-2">
						{#if p.status === 'butuh_manusia'}
							<button
								class="rounded-control border border-line px-2 py-0.5 text-11 text-text-2"
								onclick={() => onexec(p.id, 'apply')}>terapkan</button
							>
						{/if}
						{#if p.status === 'diterapkan'}
							<button
								class="rounded-control border border-line px-2 py-0.5 text-11 text-text-2"
								onclick={() => onexec(p.id, 'rollback')}>rollback</button
							>
						{/if}
					</div>
				{/if}
			</article>
		{/each}
	</div>
{/if}
