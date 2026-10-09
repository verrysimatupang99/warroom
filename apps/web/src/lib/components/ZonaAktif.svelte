<script lang="ts">
	/**
	 * ZonaAktif — "Zona & Sinyal Mesin" untuk pasar Forex.
	 *
	 * Bentuk ini DITIRU dari desk XAU Tencent (`/xau/api/activesignals`): daftar zona
	 * (pair · TF · jenis · sisi · rentang harga · pemicu · play) yang sedang dipantau mesin.
	 * DISESUAIKAN ke War Room: angka datang APA ADANYA dari fakta `forex_sinyal.entries` —
	 * tidak ada satu pun nilai yang dihitung atau dikarang di sini.
	 *
	 * Beda dengan Tencent (yang menandai SWING/INTRADAY/SCALPING sebagai "play"): jurnal kita
	 * belum menyimpan nama play, jadi kolom play hanya tampil bila datanya memang ada — kalau
	 * tidak, ditulis apa adanya (bukan ditebak).
	 */
	interface Entri {
		pair?: string | null;
		tf?: string | null;
		jenis?: string | null;
		kind?: string | null;
		arah?: string | null;
		side?: string | null;
		zona?: string | null;
		entry?: number | string | null;
		sl?: number | string | null;
		tp1?: number | string | null;
		tp2?: number | string | null;
		r_r?: number | null;
		konfluensi?: number | null;
		play?: string | null;
		status?: string | null;
		hasil?: string | null;
		waktu?: string | null;
		alasan?: string | null;
	}

	interface Props {
		blok: {
			entries?: Entri[] | null;
			sumber?: string | null;
			tersedia?: boolean | null;
			alasan?: string | null;
		} | null;
		judul?: string;
		/** Batas baris yang ditampilkan; sisanya diberi keterangan. */
		maks?: number;
	}

	let { blok, judul = 'Zona & Sinyal Mesin (Forex)', maks = 8 }: Props = $props();

	function num(v: number | string | null | undefined): number | null {
		if (v === null || v === undefined || v === '') return null;
		const n = Number(v);
		return Number.isFinite(n) ? n : null;
	}

	function fmt(v: number | string | null | undefined, dp = 5): string {
		const n = num(v);
		if (n === null) return '—';
		// Pair FX butuh 5 desimal; indeks/emas cukup 2 — pilih dari besaran angkanya.
		const d = Math.abs(n) >= 100 ? 2 : dp;
		return n.toLocaleString('id-ID', { minimumFractionDigits: d, maximumFractionDigits: d });
	}

	const semua = $derived((blok?.entries ?? []) as Entri[]);

	/** Zona hidup = status ACTIVE / belum ada hasil. Sisanya riwayat. */
	const hidup = $derived(
		semua.filter((e) => {
			const st = String(e.status ?? '').toUpperCase();
			return st === 'ACTIVE' || st === 'OPEN' || (e.hasil === null && st !== 'CLOSED' && st !== 'CANCELLED');
		})
	);
	const riwayat = $derived(semua.filter((e) => !hidup.includes(e)));
	const tampil = $derived(hidup.length ? hidup.slice(0, maks) : riwayat.slice(0, maks));
	const mode = $derived(hidup.length ? 'hidup' : 'riwayat');
</script>

