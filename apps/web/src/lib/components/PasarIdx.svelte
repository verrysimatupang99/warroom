<script lang="ts">
	import JudulBagian from './JudulBagian.svelte';

	interface Props {
		sub: string;
	}
	let { sub }: Props = $props();
</script>

<div class="mb-4 bg-gradient-to-r from-emerald-950/40 via-surface to-surface border border-emerald-800/40 rounded-xl p-3.5 shadow-sm flex flex-wrap items-center justify-between gap-3">
	<div class="flex items-center gap-3">
		<div class="w-8 h-8 rounded-lg bg-emerald-600/20 text-emerald-400 border border-emerald-500/30 flex items-center justify-center font-bold text-base">
			📊
		</div>
		<div>
			<div class="flex items-center gap-2">
				<h3 class="text-xs sm:text-sm font-bold text-white tracking-wide">IDX EQUITY & BANDARMOLOGI REPLICATOR</h3>
				<span class="px-2 py-0.2 rounded text-[9px] font-mono font-bold bg-emerald-950 text-emerald-400 border border-emerald-800/60">
					KRAKEN FLOW ATS • NO SELL
				</span>
				<span class="px-2 py-0.2 rounded text-[9px] font-mono font-bold bg-cyan-950 text-cyan-400 border border-cyan-800/60">
					CAP FASE 2: ADVISORY 🛡️
				</span>
			</div>
			<p class="text-[11px] text-muted">
				Analisis broker summary Arjum API, foreign net flow Big Caps, dan deteksi akumulasi tersembunyi saham lapis dua.
			</p>
		</div>
	</div>

	<div class="flex items-center gap-3 text-xs font-mono">
		<div class="text-right">
			<div class="text-[9px] text-muted uppercase">Arjum Quota Guard:</div>
			<div class="text-emerald-400 font-bold">Anti-Freeze Active</div>
		</div>
		<div class="h-6 w-px bg-border"></div>
		<div class="text-right">
			<div class="text-[9px] text-muted uppercase">Test Suite:</div>
			<div class="text-cyan-400 font-bold">39/39 Passed (100%)</div>
		</div>
	</div>
</div>

{#if sub === 'cockpit' || !sub}
	<JudulBagian nomor="1" judul="Cockpit IDX & Foreign Flow Dashboard" tujuan="Overview pasar modal domestik, skor akumulasi bandar, dan status sesi reguler" ikon="◎" />
{:else if sub === 'setup'}
	<JudulBagian nomor="2" judul="Sinyal & Setup Broker Summary" tujuan="Emiten lolos saringan: Sinyal BSJP, ARA Hunter, dan Broker Summary" ikon="◈" />
{:else if sub === 'ukur'}
	<JudulBagian nomor="3" judul="Kuantitatif / Backtest Bandarmologi" tujuan="Uji statistik BSJP, akurasi aturan bandarmologi, dan backtest emiten" ikon="⚖" />
{:else if sub === 'eksekusi'}
	<JudulBagian nomor="4" judul="Eksekusi / Paper Ledger (Rp 10 Jt)" tujuan="Simulasi paper portofolio saham IDX (Rp 10 jt) dan riwayat transaksi" ikon="⇄" />
{/if}
