<script lang="ts">
	import JudulBagian from './JudulBagian.svelte';

	interface Props {
		sub: string;
	}
	let { sub }: Props = $props();
</script>

<div class="mb-4 bg-gradient-to-r from-purple-950/40 via-surface to-surface border border-purple-800/40 rounded-xl p-3.5 shadow-sm flex flex-wrap items-center justify-between gap-3">
	<div class="flex items-center gap-3">
		<div class="w-8 h-8 rounded-lg bg-purple-600/20 text-purple-400 border border-purple-500/30 flex items-center justify-center font-bold text-base">
			🎯
		</div>
		<div>
			<div class="flex items-center gap-2">
				<h3 class="text-xs sm:text-sm font-bold text-white tracking-wide">POLYMARKET CLOB & PREDICTION EDGE</h3>
				<span class="px-2 py-0.2 rounded text-[9px] font-mono font-bold bg-purple-950 text-purple-400 border border-purple-800/60">
					ARM B FAVORITE (0.70 - 0.95)
				</span>
				<span class="px-2 py-0.2 rounded text-[9px] font-mono font-bold bg-emerald-950 text-emerald-400 border border-emerald-800/60">
					EV EDGE +2.07% 🔥
				</span>
			</div>
			<p class="text-[11px] text-muted">
				Eksploitasi mispricing odds biner BTC 5m dan makro-geopolitik pada Polygon orderbook dengan proteksi slippage CTF.
			</p>
		</div>
	</div>

	<div class="flex items-center gap-3 text-xs font-mono">
		<div class="text-right">
			<div class="text-[9px] text-muted uppercase">Sample Size:</div>
			<div class="text-slate-200 font-bold">n = 4,133 (78.25% Win)</div>
		</div>
		<div class="h-6 w-px bg-border"></div>
		<div class="text-right">
			<div class="text-[9px] text-muted uppercase">Pipeline Latency:</div>
			<div class="text-cyan-400 font-bold">~400ms</div>
		</div>
	</div>
</div>

{#if sub === 'cockpit' || !sub}
	<JudulBagian nomor="1" judul="Cockpit Polymarket & Probability Radar" tujuan="Ringkasan pasar binary, Arm B favorit 0.70-0.95, akurasi, dan dompet paper" ikon="◎" />
{:else if sub === 'setup'}
	<JudulBagian nomor="2" judul="Sinyal & Setup Arbitrage" tujuan="Sinyal aktif: Favorit 0,70–0,95 (Arm B) + PolyBTC 5m momentum" ikon="◈" />
{:else if sub === 'ukur'}
	<JudulBagian nomor="3" judul="Kuantitatif & Parity Drift" tujuan="Dataset historis, parity/drift analysis, dan katalog replay pengujian kuantitatif" ikon="⚖" />
{:else if sub === 'eksekusi'}
	<JudulBagian nomor="4" judul="Eksekusi & Virtual Paper Ledger" tujuan="Paper trade ledger, status arming 3-way, dan eksekusi binary CLOB" ikon="⇄" />
{/if}
