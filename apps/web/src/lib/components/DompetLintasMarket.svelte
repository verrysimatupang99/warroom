<script lang="ts">
	/**
	 * Perbandingan dompet Rp 10 juta lintas market (7 Okt).
	 *
	 * Inilah satu-satunya tempat R/IDR/USD boleh dibandingkan: karena saldo awalnya SAMA
	 * (Rp 10 juta) dan risikonya sama (1% saldo awal), saldo akhir menjadi ukuran yang adil.
	 * Meski begitu kolom satuan tetap dipisah — IDX memakai rupiah, sisanya USD.
	 */
	interface Market {
		market: string;
		tersedia: boolean;
		alasan?: string | null;
		saldo_awal_unit?: number;
		mata_uang?: string;
		saldo_akhir_idr?: number | null;
		saldo_akhir_usd?: number | null;
		pnl_idr?: number | null;
		pnl_usd?: number | null;
		pnl_pct?: number | null;
		trade?: number;
		setup?: string | null;
		per_setup?: Record<string, { setup?: string; n: number; mean_r?: number | null; pnl_idr: number }>;
	}
	interface Props {
		dompet?: { pasar?: Record<string, Market>; kurs_usd_idr?: number | null; saldo_awal_idr?: number } | null;
	}
	let { dompet }: Props = $props();

	const label: Record<string, string> = {
		crypto: 'Crypto (SMC)',
		idx: 'IDX (ARA/BSJP)',
		forex: 'Forex (XAUUSD dll)',
		gmgn: 'GMGN / LP',
		polymarket: 'Polymarket (arm B)'
	};
	const baris = $derived(
		Object.entries(dompet?.pasar ?? {}).map(([k, v]) => ({ kunci: k, ...v }))
	);
	const rp = (v: number | null | undefined) =>
		v === null || v === undefined ? '—' : `${v < 0 ? '−' : ''}Rp ${Math.abs(Math.round(v)).toLocaleString('id-ID')}`;

	/** Setup terbaik & terburuk per market (dari pecahan IDX) — untuk menyaring pelajaran. */
	const ekstrem = $derived.by(() => {
		const idx = dompet?.pasar?.idx?.per_setup;
		if (!idx) return null;
		const daftar = Object.values(idx);
		return {
			terbaik: daftar.reduce((a, b) => (b.pnl_idr > a.pnl_idr ? b : a)),
			terburuk: daftar.reduce((a, b) => (b.pnl_idr < a.pnl_idr ? b : a))
		};
	});
</script>

<div class="permukaan-2 rounded-card border border-line p-3">
	<div class="mb-3 border-b border-line-soft pb-2">
		<h3 class="text-14 font-medium text-text">Dompet Paper Lintas Market — Rp 10.000.000 masing-masing</h3>
		<p class="text-11 text-text-3">
			Satu ukuran untuk semua market. R tidak bisa dibandingkan antar-market; rupiah dengan risiko yang sama bisa.
			{#if dompet?.kurs_usd_idr}Kurs: Rp {Math.round(dompet.kurs_usd_idr).toLocaleString('id-ID')}/USD.{/if}
		</p>
	</div>
	<div class="overflow-x-auto">
		<table class="w-full text-left text-12 font-mono">
			<thead class="border-b border-line text-text-3 text-10 uppercase">
				<tr>
					<th class="py-1.5 px-1.5">Market</th>
					<th class="py-1.5 px-1.5 text-right">Modal Awal</th>
					<th class="py-1.5 px-1.5 text-right">Saldo Kini (IDR)</th>
					<th class="py-1.5 px-1.5 text-right">PnL</th>
					<th class="py-1.5 px-1.5 text-right">%</th>
					<th class="py-1.5 px-1.5 text-right">Trade</th>
				</tr>
			</thead>
			<tbody class="divide-y divide-line-soft">
				{#each baris as b (b.kunci)}
					<tr class="hover:bg-surface/50 transition-colors">
						<td class="py-1.5 px-1.5 font-bold text-text">{label[b.kunci] ?? b.market}</td>
						<td class="py-1.5 px-1.5 text-right text-text-3">{rp(dompet?.saldo_awal_idr ?? b.saldo_awal_unit)}</td>
						<td class="py-1.5 px-1.5 text-right text-text">
							{#if !b.tersedia}—{:else}{rp(b.saldo_akhir_idr ?? (b.saldo_akhir_usd ?? 0) * (dompet?.kurs_usd_idr ?? 0))}{/if}
						</td>
						<td class="py-1.5 px-1.5 text-right font-bold {(b.pnl_pct ?? 0) >= 0 ? 'text-pos' : 'text-neg'}">
							{#if !b.tersedia}—{:else}{rp(b.pnl_idr ?? (b.pnl_usd ?? 0) * (dompet?.kurs_usd_idr ?? 0))}{/if}
						</td>
						<td class="py-1.5 px-1.5 text-right {(b.pnl_pct ?? 0) >= 0 ? 'text-pos' : 'text-neg'}">
							{#if !b.tersedia}—{:else}{(b.pnl_pct ?? 0) > 0 ? '+' : ''}{(b.pnl_pct ?? 0).toFixed(2)}%{/if}
						</td>
						<td class="py-1.5 px-1.5 text-right text-text-2">{b.tersedia ? b.trade ?? 0 : '—'}</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
	{#if ekstrem}
		<div class="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
			<div class="rounded border border-pos/30 bg-pos/5 p-2 text-11">
				<span class="font-bold text-pos">Setup terbaik: {ekstrem.terbaik.setup}</span>
				<span class="text-text-3"> · {ekstrem.terbaik.n} trade · {rp(ekstrem.terbaik.pnl_idr)}</span>
			</div>
			<div class="rounded border border-neg/30 bg-neg/5 p-2 text-11">
				<span class="font-bold text-neg">Setup terburuk: {ekstrem.terburuk.setup}</span>
				<span class="text-text-3"> · {ekstrem.terburuk.n} trade · {rp(ekstrem.terburuk.pnl_idr)}</span>
			</div>
		</div>
	{/if}
	<p class="mt-2 text-10 text-text-3">
		Pelajaran 7 Okt: di IDX, ARA_HUNTER (−139%) menghabiskan dompet sendirian, sementara BSJP_STRONG (+20,5%)
		dan BSJP_ARA (+6,8%) menghasilkan. Pertanyaan yang benar bukan "IDX untung/rugi", tapi "setup mana yang dipakai".
	</p>
</div>
