<script lang="ts">
	// Tab Sinyal forex: level XAUUSD dari Laya Sentinel, plus bias bila tersedia.
	import { onMount } from 'svelte';
	import { urlApi } from '$lib/api/client';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import Skeleton from '$lib/components/Skeleton.svelte';

	interface Level {
		symbol?: string; play?: string; status?: string; price?: number; trend?: string;
		strategy?: string; reason?: string; blocked_reason?: string; side?: string;
		entry?: number; sl?: number; tp?: number;
	}

	let level = $state<Level | null>(null);
	let bias = $state<Record<string, unknown> | null>(null);
	let galat = $state<string | null>(null);
	let memuat = $state(true);

	async function j<T>(jalur: string): Promise<T | null> {
		try {
			const r = await fetch(urlApi(jalur), { credentials: 'include' });
			const isi = await r.json().catch(() => null);
			if (!r.ok) {
				galat = isi?.error?.message ?? isi?.detail?.message ?? `HTTP ${r.status}`;
				return null;
			}
			return isi as T;
		} catch (e) {
			galat = e instanceof Error ? e.message : 'gagal menghubungi API';
			return null;
		}
	}

	onMount(async () => {
		level = await j<Level>('/api/v1/tencent/forex/levels?symbol=XAUUSD');
		bias = await j<Record<string, unknown>>('/api/v1/tencent/forex/bias');
		memuat = false;
	});
</script>

{#if memuat}
	<Skeleton baris={3} tinggi={44} />
{:else if !level}
	<EmptyState
		judul="Level belum tersedia"
		pesan={galat ?? 'Laya Sentinel tidak mengembalikan level untuk XAUUSD.'}
	/>
{:else}
	<div class="space-y-4">
		<section class="rounded-card border border-line bg-surface p-4">
			<div class="flex flex-wrap items-center gap-2">
				<span class="label-mikro font-mono text-text-3">XAUUSD</span>
				<span class="rounded border border-line px-2 py-0.5 font-mono text-10 uppercase text-accent">
					{level.status ?? 'TANPA STATUS'}
				</span>
				<span class="font-mono text-11 text-text-3">{level.strategy ?? ''}</span>
			</div>
			<dl class="mt-3 grid gap-2 text-12 sm:grid-cols-2 lg:grid-cols-4">
				<div>
					<dt class="text-text-3">Harga</dt>
					<dd class="font-mono text-15 font-bold text-text">{level.price ?? '—'}</dd>
				</div>
				<div>
					<dt class="text-text-3">Tren</dt>
					<dd class="font-mono text-15 font-bold text-text">{level.trend ?? '—'}</dd>
				</div>
				<div>
					<dt class="text-text-3">Sisi</dt>
					<dd class="font-mono text-15 font-bold text-text">{level.side ?? '—'}</dd>
				</div>
				<div>
					<dt class="text-text-3">Play</dt>
					<dd class="font-mono text-15 font-bold text-text">{level.play ?? '—'}</dd>
				</div>
			</dl>
			{#if level.reason}
				<p class="mt-3 border-t border-line-soft pt-2 text-11 text-text-2">{level.reason}</p>
			{/if}
			{#if level.blocked_reason}
				<p class="mt-1 font-mono text-11 text-neg">{level.blocked_reason}</p>
			{/if}
		</section>

		{#if bias && Object.keys(bias).length > 0}
			<section class="rounded-card border border-line bg-surface p-4">
				<h2 class="text-13 font-bold text-text">Bias Laya</h2>
				<dl class="mt-2 grid gap-1.5 text-12 sm:grid-cols-2">
					{#each Object.entries(bias).slice(0, 8) as [k, v]}
						<div class="flex justify-between gap-2 border-b border-line-soft py-1">
							<dt class="text-text-3">{k}</dt>
							<dd class="font-mono text-text">{typeof v === 'object' ? JSON.stringify(v).slice(0, 40) : String(v)}</dd>
						</div>
					{/each}
				</dl>
			</section>
		{/if}
	</div>
{/if}
