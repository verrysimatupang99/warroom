<script lang="ts">
	import { onMount } from 'svelte';
	import AreaView from '$lib/components/AreaView.svelte';
	import LiveMT5ExecutionCard from '$lib/components/LiveMT5ExecutionCard.svelte';

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
	});
</script>

<div class="space-y-6">
	<!-- Panel Eksekusi Live MT5 Utama -->
	<LiveMT5ExecutionCard />

	<!-- Ringkasan Statistik Histori -->
	<div class="rounded-card border border-line bg-surface p-5 shadow-2xl backdrop-blur">
		<div class="flex flex-wrap items-center justify-between gap-3 border-b border-line-soft pb-4">
			<div>
				<h2 class="font-mono text-base font-bold text-white flex items-center gap-2">
					<svg class="h-4 w-4 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
					</svg>
					RIWAYAT PERDAGANGAN MT5 LENGKAP (ORDER & DEAL AUDIT)
				</h2>
				<p class="text-xs text-zinc-400 font-sans mt-0.5">
					Catatan riwayat transaksi algo trading Gold (XAUUSDm) pada akun Exness
					{historyData?.account ? `#${historyData.account}` : ''}
				</p>
			</div>

			<div class="flex items-center gap-2">
				<span class="rounded bg-white/5 px-2.5 py-1 text-xs font-mono text-zinc-300 border border-white/10">
					Total: <strong class="text-white">{historyData?.total_trades ?? 0}</strong> Trades
				</span>
				<span class="rounded bg-emerald-500/10 px-2.5 py-1 text-xs font-mono text-emerald-400 border border-emerald-500/20">
					Menang: <strong>{historyData?.wins ?? 0}</strong>
					({historyData?.win_rate_pct ?? 0}%)
				</span>
				<span class="rounded bg-rose-500/10 px-2.5 py-1 text-xs font-mono text-rose-400 border border-rose-500/20">
					Kalah: <strong>{historyData?.losses ?? 0}</strong>
				</span>
				<span class="rounded bg-white/5 px-2.5 py-1 text-xs font-mono text-zinc-300 border border-white/10">
					Net: <strong class="text-white">{historyData?.net_pnl_usd ?? 0}</strong> USD
				</span>
			</div>
		</div>

		<!-- Tabel Riwayat Transaksi Lengkap -->
		<div class="mt-4 overflow-x-auto">
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

	<!-- Konten standar overview pasar Forex -->
	<AreaView kunci="forex" />
</div>
