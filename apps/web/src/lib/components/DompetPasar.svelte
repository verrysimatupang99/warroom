<script lang="ts">
	/**
	 * Dompet paper per market — Rp 10.000.000 saldo awal (permintaan owner 7 Okt).
	 *
	 * Kenapa rupiah: R TIDAK bisa dibandingkan antar-market (1R crypto ≠ 1R IDX), tapi
	 * saldo yang sama dengan risiko yang sama bisa. Angka datang apa adanya dari fakta
	 * `dompet` (mesin dompet.py); komponen ini tidak menghitung apa pun.
	 *
	 * Yang wajib terlihat, bukan disembunyikan:
	 * - saldo bisa MINUS (IDX: ARA_HUNTER menghabiskan dompet) — itu temuan, bukan bug tampilan;
	 * - pecahan per setup pada IDX/GBMN — supaya jelas siapa yang menghasilkan;
	 * - biaya yang belum tercatat dinyatakan, bukan dianggap nol.
	 */
	interface TitikDompet {
		i: number;
		label?: string;
		pair?: string;
		status?: string;
		r?: number;
		pnl_usd?: number;
		pnl_idr?: number;
		saldo_usd?: number;
		saldo_idr?: number;
		closed_at?: string;
	}

	interface SetupDompet {
		setup: string;
		n: number;
		mean_r: number | null;
		min_r?: number | null;
		max_r?: number | null;
		risiko_tak_terbatas?: boolean;
		pnl_idr: number;
		saldo_idr: number;
		pnl_pct: number;
	}

	interface DompetMarket {
		market: string;
		tersedia: boolean;
		alasan?: string | null;
		saldo_awal_idr?: number;
		saldo_awal_unit?: number;
		mata_uang?: string;
		kurs_usd_idr?: number | null;
		risk_pct?: number | null;
		saldo_akhir_idr?: number | null;
		saldo_akhir_usd?: number | null;
		pnl_idr?: number | null;
		pnl_usd?: number | null;
		pnl_pct?: number | null;
		trade?: number;
		titik?: TitikDompet[];
		per_setup?: Record<string, SetupDompet>;
		biaya_tercatat?: boolean;
		sumber?: string;
		catatan?: string[];
	}

	interface Props {
		market: 'crypto' | 'idx' | 'forex' | 'gmgn' | 'polymarket';
		dompet?: { pasar?: Record<string, DompetMarket>; kurs_usd_idr?: number | null } | null;
		judul?: string;
		ringkas?: boolean;
	}

	let { market, dompet, judul, ringkas = false }: Props = $props();

	const d = $derived(dompet?.pasar?.[market] ?? null);
	const titik = $derived((d?.titik ?? []).filter((t) => t.i > 0));

	const rupiah = (v: number | null | undefined) =>
		v === null || v === undefined
			? '—'
			: `${v < 0 ? '−' : ''}Rp ${Math.abs(Math.round(v)).toLocaleString('id-ID')}`;

	const dolar = (v: number | null | undefined) =>
		v === null || v === undefined ? '—' : `${v > 0 ? '+' : ''}${v.toFixed(2)} USD`;

	// Kurva mini: posisi (x,y) dari saldo berjalan — SVG, tanpa pustaka.
	const lebar = 260;
	const tinggi = 60;
	const skala = $derived.by(() => {
		const nilai = titik.map((t) => Number(t.saldo_idr ?? t.saldo_usd ?? 0));
		if (nilai.length === 0) return null;
		const bawah = Math.min(...nilai);
		const atas = Math.max(...nilai);
		const rentang = atas - bawah || 1;
		const x = (i: number) => (i / Math.max(1, nilai.length - 1)) * lebar;
		const y = (v: number) => tinggi - ((v - bawah) / rentang) * (tinggi - 6) - 3;
		return { jalur: nilai.map((v, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' '), bawah, atas };
	});
</script>

<div class="permukaan-2 rounded-card border border-line p-3">
	<div class="mb-3 flex flex-wrap items-center justify-between gap-2 border-b border-line-soft pb-2">
		<div>
			<h3 class="text-14 font-medium text-text">{judul ?? 'Dompet Paper'}</h3>
			<p class="text-11 text-text-3">
				Saldo awal Rp 10.000.000 per market · risiko {(d?.risk_pct ?? 1)}% saldo awal per trade · tanpa compounding
			</p>
		</div>
		{#if d?.tersedia}
			<span class="rounded bg-surface border border-line px-2 py-0.5 text-11 font-mono {((d.pnl_pct ?? 0) >= 0) ? 'text-pos' : 'text-neg'}">
				{(d.pnl_pct ?? 0) > 0 ? '+' : ''}{(d.pnl_pct ?? 0).toFixed(2)}%
			</span>
		{/if}
	</div>

	{#if !d?.tersedia}
		<div class="py-4 text-center text-12 text-text-3">
			Dompet belum bisa dihitung ({d?.alasan ?? '—'})
		</div>
	{:else}
		<div class="mb-3 grid grid-cols-2 gap-2 sm:grid-cols-4 font-mono">
			<div class="rounded bg-surface p-2.5 border border-line">
				<div class="text-10 text-text-3">SALDO AWAL</div>
				<div class="text-13 font-bold text-text">{rupiah(d.saldo_awal_idr)}</div>
			</div>
			<div class="rounded bg-surface p-2.5 border border-line">
				<div class="text-10 text-text-3">SALDO KINI</div>
				<!-- Satuannya RUPIAH (dompet Rp 10 juta). Angka venue (USD) ditaruh sebagai
				     konteks, BUKAN sebagai nilai utama — 7 Okt pemilik bingung melihat
				     "+576.45 USD" di kartu yang PnL-nya rupiah. -->
				<div class="text-13 font-bold {(d.pnl_pct ?? 0) >= 0 ? 'text-pos' : 'text-neg'}">
					{rupiah(d.saldo_akhir_idr ?? (d.saldo_akhir_usd ?? 0) * (d.kurs_usd_idr ?? 0))}
				</div>
				{#if d.mata_uang !== 'IDR' && d.saldo_akhir_usd != null}
					<div class="text-10 text-text-3 font-mono">{dolar(d.saldo_akhir_usd)} @ {Math.round(d.kurs_usd_idr ?? 0).toLocaleString('id-ID')}</div>
				{/if}
			</div>
			<div class="rounded bg-surface p-2.5 border border-line">
				<div class="text-10 text-text-3">PnL</div>
				<div class="text-13 font-bold {(d.pnl_pct ?? 0) >= 0 ? 'text-pos' : 'text-neg'}">
					{d.pnl_idr != null ? rupiah(d.pnl_idr) : dolar(d.pnl_usd)}
				</div>
			</div>
			<div class="rounded bg-surface p-2.5 border border-line">
				<div class="text-10 text-text-3">TRADE TUNTAS</div>
				<div class="text-13 font-bold text-text">{d.trade ?? 0}</div>
			</div>
		</div>

		{#if skala && titik.length > 1}
			<div class="mb-3">
				<svg viewBox="0 0 {lebar} {tinggi}" class="w-full h-16" role="img" aria-label="Kurva saldo dompet">
					<path d={skala.jalur} fill="none" class="stroke-accent" stroke-width="1.5" />
				</svg>
				<div class="flex justify-between text-10 text-text-3 font-mono">
					<span>mulai {rupiah(d.saldo_awal_idr)}</span>
					<span>{titik.length} trade tuntas</span>
					<span>kini {rupiah(d.saldo_akhir_idr ?? (d.saldo_akhir_usd ?? 0) * (d.kurs_usd_idr ?? 0))}</span>
				</div>
			</div>
		{/if}

		{#if !ringkas && d.per_setup && Object.keys(d.per_setup).length > 0}
			<div class="mb-3">
				<div class="mb-1.5 text-11 font-bold text-text-2">Per setup — siapa yang menghasilkan, siapa yang menghabiskan</div>
				<div class="overflow-x-auto">
					<table class="w-full text-left text-12 font-mono">
						<thead class="border-b border-line text-text-3 text-10 uppercase">
							<tr>
								<th class="py-1.5 px-1.5">Setup</th>
								<th class="py-1.5 px-1.5 text-right">n</th>
								<th class="py-1.5 px-1.5 text-right">Mean R</th>
								<th class="py-1.5 px-1.5 text-right">Terburuk</th>
								<th class="py-1.5 px-1.5 text-right">PnL</th>
								<th class="py-1.5 px-1.5 text-right">Saldo</th>
							</tr>
						</thead>
						<tbody class="divide-y divide-line-soft">
							{#each Object.values(d.per_setup) as s (s.setup)}
								<tr>
									<td class="py-1.5 px-1.5 font-bold text-text">
										{s.setup}
										{#if s.risiko_tak_terbatas}
											<span class="ml-1 rounded border border-neg/40 bg-neg/10 px-1 py-0.5 text-10 font-bold text-neg" title="Ada trade rugi >3R: stop 1R tidak dihormati (exit di open sesi berikutnya)">⚠ STOP TAK DIHORMATI</span>
										{/if}
									</td>
									<td class="py-1.5 px-1.5 text-right text-text-2">{s.n}</td>
									<td class="py-1.5 px-1.5 text-right {s.mean_r != null && s.mean_r > 0 ? 'text-pos' : 'text-neg'}">
										{s.mean_r != null ? `${s.mean_r > 0 ? '+' : ''}${s.mean_r}` : '—'}
									</td>
									<td class="py-1.5 px-1.5 text-right {s.min_r != null && s.min_r <= -3 ? 'text-neg font-bold' : 'text-text-3'}">
										{s.min_r != null ? `${s.min_r}R` : '—'}
									</td>
									<td class="py-1.5 px-1.5 text-right font-bold {s.pnl_idr >= 0 ? 'text-pos' : 'text-neg'}">{rupiah(s.pnl_idr)}</td>
									<td class="py-1.5 px-1.5 text-right {s.saldo_idr >= d.saldo_awal_idr! ? 'text-text' : 'text-neg'}">{rupiah(s.saldo_idr)}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</div>
		{/if}

		{#if !ringkas}
			{#if d.biaya_tercatat === false}
				<p class="text-11 text-warn">⚠ Biaya (fee/slippage) belum tercatat di ledger market ini — PnL masih bruto.</p>
			{/if}
			{#if d.catatan?.length}
				<ul class="mt-1.5 space-y-0.5">
					{#each d.catatan as c}
						<li class="text-11 text-text-3">· {c}</li>
					{/each}
				</ul>
			{/if}
			{#if d.sumber}
				<p class="mt-1.5 text-10 text-text-3 font-mono truncate">Sumber: {d.sumber}</p>
			{/if}
		{/if}
	{/if}
</div>
