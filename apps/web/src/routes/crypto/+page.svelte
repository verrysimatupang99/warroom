<script lang="ts">
	import { onMount } from 'svelte';

	interface Posisi {
		koin: string;
		entry: number;
		harga: number;
		qty: number;
		puncak: number;
		pl_pct: number;
	}

	interface Dagang {
		waktu: string;
		koin: string;
		aksi: string;
		harga: string;
		qty: string;
		pnl_pct: string;
		alasan: string;
	}

	interface Ringkas {
		aktif: boolean;
		jumlah_koin: number;
		modal: number;
		ekuitas_perkiraan: number;
		return_pct: number;
		posisi_terbuka: number;
		posisi: Posisi[];
		trade_terakhir: Dagang[];
		catatan: string;
	}

	let data = $state<Ringkas | null>(null);
	let galat = $state('');

	async function muat() {
		try {
			const r = await fetch('/api/v1/tencent/crypto/momentum');
			if (r.ok) data = await r.json();
			else galat = `HTTP ${r.status}`;
		} catch (e) {
			galat = 'gagal menghubungi API';
			console.error(e);
		}
	}

	onMount(() => {
		muat();
		const t = setInterval(muat, 60_000);
		return () => clearInterval(t);
	});

	const angka = (n: number) => n.toLocaleString('en-US', { maximumFractionDigits: 2 });
</script>

<svelte:head>
	<title>Crypto — Paper Trader Momentum | War Room</title>
</svelte:head>

