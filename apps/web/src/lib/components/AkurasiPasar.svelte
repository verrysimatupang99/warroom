<script lang="ts">
	/**
	 * Tabel akurasi + PnL per setup untuk SATU pasar — bentuk seragam untuk semua market.
	 *
	 * Sumber: fakta snapshot `pasar_akurasi` (mesin `pasar.py`). Semua angka dihitung di
	 * backend memakai pakem bukti yang sama; komponen ini TIDAK menghitung ulang apa pun.
	 * Karena itu seri yang bukan R (LP: P&L USD; Polymarket: entri menang/kalah) tampil
	 * apa adanya dengan MEAN R "—", bukan 0.
	 */
	interface BarisAkurasi {
		nama?: string;
		n?: number | null;
		n_hari?: number | null;
		winrate_pct?: number | null;
		mean_r?: number | null;
		total_r?: number | null;
		total_pnl_usd?: number | null;
		pnl_usd?: number | null;
		menang?: number | null;
		kalah?: number | null;
		tingkat?: string | null;
		ci_winrate?: number[] | null;
		alasan?: string[] | null;
	}

	interface Props {
		judul: string;
		subjudul?: string;
		/** Nama pasar untuk label populasi (opsional). */
		market?: string;
		data?: {
			tersedia?: boolean;
			alasan?: string | null;
			per_setup?: Record<string, BarisAkurasi>;
			sumber?: string | null;
			catatan?: string[] | null;
		} | null;
	}

	let { judul, subjudul, data, market }: Props = $props();

	const baris = $derived(Object.entries(data?.per_setup ?? {}).map(([k, v]) => ({ kunci: k, ...v })));

	function angka(v: number | null | undefined, dp = 4): string {
		if (v === null || v === undefined) return '—';
		return v.toFixed(dp);
	}

	function rupiah(v: number | null | undefined): string {
		if (v === null || v === undefined) return '—';
		return `${v > 0 ? '+' : ''}${v.toFixed(4)}`;
	}

	function kelasPakem(t: string | null | undefined): string {
		if (t === 'TUNING') return 'border-line text-text';
		if (t === 'PRELIMINARY') return 'border-warn/40 text-warn bg-warn/10';
		if (t === 'DIRECTIONAL') return 'border-accent/40 text-accent bg-accent/10';
		return 'border-neg/40 text-neg bg-neg/10';
	}
</script>

<div class="permukaan-2 rounded-card border border-line p-3">
	<div class="mb-3 flex flex-wrap items-center justify-between gap-2 border-b border-line-soft pb-2">
		<div>
			<h3 class="text-14 font-medium text-text">{judul}</h3>
			{#if subjudul}
				<p class="text-11 text-text-3">{subjudul}</p>
			{/if}
		</div>
		<span class="rounded bg-surface px-2 py-0.5 text-11 font-mono text-accent border border-line">
			{baris.length} setup
		</span>
	</div>

	{#if !data?.tersedia}
		<div class="py-4 text-center text-12 text-text-3">
			Akurasi belum tersedia ({data?.alasan ?? '—'})
		</div>
	{:else}
		<div class="overflow-x-auto">
			<table class="w-full text-left text-12 font-mono">
				<thead class="border-b border-line text-text-3 text-10 uppercase">
					<tr>
						<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5">Setup</th>
						<!-- QA 7 Okt: "n" tanpa nama populasi menyesatkan (halaman lain menulis
						     n=16 untuk "semua sinyal dinilai", di sini n=12 untuk "trade TUNTAS").
						     Kolom ini SELALU trade tuntas dari ledger; namanya ditulis utuh. -->
						<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right" title="Jumlah trade TUNTAS (sudah ditutup) di ledger — bukan jumlah sinyal, bukan kandidat aktif">Tuntas<br /><span class="text-9 normal-case">(n)</span></th>
						<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right">Hari</th>
						<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right">Menang%</th>
						<th class="hidden py-1.5 px-1.5 sm:table-cell sm:py-2 sm:px-2.5 text-right">CI90</th>
						<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right">Mean R</th>
						<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right">Total R</th>
						<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right">PnL</th>
						<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5">Pakem</th>
					</tr>
				</thead>
				<tbody class="divide-y divide-line-soft">
					{#each baris as s (s.kunci)}
						<tr class="hover:bg-surface/50 transition-colors">
							<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 font-bold text-text">{s.nama ?? s.kunci}</td>
							<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right text-text-2">{s.n ?? '—'}</td>
							<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right text-text-2">{s.n_hari ?? '—'}</td>
							<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right {s.winrate_pct != null && s.winrate_pct >= 50 ? 'text-pos' : 'text-text-2'}">
								{s.winrate_pct != null ? `${angka(s.winrate_pct, 2)}%` : '—'}
							</td>
							<td class="hidden py-1.5 px-1.5 sm:table-cell sm:py-2 sm:px-2.5 text-right text-text-3">
								{s.ci_winrate && s.n ? `${(s.ci_winrate[0] * 100).toFixed(0)}–${(s.ci_winrate[1] * 100).toFixed(0)}%` : '—'}
							</td>
							<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right {s.mean_r != null && s.mean_r > 0 ? 'text-pos' : s.mean_r != null && s.mean_r < 0 ? 'text-neg' : 'text-text-3'}">
								{s.mean_r != null ? `${s.mean_r > 0 ? '+' : ''}${angka(s.mean_r)}` : '—'}
							</td>
							<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right {s.total_r != null && s.total_r > 0 ? 'text-pos' : s.total_r != null && s.total_r < 0 ? 'text-neg' : 'text-text-3'}">
								{s.total_r != null ? `${s.total_r > 0 ? '+' : ''}${angka(s.total_r)}` : '—'}
							</td>
							<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right text-text-2">
								{rupiah(s.total_pnl_usd ?? s.pnl_usd) === '—' ? '—' : `${rupiah(s.total_pnl_usd ?? s.pnl_usd)} USD`}
							</td>
							<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5">
								<span class="rounded border px-1.5 py-0.5 text-10 font-bold {kelasPakem(s.tingkat)}">{s.tingkat ?? '—'}</span>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
		<p class="mt-2 text-10 text-text-3">
			<b>Populasi:</b> kolom <span class="font-mono">Tuntas (n)</span> = trade yang sudah DITUTUP di ledger
			{market ? `(${market})` : ''} — bukan sinyal yang dinilai, bukan kandidat aktif, bukan posisi berjalan.
			Angka di kartu lain (mis. narasi "n=16") bisa berasal dari populasi BERBEDA: sinyal yang dievaluasi
			versus trade yang tuntas. Bandingkan hanya populasi yang sama.
		</p>


		{#if data?.sumber}
			<p class="mt-2 text-10 text-text-3 font-mono truncate">Sumber: {data.sumber}</p>
		{/if}
		{#if data?.catatan?.length}
			<ul class="mt-2 space-y-0.5">
				{#each data.catatan as c}
					<li class="text-11 text-text-3">· {c}</li>
				{/each}
			</ul>
		{/if}
	{/if}
</div>
