<script lang="ts">
	import JudulBagian from './JudulBagian.svelte';

	interface Props {
		sub: string;
	}
	let { sub }: Props = $props();
</script>

<div class="mb-4 bg-gradient-to-r from-sky-950/40 via-surface to-surface border border-sky-800/40 rounded-xl p-3.5 shadow-sm flex flex-wrap items-center justify-between gap-3">
	<div class="flex items-center gap-3">
		<div class="w-8 h-8 rounded-lg bg-sky-600/20 text-sky-400 border border-sky-500/30 flex items-center justify-center font-bold text-base">
			🚀
		</div>
		<div>
			<div class="flex items-center gap-2">
				<h3 class="text-xs sm:text-sm font-bold text-white tracking-wide">CRYPTO DERIVATIVES & DEX RADAR</h3>
				<span class="px-2 py-0.2 rounded text-[9px] font-mono font-bold bg-sky-950 text-sky-400 border border-sky-800/60">
					BTC • SOL • SUI
				</span>
				<span class="px-2 py-0.2 rounded text-[9px] font-mono font-bold bg-emerald-950 text-emerald-400 border border-emerald-800/60">
					LIVE VENUE FAIL-CLOSED 🛡️
				</span>
			</div>
			<p class="text-[11px] text-muted">
				Analisis orderbook Binance/OKX futures, kalkulasi funding rate real-time, dan deteksi anomali likuidasi.
			</p>
		</div>
	</div>

	<div class="flex items-center gap-3 text-xs font-mono">
		<div class="text-right">
			<div class="text-[9px] text-muted uppercase">Funding Rate BTC:</div>
			<div class="text-emerald-400 font-bold">+0.0068% / 8h</div>
		</div>
		<div class="h-6 w-px bg-border"></div>
		<div class="text-right">
			<div class="text-[9px] text-muted uppercase">Short Squeeze Alert:</div>
			<div class="text-amber-400 font-bold">SUI (-0.0025%)</div>
		</div>
	</div>
</div>

{#if sub === 'cockpit' || !sub}
	<JudulBagian nomor="1" judul="Ringkasan Likuidasi & Momentum" tujuan="Uang, risiko, dan sinyal teratas — keadaan pasar derivatif hari ini dalam satu pandangan" ikon="◎" />
{:else if sub === 'setup'}
	<JudulBagian nomor="2" judul="Setup Kandidat & Liquidity Sweep" tujuan="Daftar lengkap kandidat + alasan lolos/gagal per aturan (kolom 'skor gate')" ikon="◈" />
{:else if sub === 'ukur'}
	<JudulBagian nomor="3" judul="Ukur (Validasi Model)" tujuan="Apakah aturan gate punya nilai? Lolos vs ditolak, dihitung setelah kejadian" ikon="⚖" />
{:else if sub === 'eksekusi'}
	<JudulBagian nomor="4" judul="Eksekusi & Paper Ledger" tujuan="Yang benar-benar terjadi: posisi terbuka, fill, hasil per trade" ikon="⇄" />
{/if}
