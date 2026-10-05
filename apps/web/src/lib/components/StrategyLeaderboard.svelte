<script lang="ts">
	// StrategyLeaderboard: Papan Peringkat Strategi Kuantitatif (Inspirasi Fomo Family).
	// Mengurutkan dan membandingkan performa seluruh mesin sinyal & eksekusi War Room
	// berdasarkan risk-adjusted return, winrate, sampel (N), dan status operasional.
	import { angka } from '$lib/format';

	export interface StrategyItem {
		rank: number;
		id: string;
		nama: string;
		venue: string;
		tipe: 'PAPER' | 'LIVE' | 'SIGNAL-ONLY' | 'RESEARCH';
		winrate_pct: number | null;
		total_r: number | null;
		expectancy_r: number | null;
		n_samples: number;
		max_dd_r: number | null;
		status: 'UNGGUL' | 'PENGUJIAN' | 'FLAG_EXIT' | 'MONITOR';
		status_detail: string;
		/** Friksi terukur (%). Bila tidak diukur, kosongkan — jangan dikarang. */
		friksi_est_pct?: number | null;
	}

	interface Props {
		strategies?: StrategyItem[];
	}

	// PENTING (6 Okt 2026): komponen ini dulu punya `DEFAULT_STRATEGIES` berisi 5
	// strategi KARANGAN (winrate 80%, +3.844R, dll) yang tampil sebagai papan
	// peringkat nyata. Itu melanggar aturan inti produk ("UI tidak boleh mengarang
	// angka"). Default dihapus; baris hanya dibuat dari fakta nyata oleh pemanggil.
	let { strategies = [] }: Props = $props();
</script>

<div class="permukaan-2 rounded-card border border-line p-3" data-testid="strategy-leaderboard">
	<div class="mb-3 flex flex-wrap items-center justify-between gap-2 border-b border-line-soft pb-2">
		<div>
			<div class="flex items-center gap-2">
				<h3 class="text-14 font-bold text-text">Papan Peringkat Strategi</h3>
				<span class="rounded bg-accent/10 px-2 py-0.5 text-10 font-bold uppercase text-accent border border-accent/20">
					Leaderboard
				</span>
			</div>
			<p class="text-11 text-text-3 mt-0.5">
				Peringkat performa strategi kuantitatif lintas instrumen berbasis risk-adjusted return
			</p>
		</div>
		<span class="text-11 font-mono text-text-3">
			{strategies.length} strategi aktif
		</span>
	</div>

	<!-- List / Table Leaderboard dengan Scroll Responsif -->
	{#if strategies.length === 0}
		<div class="py-6 text-center space-y-1">
			<p class="text-12 font-medium text-text-2">Belum ada data strategi yang bisa dibandingkan.</p>
			<p class="text-11 text-text-3">
				Peringkat ini hanya menampilkan strategi dengan bukti terukur (winrate &amp; R dari ledger
				nyata). Kosong berarti belum ada yang memenuhi — bukan diisi contoh.
			</p>
		</div>
	{:else}
		<div class="overflow-x-auto -mx-3 px-3">
			<div class="space-y-2 min-w-[500px]">
			{#each strategies as s (s.id)}
				<div class="flex items-center justify-between gap-3 rounded-card border border-line-soft bg-surface p-2.5 transition-colors hover:border-line">
					<!-- Rank & Info -->
					<div class="flex items-center gap-3 min-w-[200px]">
						<div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full font-mono text-12 font-bold {s.rank === 1 ? 'bg-accent/15 text-accent border border-accent/30' : s.rank === 2 ? 'bg-accent-2/15 text-accent-2 border border-accent-2/30' : s.rank === 3 ? 'bg-warn/15 text-warn border border-warn/30' : 'bg-surface text-text-3 border border-line'}">
							#{s.rank}
						</div>
						<div>
							<div class="flex items-center gap-1.5">
								<span class="font-bold text-12 text-text">{s.nama}</span>
								<span class="rounded px-1.5 py-0.5 text-10 font-mono font-bold {s.tipe === 'LIVE' ? 'bg-pos/20 text-pos' : s.tipe === 'PAPER' ? 'bg-accent/15 text-accent' : 'bg-surface text-text-3 border border-line'}">
									{s.tipe}
								</span>
							</div>
							<div class="flex items-center gap-2 text-10 text-text-3 mt-0.5 font-mono">
								<span>{s.venue}</span>
								{#if s.friksi_est_pct != null}
									<span>·</span>
									<span>Friksi: ~{s.friksi_est_pct}%</span>
								{/if}
							</div>
						</div>
					</div>

					<!-- Metrics -->
					<div class="flex items-center gap-4 text-right">
						<div>
							<span class="text-10 text-text-3 uppercase block">Win Rate</span>
							<span class="angka text-12 font-bold {s.winrate_pct != null && s.winrate_pct >= 50 ? 'text-pos' : s.winrate_pct != null ? 'text-warn' : 'text-text-3'}">
								{s.winrate_pct != null ? `${s.winrate_pct.toFixed(1)}%` : '—'}
							</span>
						</div>

						<div>
							<span class="text-10 text-text-3 uppercase block">Return / R</span>
							<span class="angka text-12 font-bold {s.total_r != null && s.total_r >= 0 ? 'text-pos' : s.total_r != null ? 'text-neg' : 'text-text-3'}">
								{s.total_r != null ? `${s.total_r >= 0 ? '+' : ''}${angka(s.total_r)}R` : '—'}
							</span>
						</div>

						<div>
							<span class="text-10 text-text-3 uppercase block">Sampel</span>
							<span class="text-11 font-mono text-text-2">
								{s.n_samples} n
							</span>
						</div>

						<!-- Status Badge -->
						<div class="w-24 text-right">
							<span class="inline-block rounded px-2 py-0.5 text-10 font-bold {s.status === 'UNGGUL' ? 'bg-pos/15 text-pos border border-pos/30' : s.status === 'FLAG_EXIT' ? 'bg-neg/15 text-neg border border-neg/30' : s.status === 'PENGUJIAN' ? 'bg-warn/15 text-warn border border-warn/30' : 'bg-surface text-text-3 border border-line'}">
								{s.status}
							</span>
						</div>
					</div>
				</div>
			{/each}
			</div>
		</div>
	{/if}
</div>