<div class="mx-auto max-w-5xl space-y-6 p-4 md:p-8">
	<header class="space-y-2">
		<p class="font-mono text-[11px] uppercase tracking-[0.2em] text-amber-400/80">
			Crypto · Paper Trading
		</p>
		<h1 class="text-2xl font-semibold text-white">Momentum Donchian</h1>
		<p class="max-w-2xl text-sm text-zinc-400">
			Strategi yang lolos uji walk-forward: breakout 55 bar, trailing 3×ATR, risiko 2% per
			trade. <strong class="text-zinc-200">Tanpa order nyata</strong> — hanya pencatatan.
		</p>
	</header>

	{#if galat}
		<p class="rounded border border-red-500/30 bg-red-500/10 p-3 font-mono text-xs text-red-300">
			{galat}
		</p>
	{:else if !data}
		<p class="font-mono text-xs text-zinc-500">memuat…</p>
	{:else if !data.aktif}
		<p class="rounded border border-white/10 bg-white/5 p-4 font-mono text-xs text-zinc-400">
			Paper trader belum pernah berjalan. Jalankan <code>warroom-momentum-paper.timer</code>.
		</p>
	{:else}
		<div class="grid grid-cols-2 gap-3 md:grid-cols-4">
			<div class="rounded-lg border border-white/10 bg-white/[0.03] p-4">
				<p class="font-mono text-[10px] uppercase tracking-wider text-zinc-500">Modal</p>
				<p class="mt-1 font-mono text-lg text-white">${angka(data.modal)}</p>
			</div>
			<div class="rounded-lg border border-white/10 bg-white/[0.03] p-4">
				<p class="font-mono text-[10px] uppercase tracking-wider text-zinc-500">Ekuitas</p>
				<p class="mt-1 font-mono text-lg text-white">${angka(data.ekuitas_perkiraan)}</p>
			</div>
			<div class="rounded-lg border border-white/10 bg-white/[0.03] p-4">
				<p class="font-mono text-[10px] uppercase tracking-wider text-zinc-500">Return</p>
				<p
					class="mt-1 font-mono text-lg {data.return_pct >= 0
						? 'text-emerald-400'
						: 'text-red-400'}"
				>
					{data.return_pct >= 0 ? '+' : ''}{data.return_pct.toFixed(2)}%
				</p>
			</div>
			<div class="rounded-lg border border-white/10 bg-white/[0.03] p-4">
				<p class="font-mono text-[10px] uppercase tracking-wider text-zinc-500">Posisi</p>
				<p class="mt-1 font-mono text-lg text-white">
					{data.posisi_terbuka}<span class="text-sm text-zinc-500">/{data.jumlah_koin}</span>
				</p>
			</div>
		</div>

		<section class="rounded-lg border border-white/10 bg-white/[0.02]">
			<h2
				class="border-b border-white/10 px-4 py-3 font-mono text-xs uppercase tracking-wider text-zinc-400"
			>
				Posisi Terbuka
			</h2>
			{#if data.posisi.length === 0}
				<p class="p-4 text-center font-mono text-xs text-zinc-500">
					Tidak ada posisi — menunggu breakout 55 bar.
				</p>
			{:else}
				<div class="overflow-x-auto">
					<table class="w-full border-collapse text-left font-mono text-xs">
						<thead>
							<tr
								class="border-b border-white/10 bg-white/[0.02] text-[11px] uppercase tracking-wider text-zinc-400"
							>
								<th class="px-3 py-2.5">Koin</th>
								<th class="px-3 py-2.5">Entry</th>
								<th class="px-3 py-2.5">Harga</th>
								<th class="px-3 py-2.5">Puncak</th>
								<th class="px-3 py-2.5">P/L</th>
							</tr>
						</thead>
						<tbody>
							{#each data.posisi as p (p.koin)}
								<tr class="border-b border-white/5">
									<td class="px-3 py-2 text-white">{p.koin}</td>
									<td class="px-3 py-2 text-zinc-300">{p.entry}</td>
									<td class="px-3 py-2 text-zinc-300">{p.harga}</td>
									<td class="px-3 py-2 text-zinc-500">{p.puncak}</td>
									<td class="px-3 py-2 {p.pl_pct >= 0 ? 'text-emerald-400' : 'text-red-400'}">
										{p.pl_pct >= 0 ? '+' : ''}{p.pl_pct.toFixed(2)}%
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{/if}
		</section>

		<section class="rounded-lg border border-white/10 bg-white/[0.02]">
			<h2
				class="border-b border-white/10 px-4 py-3 font-mono text-xs uppercase tracking-wider text-zinc-400"
			>
				Trade Terakhir
			</h2>
			{#if data.trade_terakhir.length === 0}
				<p class="p-4 text-center font-mono text-xs text-zinc-500">Belum ada trade.</p>
			{:else}
				<div class="overflow-x-auto">
					<table class="w-full border-collapse text-left font-mono text-xs">
						<thead>
							<tr
								class="border-b border-white/10 bg-white/[0.02] text-[11px] uppercase tracking-wider text-zinc-400"
							>
								<th class="px-3 py-2.5">Waktu</th>
								<th class="px-3 py-2.5">Koin</th>
								<th class="px-3 py-2.5">Aksi</th>
								<th class="px-3 py-2.5">Harga</th>
								<th class="px-3 py-2.5">P/L</th>
								<th class="px-3 py-2.5">Alasan</th>
							</tr>
						</thead>
						<tbody>
							{#each data.trade_terakhir as t, i (i)}
								<tr class="border-b border-white/5">
									<td class="px-3 py-2 text-zinc-500"
										>{t.waktu.slice(0, 16).replace('T', ' ')}</td
									>
									<td class="px-3 py-2 text-white">{t.koin}</td>
									<td class="px-3 py-2 text-zinc-300">{t.aksi}</td>
									<td class="px-3 py-2 text-zinc-300">{t.harga}</td>
									<td
										class="px-3 py-2 {t.pnl_pct?.startsWith('-')
											? 'text-red-400'
											: 'text-emerald-400'}"
									>
										{t.pnl_pct || '—'}
									</td>
									<td class="px-3 py-2 text-zinc-500">{t.alasan}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{/if}
		</section>

		<p class="font-mono text-[11px] text-zinc-500">{data.catatan}</p>
	{/if}
</div>
