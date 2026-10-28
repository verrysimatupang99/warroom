<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { AREAS, SLUG_LAMA } from '$lib/nav';
	import { urlApi } from '$lib/api/client';
	import MarketShell from '$lib/components/MarketShell.svelte';
	import ServerTencentView from '$lib/components/ServerTencentView.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import Skeleton from '$lib/components/Skeleton.svelte';

	const area = AREAS.find((a) => a.kunci === 'sistem')!;
	const sub = $derived.by(() => {
		const s = page.url.searchParams.get('sub') ?? 'layanan';
		return SLUG_LAMA[s] ?? s;
	});

	interface Unit { unit?: string; aktif?: string; sub?: string; aktif_sejak?: string }
	interface Berkas { berkas?: string; umur_s?: number; basi?: boolean }
	interface Status { unit_total?: number; unit_sehat?: number; unit?: Unit[]; berkas?: Berkas[]; waktu?: string }

	let status = $state<Status | null>(null);
	let galatStatus = $state<string | null>(null);
	let memuat = $state(true);

	let kejadian = $state<Record<string, unknown>[]>([]);
	let galatEvent = $state<string | null>(null);
	let params = $state<Record<string, unknown> | null>(null);

	async function ambil<T>(jalur: string): Promise<T | null> {
		try {
			const r = await fetch(urlApi(jalur), { credentials: 'include' });
			const isi = await r.json().catch(() => null);
			if (!r.ok) return null;
			return isi as T;
		} catch {
			return null;
		}
	}

	onMount(async () => {
		const s = await ambil<Status>('/api/v1/sistem/status');
		if (s) status = s;
		else galatStatus = 'Endpoint status layanan tidak menjawab.';
		const ev = await ambil<unknown>('/api/v1/events?limit=10');
		const arr = Array.isArray(ev) ? ev : ((ev as { items?: unknown[] })?.items ?? []);
		kejadian = (arr as Record<string, unknown>[]).slice(0, 10);
		if (!kejadian.length) galatEvent = 'Belum ada kejadian terekam.';
		params = await ambil<Record<string, unknown>>('/api/v1/params');
		memuat = false;
	});
</script>

<svelte:head><title>Sistem | War Room</title></svelte:head>

<MarketShell
	{area}
	aktif={sub}
	judul="Sistem"
	deskripsi="Status layanan, sumber data, kejadian, dan kebijakan yang berlaku. Satu tempat untuk menjawab: apa yang hidup, dari mana angkanya, dan apa batasnya."
	sumber="sistem/status + freshness + events"
>
	{#if sub === 'layanan'}
		{#if memuat}
			<Skeleton baris={4} tinggi={44} />
		{:else if !status}
			<EmptyState judul="Status tidak tersedia" pesan={galatStatus ?? 'Tidak ada jawaban.'} />
		{:else}
			<div class="space-y-4">
				<section class="grid gap-3 sm:grid-cols-3">
					<div class="rounded-card border border-line bg-surface p-4">
						<div class="label-mikro font-mono text-text-3">UNIT SEHAT</div>
						<div class="mt-1 font-mono text-17 font-bold text-text">
							{status.unit_sehat ?? 0}<span class="text-13 text-text-3">/{status.unit_total ?? 0}</span>
						</div>
					</div>
					<div class="rounded-card border border-line bg-surface p-4">
						<div class="label-mikro font-mono text-text-3">BERKAS BASI</div>
						<div class="mt-1 font-mono text-17 font-bold text-text">
							{(status.berkas ?? []).filter((b) => b.basi).length}
							<span class="text-13 text-text-3">/{(status.berkas ?? []).length}</span>
						</div>
					</div>
					<div class="rounded-card border border-line bg-surface p-4">
						<div class="label-mikro font-mono text-text-3">DIPERBARUI</div>
						<div class="mt-1 font-mono text-12 text-text">{status.waktu ?? '—'}</div>
					</div>
				</section>

				<section class="rounded-card border border-line bg-surface p-4">
					<h2 class="text-13 font-bold text-text">Unit</h2>
					<div class="mt-2 overflow-x-auto">
						<table class="w-full text-11 text-left">
							<thead class="border-b border-line text-10 text-text-3">
								<tr><th class="px-2 py-1.5">Unit</th><th class="px-2 py-1.5">Status</th><th class="px-2 py-1.5">Sub</th></tr>
							</thead>
							<tbody class="divide-y divide-line-soft">
								{#each status.unit ?? [] as u (u.unit)}
									<tr>
										<td class="px-2 py-1.5 font-mono text-text">{u.unit}</td>
										<td class="px-2 py-1.5 font-mono" class:text-pos={u.aktif === 'active'} class:text-neg={u.aktif !== 'active'}>{u.aktif ?? '—'}</td>
										<td class="px-2 py-1.5 font-mono text-text-3">{u.sub ?? '—'}</td>
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				</section>
			</div>
		{/if}
	{:else if sub === 'data'}
		<ServerTencentView />
	{:else if sub === 'event'}
		<section class="rounded-card border border-line bg-surface p-4">
			<h2 class="text-13 font-bold text-text">Kejadian terakhir</h2>
			{#if kejadian.length === 0}
				<EmptyState judul="Belum ada kejadian" pesan={galatEvent ?? 'Umpan kejadian kosong.'} ringkas={true} />
			{:else}
				<ul class="mt-2 divide-y divide-line-soft">
					{#each kejadian as k, i (i)}
						<li class="py-1.5 text-11">
							<span class="font-mono text-text-3">{String(k.severity ?? k.type ?? 'info')}</span>
							<span class="ml-2 text-text">{String(k.actor ?? 'sistem')}</span>
							<span class="ml-2 text-text-3">{String(k.created_at ?? '')}</span>
						</li>
					{/each}
				</ul>
			{/if}
		</section>
	{:else if sub === 'kebijakan'}
		<div class="space-y-3">
			<section class="rounded-card border border-line bg-surface p-4">
				<h2 class="text-13 font-bold text-text">Gate yang berlaku</h2>
				<ol class="mt-2 space-y-2 text-12 text-text-2">
					<li><strong class="text-text">Gate A, permukaan.</strong> Unit gagal 0, tidak ada tab kosong, sumber data jelas.</li>
					<li><strong class="text-text">Gate B, bukti.</strong> 100 trade, PF di atas 1,25 setelah biaya, DD di bawah 12%.</li>
					<li><strong class="text-text">Gate C, uang kecil.</strong> Modal $10 sampai $20, batas rugi harian 2%, rekonsiliasi nol.</li>
				</ol>
			</section>
			<section class="rounded-card border border-line bg-surface p-4">
				<h2 class="text-13 font-bold text-text">Parameter aktif</h2>
				{#if params && Object.keys(params).length > 0}
					<dl class="mt-2 grid gap-1.5 text-12 sm:grid-cols-2">
						{#each Object.entries(params).slice(0, 12) as [k, v]}
							<div class="flex justify-between gap-2 border-b border-line-soft py-1">
								<dt class="text-text-3">{k}</dt>
								<dd class="font-mono text-text">{typeof v === 'object' ? JSON.stringify(v).slice(0, 30) : String(v)}</dd>
							</div>
						{/each}
					</dl>
				{:else}
					<EmptyState judul="Parameter tidak terbaca" pesan="Endpoint params tidak mengembalikan data." ringkas={true} />
				{/if}
			</section>
		</div>
	{:else}
		<p class="text-12 text-text-3">Tab tidak dikenal: {sub}</p>
	{/if}
</MarketShell>
