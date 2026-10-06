<script lang="ts">
	/**
	 * Sinyal & Entry Setup per market — satu komponen, kolom menyesuaikan keunikan pasar.
	 *
	 * Sumber: fakta snapshot `crypto_sinyal` / `forex_sinyal` / `idx_sinyal` (mesin `pasar.py`).
	 * Tidak ada perhitungan di sini — semua angka datang dari backend apa adanya.
	 *
	 * Keunikan yang HARUS tampak:
	 * - crypto : skor gate (aturan lolos), tier, POI SMC, daftar aturan gagal.
	 * - forex  : zona FVG/OB + time-frame + konfluensi (khas SMC zone entry).
	 * - idx    : setup (ARA/BSJP/INTRADAY) + hasil R (khas ledger 616).
	 */
	interface Entry {
		pair?: string;
		ticker?: string;
		setup?: string;
		arah?: string;
		tier?: string;
		status?: string;
		skor?: number | null;
		ok?: number;
		total_aturan?: number;
		aturan_gagal?: string[];
		entry?: unknown;
		sl?: number | null;
		tp1?: number | null;
		tp2?: number | null;
		r_r?: number | null;
		risk_pct?: number | null;
		poi?: (number | null)[];
		zona?: string | null;
		tf?: string | null;
		konfluensi?: number | null;
		hasil?: string | null;
		r?: number | null;
		net_r?: number | null;
		waktu?: string | null;
		dibuat?: string | null;
		alasan?: string | null;
		note?: string | null;
	}

	interface Strategi {
		nama: string;
		status: string;
		sumber: string;
	}

	interface Props {
		pasar: 'crypto' | 'forex' | 'idx';
		judul: string;
		subjudul?: string;
		data?: {
			tersedia?: boolean;
			alasan?: string | null;
			entries?: Entry[];
			strategi?: Strategi[];
			sumber?: string | null;
			suplai?: { mesin?: string; catatan?: string } | string | null;
			catatan?: string[] | null;
			dimensi?: { dimensi: string; lolos: number; total: number; persen: number | null }[];
			aktif?: Entry[];
		} | null;
	}

	let { pasar, judul, subjudul, data }: Props = $props();

	const entries = $derived((data?.entries ?? []) as Entry[]);

	function fmt(v: unknown, dp = 4): string {
		if (v === null || v === undefined || v === '') return '—';
		const n = typeof v === 'number' ? v : Number(v);
		if (Number.isNaN(n)) return String(v);
		return n.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: dp });
	}

	function kelasStatus(s: string | null | undefined): string {
		const t = String(s ?? '').toLowerCase();
		if (t.includes('lolos') || t.includes('closed_tp') || t.includes('win')) return 'text-pos bg-pos/10 border-pos/20';
		if (t.includes('ditolak') || t.includes('closed_sl') || t.includes('loss') || t.includes('sl')) return 'text-neg bg-neg/10 border-neg/20';
		if (t.includes('jalan') || t.includes('open') || t.includes('active')) return 'text-accent bg-accent/10 border-accent/20';
		return 'text-text-2 bg-surface border-line';
	}

	function kelasStatusStrategi(s: string): string {
		if (s === 'aktif') return 'text-pos bg-pos/10 border-pos/20';
		if (s === 'paper') return 'text-accent bg-accent/10 border-accent/20';
		return 'text-text-3 bg-canvas border-line';
	}
</script>

