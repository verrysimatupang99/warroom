<script lang="ts">
	import { onMount } from 'svelte';
	import ForexCockpitExness from '$lib/components/ForexCockpitExness.svelte';

	interface TradeRecord {
		id: number;
		ticket: number;
		deal_in: number;
		deal_out: number;
		time_open: string;
		time_close: string;
		symbol: string;
		type: string;
		volume: number;
		open_price: number;
		close_price: number;
		sl: number;
		tp: number;
		pnl_usd: number;
		return_pct: number;
		status: 'WIN' | 'LOSS';
		reason: string;
	}

	interface MT5HistoryData {
		account: string;
		broker: string;
		total_trades: number;
		wins: number;
		losses: number;
		win_rate_pct: number;
		net_pnl_usd: number;
		records: TradeRecord[];
	}

	let historyData = $state<MT5HistoryData | null>(null);
	let loading = $state(true);

	interface PanelRow {
		nama: string;
		risk_pct: number;
		target_pct: number;
		stop_pct: number;
		ekuitas: number;
		total_pct: number;
		hari_pct: number;
		trades_hari: number;
		max_trades: number;
		berhenti: boolean;
		alasan: string;
	}

	let panels = $state<PanelRow[]>([]);

	async function muatPanel() {
		try {
			const res = await fetch('/api/v1/tencent/mt5/panels');
			if (res.ok) {
				const d = await res.json();
				panels = d.panels ?? [];
			}
		} catch (err) {
			console.error('Gagal memuat panel simulator:', err);
		}
	}

	async function muatHistory() {
		try {
			const res = await fetch('/api/v1/tencent/mt5/history');
			if (res.ok) {
				historyData = await res.json();
			}
		} catch (err) {
			console.error('Gagal memuat history MT5:', err);
		} finally {
			loading = false;
		}
	}

	onMount(() => {
		muatHistory();
		muatPanel();
		const interval = setInterval(() => {
			muatHistory();
			muatPanel();
		}, 5000);
		return () => clearInterval(interval);
	});
</script>

<svelte:head>
	<title>Forex & Gold (XAUUSD) Cockpit — War Room Exness MT5</title>
</svelte:head>

