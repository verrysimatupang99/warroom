<script lang="ts">
	import { onMount } from 'svelte';

	interface Unit {
		unit: string;
		aktif: string;
		sehat: boolean;
	}

	interface Berkas {
		berkas: string;
		ada: boolean;
		umur_s: number | null;
		basi: boolean;
		ambang_s?: number;
	}

	interface Status {
		waktu: number;
		unit_total: number;
		unit_sehat: number;
		unit: Unit[];
		berkas: Berkas[];
	}

	let data = $state<Status | null>(null);
	let galat = $state('');

	async function muat() {
		try {
			const r = await fetch('/api/v1/sistem/status');
			if (r.ok) {
				data = await r.json();
				galat = '';
			} else {
				galat = `HTTP ${r.status}`;
			}
		} catch (e) {
			galat = 'gagal menghubungi API';
			console.error(e);
		}
	}

	onMount(() => {
		muat();
		const t = setInterval(muat, 30_000);
		return () => clearInterval(t);
	});

	function umur(s: number | null): string {
		if (s === null) return '—';
		if (s < 60) return `${s} dtk`;
		if (s < 3600) return `${Math.floor(s / 60)} mnt`;
		if (s < 86400) return `${Math.floor(s / 3600)} jam`;
		return `${Math.floor(s / 86400)} hari`;
	}

	const namaBerkas = (p: string) => p.split('/').pop() ?? p;
</script>

<svelte:head>
	<title>Sistem &amp; Layanan | War Room</title>
</svelte:head>

<div class="mx-auto max-w-5xl space-y-6 p-4 md:p-8">
	<header class="space-y-2">
		<p class="font-mono text-[11px] uppercase tracking-[0.2em] text-amber-400/80">
			Infrastruktur
		</p>
		<h1 class="text-2xl font-semibold text-white">Status Layanan</h1>
		<p class="text-sm text-zinc-400">
			Unit systemd dan kesegaran berkas data. Diperbarui tiap 30 detik.
		</p>
	</header>

	{#if galat}
		<p class="rounded border border-red-500/30 bg-red-500/10 p-3 font-mono text-xs text-red-300">
			{galat}
		</p>
	{:else if !data}
		<p class="font-mono text-xs text-zinc-500">memuat…</p>
	{:else}
		<div class="grid grid-cols-2 gap-3 md:grid-cols-3">
			<div class="rounded-lg border border-white/10 bg-white/[0.03] p-4">
				<p class="font-mono text-[10px] uppercase tracking-wider text-zinc-500">Unit Sehat</p>
				<p
					class="mt-1 font-mono text-lg {data.unit_sehat === data.unit_total
						? 'text-emerald-400'
						: 'text-amber-400'}"
				>
					{data.unit_sehat}<span class="text-sm text-zinc-500">/{data.unit_total}</span>
				</p>
			</div>
			<div class="rounded-lg border border-white/10 bg-white/[0.03] p-4">
				<p class="font-mono text-[10px] uppercase tracking-wider text-zinc-500">Berkas Basi</p>
				<p class="mt-1 font-mono text-lg {data.berkas.some((b) => b.basi) ? 'text-amber-400' : 'text-emerald-400'}">
					{data.berkas.filter((b) => b.basi).length}<span class="text-sm text-zinc-500"
						>/{data.berkas.length}</span
					>
				</p>
			</div>
			<div class="rounded-lg border border-white/10 bg-white/[0.03] p-4">
				<p class="font-mono text-[10px] uppercase tracking-wider text-zinc-500">Diperiksa</p>
				<p class="mt-1 font-mono text-sm text-zinc-300">
					{new Date(data.waktu * 1000).toLocaleTimeString('id-ID')}
				</p>
			</div>
		</div>

		<section class="rounded-lg border border-white/10 bg-white/[0.02]">
			<h2
				class="border-b border-white/10 px-4 py-3 font-mono text-xs uppercase tracking-wider text-zinc-400"
			>
				Unit Systemd
			</h2>
			<div class="overflow-x-auto">
				<table class="w-full border-collapse text-left font-mono text-xs">
					<thead>
						<tr
							class="border-b border-white/10 bg-white/[0.02] text-[11px] uppercase tracking-wider text-zinc-400"
						>
							<th class="px-3 py-2.5">Unit</th>
							<th class="px-3 py-2.5">Status</th>
						</tr>
					</thead>
					<tbody>
						{#each data.unit as u (u.unit)}
							<tr class="border-b border-white/5">
								<td class="px-3 py-2 text-zinc-200">{u.unit}</td>
								<td class="px-3 py-2">
									<span
										class="rounded px-2 py-0.5 text-[11px] {u.sehat
											? 'bg-emerald-500/15 text-emerald-400'
											: 'bg-red-500/15 text-red-400'}"
									>
										{u.aktif}
									</span>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</section>

		<section class="rounded-lg border border-white/10 bg-white/[0.02]">
			<h2
				class="border-b border-white/10 px-4 py-3 font-mono text-xs uppercase tracking-wider text-zinc-400"
			>
				Kesegaran Data
			</h2>
			<div class="overflow-x-auto">
				<table class="w-full border-collapse text-left font-mono text-xs">
					<thead>
						<tr
							class="border-b border-white/10 bg-white/[0.02] text-[11px] uppercase tracking-wider text-zinc-400"
						>
							<th class="px-3 py-2.5">Berkas</th>
							<th class="px-3 py-2.5">Umur</th>
							<th class="px-3 py-2.5">Ambang</th>
							<th class="px-3 py-2.5">Status</th>
						</tr>
					</thead>
					<tbody>
						{#each data.berkas as b (b.berkas)}
							<tr class="border-b border-white/5">
								<td class="px-3 py-2 text-zinc-200">{namaBerkas(b.berkas)}</td>
								<td class="px-3 py-2 text-zinc-400">{b.ada ? umur(b.umur_s) : 'tidak ada'}</td>
								<td class="px-3 py-2 text-zinc-500">{b.ambang_s ? umur(b.ambang_s) : '—'}</td>
								<td class="px-3 py-2">
									<span
										class="rounded px-2 py-0.5 text-[11px] {b.basi
											? 'bg-amber-500/15 text-amber-400'
											: 'bg-emerald-500/15 text-emerald-400'}"
									>
										{b.basi ? 'basi' : 'segar'}
									</span>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</section>
	{/if}
</div>