<div class="space-y-4">
	<!-- Registry strategi: apa yang dipertaruhkan market ini, jujur statusnya -->
	{#if data?.strategi?.length}
		<div class="permukaan-2 rounded-card border border-line p-3">
			<div class="mb-2 flex items-center justify-between border-b border-line-soft pb-2">
				<div>
					<h3 class="text-14 font-medium text-text">Strategi {pasar.toUpperCase()}</h3>
					<p class="text-11 text-text-3">Yang benar-benar dipakai vs yang masih rencana — dibedakan, tidak disamarkan</p>
				</div>
			</div>
			<ul class="space-y-1.5">
				{#each data.strategi as st}
					<li class="flex flex-wrap items-center gap-2 text-12">
						<span class="rounded px-1.5 py-0.5 text-10 font-bold uppercase border {kelasStatusStrategi(st.status)}">{st.status}</span>
						<span class="font-medium text-text">{st.nama}</span>
						<span class="text-11 text-text-3 font-mono truncate">— {st.sumber}</span>
					</li>
				{/each}
			</ul>
		</div>
	{/if}

	<!-- Tabel sinyal + entry setup -->
	<div class="permukaan-2 rounded-card border border-line p-3">
		<div class="mb-3 flex flex-wrap items-center justify-between gap-2 border-b border-line-soft pb-2">
			<div>
				<h3 class="text-14 font-medium text-text">{judul}</h3>
				{#if subjudul}
					<p class="text-11 text-text-3">{subjudul}</p>
				{/if}
			</div>
			<span class="rounded bg-surface px-2 py-0.5 text-11 font-mono text-accent border border-line">
				{entries.length} baris
			</span>
		</div>

		{#if !data?.tersedia}
			<div class="py-4 text-center text-12 text-text-3">
				Belum ada data sinyal ({data?.alasan ?? '—'})
			</div>
		{:else if entries.length === 0}
			<div class="py-4 text-center text-12 text-text-3">Tidak ada sinyal pada jendela terakhir.</div>
		{:else}
			<div class="overflow-x-auto">
				<table class="w-full text-left text-12 font-mono">
					<thead class="border-b border-line text-text-3 text-10 uppercase">
						<tr>
							{#if pasar === 'crypto'}
								<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5">Pair</th>
								<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5">Arah</th>
								<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right">Skor Gate</th>
								<th class="hidden py-1.5 px-1.5 sm:table-cell sm:py-2 sm:px-2.5">Tier</th>
								<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right">Entry</th>
								<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right">SL</th>
								<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right">TP1</th>
								<th class="hidden py-1.5 px-1.5 md:table-cell md:py-2 md:px-2.5 text-right">R:R</th>
								<th class="hidden py-1.5 px-1.5 md:table-cell md:py-2 md:px-2.5 text-right">POI (SMC)</th>
								<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5">Status</th>
							{:else if pasar === 'forex'}
								<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5">Pair</th>
								<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5">Arah</th>
								<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right">Entry</th>
								<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right">SL</th>
								<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right">TP1</th>
								<th class="hidden py-1.5 px-1.5 md:table-cell md:py-2 md:px-2.5 text-right">R:R</th>
								<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5">Zona (TF)</th>
								<th class="hidden py-1.5 px-1.5 sm:table-cell sm:py-2 sm:px-2.5 text-right">Konfl.</th>
								<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5">Hasil</th>
								<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right">R</th>
							{:else}
								<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5">Ticker</th>
								<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5">Setup</th>
								<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5">Arah</th>
								<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right">Entry</th>
								<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right">SL</th>
								<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right">TP1</th>
								<th class="hidden py-1.5 px-1.5 md:table-cell md:py-2 md:px-2.5 text-right">R:R</th>
								<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right">Net R</th>
								<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5">Status</th>
								<th class="hidden py-1.5 px-1.5 lg:table-cell lg:py-2 lg:px-2.5">Catatan</th>
							{/if}
						</tr>
					</thead>
					<tbody class="divide-y divide-line-soft">
						{#each entries as e, i (i)}
							<tr class="hover:bg-surface/50 transition-colors align-top">
								{#if pasar === 'crypto'}
									<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 font-bold text-text">{e.pair ?? '—'}</td>
									<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5">
										<span class="rounded px-1.5 py-0.5 text-10 font-bold border {String(e.arah).toUpperCase() === 'LONG' ? 'text-pos bg-pos/10 border-pos/20' : 'text-neg bg-neg/10 border-neg/20'}">{e.arah ?? '—'}</span>
									</td>
									<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right font-bold {e.skor != null && e.skor >= 100 ? 'text-pos' : 'text-text-2'}">
										{e.skor != null ? `${e.skor}%` : '—'}
										<div class="text-10 text-text-3 font-normal">{e.ok ?? '—'}/{e.total_aturan ?? '—'} aturan</div>
									</td>
									<td class="hidden py-1.5 px-1.5 sm:table-cell sm:py-2 sm:px-2.5 text-text-2">{e.tier ?? '—'}</td>
									<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right text-text">{fmt(e.entry, 6)}</td>
									<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right text-neg">{fmt(e.sl, 6)}</td>
									<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right text-pos">{fmt(e.tp1, 6)}</td>
									<td class="hidden py-1.5 px-1.5 md:table-cell md:py-2 md:px-2.5 text-right text-accent">{e.r_r != null ? `${e.r_r}R` : '—'}</td>
									<td class="hidden py-1.5 px-1.5 md:table-cell md:py-2 md:px-2.5 text-right text-text-3">
										{e.poi && e.poi[0] != null ? `${fmt(e.poi[0], 6)}–${fmt(e.poi[1], 6)}` : '—'}
									</td>
									<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5">
										<span class="rounded px-1.5 py-0.5 text-10 font-bold uppercase border {kelasStatus(e.status)}">{e.status ?? '—'}</span>
										{#if e.aturan_gagal?.length}
											<div class="text-10 text-text-3 font-normal mt-0.5">gagal: {e.aturan_gagal.slice(0, 2).join(', ')}</div>
										{/if}
									</td>
								{:else if pasar === 'forex'}
									<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 font-bold text-text">{e.pair ?? '—'}</td>
									<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5">
										<span class="rounded px-1.5 py-0.5 text-10 font-bold border {String(e.arah).toUpperCase() === 'BUY' || String(e.arah).toUpperCase() === 'LONG' ? 'text-pos bg-pos/10 border-pos/20' : 'text-neg bg-neg/10 border-neg/20'}">{e.arah ?? '—'}</span>
									</td>
									<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right text-text">{fmt(e.entry, 5)}</td>
									<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right text-neg">{fmt(e.sl, 5)}</td>
									<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right text-pos">{fmt(e.tp1, 5)}</td>
									<td class="hidden py-1.5 px-1.5 md:table-cell md:py-2 md:px-2.5 text-right text-accent">{e.r_r != null ? `${e.r_r}R` : '—'}</td>
									<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-text-2">
										{e.zona ?? '—'}
										{#if e.tf}<span class="text-10 text-text-3"> · {e.tf}</span>{/if}
									</td>
									<td class="hidden py-1.5 px-1.5 sm:table-cell sm:py-2 sm:px-2.5 text-right text-text-3">{e.konfluensi ?? '—'}</td>
									<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5">
										<span class="rounded px-1.5 py-0.5 text-10 font-bold uppercase border {kelasStatus(e.hasil)}">{e.hasil ?? e.status ?? '—'}</span>
									</td>
									<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right {e.r == null ? 'text-text-3' : e.r > 0 ? 'text-pos' : e.r < 0 ? 'text-neg' : 'text-text-2'}">
										{e.r != null ? `${e.r > 0 ? '+' : ''}${e.r}R` : '—'}
									</td>
								{:else}
									<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 font-bold text-text">{e.ticker ?? '—'}</td>
									<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5">
										<span class="rounded bg-surface px-1.5 py-0.5 text-10 font-bold text-accent border border-line">{e.setup ?? '—'}</span>
									</td>
									<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-text-2">{e.arah ?? '—'}</td>
									<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right text-text">{fmt(e.entry, 2)}</td>
									<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right text-neg">{fmt(e.sl, 2)}</td>
									<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right text-pos">{fmt(e.tp1, 2)}</td>
									<td class="hidden py-1.5 px-1.5 md:table-cell md:py-2 md:px-2.5 text-right text-accent">{e.r_r != null ? `${e.r_r}R` : '—'}</td>
									<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right font-bold {e.net_r == null ? 'text-text-3' : e.net_r > 0 ? 'text-pos' : e.net_r < 0 ? 'text-neg' : 'text-text-2'}">
										{e.net_r != null ? `${e.net_r > 0 ? '+' : ''}${e.net_r}R` : '—'}
									</td>
									<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5">
										<span class="rounded px-1.5 py-0.5 text-10 font-bold uppercase border {kelasStatus(e.hasil ?? e.status)}">{e.hasil ?? e.status ?? '—'}</span>
									</td>
									<td class="hidden py-1.5 px-1.5 lg:table-cell lg:py-2 lg:px-2.5 text-11 text-text-3 max-w-[320px]">{e.note ?? '—'}</td>
								{/if}
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}

		{#if data?.sumber}
			<p class="mt-2 text-10 text-text-3 font-mono truncate">Sumber: {data.sumber}</p>
		{/if}
		{#if data?.suplai}
			<p class="mt-1 text-10 text-text-3 font-mono truncate">
				Mesin: {typeof data.suplai === 'string' ? data.suplai : data.suplai?.mesin ?? '—'}
				{#if typeof data.suplai !== 'string' && data.suplai?.catatan} · {data.suplai.catatan}{/if}
			</p>
		{/if}
		{#if data?.catatan?.length}
			<ul class="mt-2 space-y-0.5">
				{#each data.catatan as c}
					<li class="text-11 text-text-3">· {c}</li>
				{/each}
			</ul>
		{/if}
	</div>

	<!-- Dimensi aturan (khas crypto: gate mana yang paling sering menggagalkan) -->
	{#if data?.dimensi?.length}
		<div class="permukaan-2 rounded-card border border-line p-3">
			<div class="mb-2 border-b border-line-soft pb-2">
				<h3 class="text-14 font-medium text-text">Dimensi Gerbang (aturan lolos)</h3>
				<p class="text-11 text-text-3">Diurut dari yang paling sering menggagalkan setup — ini yang harus diperbaiki, bukan ditambal</p>
			</div>
			<div class="space-y-1.5">
				{#each data.dimensi as d}
					<div class="flex items-center gap-2 text-12">
						<span class="w-56 shrink-0 truncate text-text-2">{d.dimensi}</span>
						<div class="h-2 flex-1 overflow-hidden rounded bg-canvas border border-line">
							<div class="h-full rounded bg-accent" style="width: {d.persen ?? 0}%"></div>
						</div>
						<span class="w-16 shrink-0 text-right font-mono text-text-3">{d.persen ?? '—'}% <span class="text-10">({d.lolos}/{d.total})</span></span>
					</div>
				{/each}
			</div>
		</div>
	{/if}
</div>