<div class="space-y-6 max-w-7xl mx-auto pb-12 pt-2">
	<!-- COCKPIT UTAMA EXNESS + LAYA SENTINEL + RADAR PRE-FLIGHT -->
	<ForexCockpitExness />

	<!-- SIMULATOR 3 PANEL: PERBANDINGAN SKEMA SIZING + DAILY RATCHET -->
	<div class="rounded-xl border border-line bg-surface/90 p-5 shadow-2xl backdrop-blur">
		<div class="flex flex-wrap items-center justify-between gap-3 border-b border-line-soft pb-4 mb-4">
			<div>
				<h2 class="font-mono text-base font-bold text-white flex items-center gap-2">
					<svg class="h-4 w-4 text-sky-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 6l3 1m0 0l-3 9a5.002 5.002 0 006.001 0M6 7l3 9M6 7l6-2m6 2l3-1m-3 1l-3 9a5.002 5.002 0 006.001 0M18 7l3 9m-3-9l-6-2m0-2v2m0 16V5m0 16H9m3 0h3" />
					</svg>
					SIMULATOR 3 PANEL (A/B/C) — SIZING &amp; DAILY RATCHET
				</h2>
				<p class="text-xs text-zinc-400 font-sans mt-0.5">
					Perbandingan skema risiko pada sinyal yang sama. Simulasi, bukan order nyata.
				</p>
			</div>
			<span class="rounded bg-white/5 px-2.5 py-1 font-mono text-xs text-zinc-300 border border-white/10">
				Modal awal: <strong class="text-white">$500</strong> per panel
			</span>
		</div>

		{#if panels.length === 0}
			<p class="py-4 text-center text-xs text-zinc-400 font-mono">
				Simulator belum berjalan atau belum ada data.
			</p>
		{:else}
			<div class="overflow-x-auto">
				<table class="w-full text-left font-mono text-xs border-collapse">
					<thead>
						<tr class="border-b border-white/10 text-zinc-400 uppercase tracking-wider text-[11px] bg-white/[0.02]">
							<th class="py-2.5 px-3">Panel</th>
							<th class="py-2.5 px-3">Risiko / Target / Stop</th>
							<th class="py-2.5 px-3">Ekuitas</th>
							<th class="py-2.5 px-3">Total</th>
							<th class="py-2.5 px-3">Hari Ini</th>
							<th class="py-2.5 px-3">Trade</th>
							<th class="py-2.5 px-3">Status</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-white/5">
						{#each panels as p}
							<tr class="hover:bg-white/[0.02] transition">
								<td class="py-3 px-3 font-bold text-white">{p.nama}</td>
								<td class="py-3 px-3 text-zinc-300">{p.risk_pct}% / {p.target_pct}% / -{p.stop_pct}%</td>
								<td class="py-3 px-3 text-zinc-200">${p.ekuitas.toFixed(2)}</td>
								<td class="py-3 px-3 font-bold {p.total_pct >= 0 ? 'text-emerald-400' : 'text-rose-400'}">
									{p.total_pct >= 0 ? '+' : ''}{p.total_pct.toFixed(2)}%
								</td>
								<td class="py-3 px-3 font-bold {p.hari_pct >= 0 ? 'text-emerald-400' : 'text-rose-400'}">
									{p.hari_pct >= 0 ? '+' : ''}{p.hari_pct.toFixed(2)}%
								</td>
								<td class="py-3 px-3 text-zinc-300">{p.trades_hari}/{p.max_trades}</td>
								<td class="py-3 px-3">
									<span class="inline-flex rounded px-2 py-0.5 text-[10px] font-bold {p.berhenti ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20' : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'}">
										{p.berhenti ? 'STOP' : 'AKTIF'}
									</span>
									{#if p.alasan}
										<div class="text-[10px] text-zinc-400 mt-1 max-w-[220px] font-sans">{p.alasan}</div>
									{/if}
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	</div>

	<!-- AUDIT HISTORI DEAL & ORDER RIIL EXNESS -->
	<div class="rounded-xl border border-line bg-surface/90 p-5 shadow-2xl backdrop-blur">
		<div class="flex flex-wrap items-center justify-between gap-3 border-b border-line-soft pb-4 mb-4">
			<div>
				<h2 class="font-mono text-base font-bold text-white flex items-center gap-2">
					<svg class="h-4 w-4 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
					</svg>
					RIWAYAT PERDAGANGAN DEAL AUDIT (EXNESS MT5 #416510164)
				</h2>
				<p class="text-xs text-zinc-400 font-sans mt-0.5">
					Catatan transaksi forward testing algo trading Gold (XAUUSDm) pada akun Exness demo
				</p>
			</div>

			<div class="flex items-center gap-2 font-mono text-xs">
				<span class="rounded bg-white/5 px-2.5 py-1 text-zinc-300 border border-white/10">
					Total: <strong class="text-white">{historyData?.total_trades ?? 0}</strong> Trades
				</span>
				<span class="rounded bg-emerald-500/10 px-2.5 py-1 text-emerald-400 border border-emerald-500/20">
					Win: <strong>{historyData?.wins ?? 0}</strong> ({historyData?.win_rate_pct ?? 0}%)
				</span>
				<span class="rounded bg-rose-500/10 px-2.5 py-1 text-rose-400 border border-rose-500/20">
					Loss: <strong>{historyData?.losses ?? 0}</strong>
				</span>
				<span class="rounded bg-white/5 px-2.5 py-1 text-zinc-300 border border-white/10">
					Net PnL: <strong class="{historyData?.net_pnl_usd && historyData.net_pnl_usd >= 0 ? 'text-emerald-400' : 'text-rose-400'}">
						{historyData?.net_pnl_usd ?? 0} USD
					</strong>
				</span>
			</div>
		</div>

		<!-- TABEL DEAL LENGKAP -->
		<div class="overflow-x-auto">
			<table class="w-full text-left font-mono text-xs border-collapse">
				<thead>
					<tr class="border-b border-white/10 text-zinc-400 uppercase tracking-wider text-[11px] bg-white/[0.02]">
						<th class="py-2.5 px-3">#</th>
						<th class="py-2.5 px-3">Waktu Buka / Tutup</th>
						<th class="py-2.5 px-3">Simbol & Sisi</th>
						<th class="py-2.5 px-3">Volume</th>
						<th class="py-2.5 px-3">Harga Buka</th>
						<th class="py-2.5 px-3">Harga Tutup</th>
						<th class="py-2.5 px-3">SL / TP</th>
						<th class="py-2.5 px-3">Hasil (PnL)</th>
						<th class="py-2.5 px-3">Status & Keterangan</th>
					</tr>
				</thead>
				<tbody class="divide-y divide-white/5">
					{#if loading}
						<tr>
							<td colspan="9" class="py-6 text-center text-zinc-400">
								Memuat riwayat transaksi dari terminal MT5...
							</td>
						</tr>
					{:else if !historyData || historyData.records.length === 0}
						<tr>
							<td colspan="9" class="py-6 text-center text-zinc-400">
								Belum ada transaksi riwayat yang tersimpan.
							</td>
						</tr>
					{:else}
						{#each historyData.records as rec}
							<tr class="hover:bg-white/[0.02] transition">
								<td class="py-3 px-3 text-zinc-400 font-semibold">{rec.id}</td>
								<td class="py-3 px-3">
									<div class="text-zinc-200">{rec.time_open}</div>
									<div class="text-[10px] text-zinc-400">{rec.time_close}</div>
								</td>
								<td class="py-3 px-3">
									<div class="flex items-center gap-1.5">
										<span class="rounded px-1.5 py-0.5 text-[10px] font-bold {rec.type === 'BUY' ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 'bg-rose-500/20 text-rose-400 border border-rose-500/30'}">
											{rec.type}
										</span>
										<span class="font-bold text-white">{rec.symbol}</span>
									</div>
									<div class="text-[10px] text-zinc-400 mt-0.5">Tiket #{rec.ticket}</div>
								</td>
								<td class="py-3 px-3 text-zinc-300">{rec.volume} Lot</td>
								<td class="py-3 px-3 text-zinc-300">{rec.open_price.toFixed(2)}</td>
								<td class="py-3 px-3 text-zinc-300">{rec.close_price.toFixed(2)}</td>
								<td class="py-3 px-3">
									<div class="text-zinc-400">SL: <span class="text-rose-400">{rec.sl.toFixed(2)}</span></div>
									<div class="text-zinc-400">TP: <span class="text-emerald-400">{rec.tp.toFixed(2)}</span></div>
								</td>
								<td class="py-3 px-3">
									<div class="font-bold text-sm {rec.pnl_usd >= 0 ? 'text-emerald-400' : 'text-rose-400'}">
										{rec.pnl_usd >= 0 ? '+' : ''}${rec.pnl_usd.toFixed(2)}
									</div>
									<div class="text-[10px] {rec.return_pct >= 0 ? 'text-emerald-400' : 'text-rose-400'}">
										{rec.return_pct >= 0 ? '+' : ''}{rec.return_pct.toFixed(1)}%
									</div>
								</td>
								<td class="py-3 px-3">
									<span class="inline-flex items-center rounded px-2 py-0.5 text-[10px] font-bold {rec.status === 'WIN' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'}">
										{rec.status}
									</span>
									<div class="text-[11px] text-zinc-400 mt-1 max-w-[220px] font-sans">
										{rec.reason}
									</div>
								</td>
							</tr>
						{/each}
					{/if}
				</tbody>
			</table>
		</div>
	</div>
</div>