<div class="permukaan-2 rounded-card border border-line p-3">
	<div class="mb-3 flex flex-wrap items-center justify-between gap-2 border-b border-line-soft pb-2">
		<div>
			<h3 class="text-14 font-medium text-text">{judul}</h3>
			<p class="text-11 text-text-3">
				{mode === 'hidup'
					? 'Zona SMC yang sedang dipantau mesin — titik masuk, batas rugi, dan target. Belum posisi.'
					: 'Belum ada zona aktif; ini catatan transaksi mesin terakhir (riwayat).'}
			</p>
		</div>
		<span class="rounded bg-surface px-2 py-0.5 text-11 font-mono border border-line {mode === 'hidup' ? 'text-pos' : 'text-text-3'}">
			{hidup.length} aktif · {riwayat.length} riwayat
		</span>
	</div>

	{#if !blok?.tersedia}
		<div class="py-4 text-center text-12 text-text-3">
			Jurnal forex belum tersedia ({blok?.alasan ?? 'belum diimpor'}).
		</div>
	{:else if !semua.length}
		<div class="py-4 text-center text-12 text-text-3">Tidak ada sinyal di jurnal mesin.</div>
	{:else}
		<div class="overflow-x-auto">
			<table class="w-full text-left text-12 font-mono">
				<thead class="border-b border-line text-10 uppercase text-text-3">
					<tr>
						<th class="py-1.5 px-1.5 sm:px-2.5">Pair</th>
						<th class="py-1.5 px-1.5 sm:px-2.5">TF</th>
						<th class="py-1.5 px-1.5 sm:px-2.5">Zona</th>
						<th class="py-1.5 px-1.5 sm:px-2.5">Arah</th>
						<th class="py-1.5 px-1.5 sm:px-2.5 text-right">Entry</th>
						<th class="py-1.5 px-1.5 sm:px-2.5 text-right">SL</th>
						<th class="py-1.5 px-1.5 sm:px-2.5 text-right">TP1</th>
						<th class="hidden py-1.5 px-1.5 sm:table-cell sm:px-2.5 text-right">R:R</th>
						<th class="py-1.5 px-1.5 sm:px-2.5">Status</th>
					</tr>
				</thead>
				<tbody class="divide-y divide-line-soft">
					{#each tampil as e, i (String(e.pair) + String(e.waktu) + i)}
						{@const naik = (e.arah ?? e.side ?? '').toUpperCase() === 'BUY'}
						<tr class="hover:bg-surface/50">
							<td class="py-1.5 px-1.5 font-bold text-text sm:px-2.5">{e.pair ?? '—'}</td>
							<td class="py-1.5 px-1.5 text-text-3 sm:px-2.5">{e.tf ?? '—'}</td>
							<td class="py-1.5 px-1.5 text-text-2 sm:px-2.5">{e.zona ?? e.jenis ?? e.kind ?? '—'}</td>
							<td class="py-1.5 px-1.5 font-bold sm:px-2.5 {naik ? 'text-pos' : 'text-neg'}">
								{e.arah ?? e.side ?? '—'}
							</td>
							<td class="py-1.5 px-1.5 text-right text-text-2 sm:px-2.5">{fmt(e.entry)}</td>
							<td class="py-1.5 px-1.5 text-right text-neg sm:px-2.5">{fmt(e.sl)}</td>
							<td class="py-1.5 px-1.5 text-right text-pos sm:px-2.5">{fmt(e.tp1)}</td>
							<td class="hidden py-1.5 px-1.5 text-right text-text-3 sm:table-cell sm:px-2.5">
								{e.r_r != null ? `${e.r_r}R` : '—'}
							</td>
							<td class="py-1.5 px-1.5 sm:px-2.5">
								{#if e.hasil}
									<span class="rounded border border-line bg-surface px-1.5 py-0.5 text-10 font-bold text-text-3">{e.hasil}</span>
								{:else if String(e.status ?? '').toUpperCase() === 'ACTIVE'}
									<span class="rounded border border-pos/40 bg-pos/10 px-1.5 py-0.5 text-10 font-bold text-pos">AKTIF</span>
								{:else}
									<span class="rounded border border-line bg-surface px-1.5 py-0.5 text-10 font-bold text-text-3">{e.status ?? '—'}</span>
								{/if}
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>

		{#if (mode === 'hidup' ? hidup.length : riwayat.length) > maks}
			<p class="mt-2 text-10 text-text-3">
				Menampilkan {maks} dari {mode === 'hidup' ? hidup.length : riwayat.length} baris — sisanya di tab Sinyal.
			</p>
		{/if}
		<p class="mt-2 text-10 text-text-3">
			<b>Populasi:</b> baris dari jurnal mesin forex (XAUUSD SMC 4-agen · NAS100/EURUSD FVG-OB 1H);
			titik harga tampil apa adanya, tidak dihitung ulang. Zona hidup = status mesin belum ditutup.
		</p>
		{#if blok?.sumber}
			<p class="mt-1 truncate font-mono text-10 text-text-3">Sumber: {blok.sumber}</p>
		{/if}
	{/if}
</div>
