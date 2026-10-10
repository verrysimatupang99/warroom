<script lang="ts">
	/**
	 * CockpitCrypto — ringkasan pipeline/sinyal/risiko crypto.
	 *
	 * Bentuk ini DITIRU dari desk Crypto Tencent (`/crypto/api/summary|risk|agent6`):
	 * status mesin, dimensi gerbang, sinyal aktif, dan ruang risiko. DISESUAIKAN ke War Room:
	 * angka datang apa adanya dari fakta (`crypto_sinyal`, `risiko`) — tidak dihitung ulang.
	 *
	 * SENGAJA TANPA panel OKX (saldo/posisi bursa): itu butuh kredensial yang atas arahan
	 * owner TIDAK diambil dari Tencent. Yang tampil hanya angka yang sudah ada di War Room.
	 */
	interface Entri {
		pair?: string | null;
		skor?: number | null;
		tier?: string | null;
		arah?: string | null;
		entry?: number | null;
		sl?: number | null;
		tp1?: number | null;
		poi?: number[] | null;
		r_r?: number | null;
		waktu?: string | null;
	}
	interface Dimensi {
		dimensi?: string | null;
		lolos?: number | null;
		total?: number | null;
		persen?: number | null;
	}

	interface Props {
		sinyal: {
			tersedia?: boolean | null;
			alasan?: string | null;
			aktif?: Entri[] | null;
			dimensi?: Dimensi[] | null;
			entries?: Entri[] | null;
			jumlah_lolos?: number | null;
			jumlah_verdict?: number | null;
			sumber?: string | null;
			suplai?: { mesin?: string | null; catatan?: string | null } | null;
			strategi?: Record<string, unknown>[] | null;
		} | null;
		risiko: {
			mode?: string | null;
			venue?: string | null;
			equity_usd?: number | null;
			hari_ini_r?: number | null;
			batas_rugi_r?: number | null;
			sisa_ruang_r?: number | null;
			posisi_terbuka?: number | null;
			maks_posisi?: number | null;
			total_trade?: number | null;
		} | null;
	}

	let { sinyal, risiko }: Props = $props();

	function angka(v: number | null | undefined, dp = 4): string {
		if (v === null || v === undefined) return '—';
		return v.toFixed(dp);
	}
</script>

<div class="permukaan-2 rounded-card border border-line p-3">
	<div class="mb-3 flex flex-wrap items-center justify-between gap-2 border-b border-line-soft pb-2">
		<div>
			<h3 class="text-14 font-medium text-text">Ringkasan Crypto — Uang, Risiko, Sinyal</h3>
			<p class="text-11 text-text-3">
				Keadaan hari ini dalam satu pandangan. Angka dari fakta
				<span class="font-mono">crypto_sinyal</span> + <span class="font-mono">risiko</span> — bukan angka bursa.
			</p>
		</div>
		<span class="rounded bg-surface px-2 py-0.5 text-11 font-mono border border-line text-accent">
			{risiko?.mode ?? '—'} · {risiko?.venue ?? '—'}
		</span>
	</div>

	<!-- Deret KPI besar (tiru kartu ringkasan Tencent: label kecil → angka besar → catatan).
	     Pembaruan 10 Okt: pertanyaan pembaca "kok bisa rugi?" dijawab lebih dulu di sini. -->
	<div class="mb-3 grid grid-cols-2 gap-2 font-mono sm:grid-cols-4">
		<div class="rounded bg-surface border border-line p-2.5">
			<div class="text-10 uppercase tracking-wide text-text-3">Modal paper</div>
			<div class="mt-0.5 text-20 font-bold text-text">${angka(risiko?.equity_usd, 2)}</div>
			<div class="text-10 text-text-3">saldo kertas, bukan uang nyata</div>
		</div>
		<div class="rounded bg-surface border border-line p-2.5">
			<div class="text-10 uppercase tracking-wide text-text-3">Hasil hari ini</div>
			<div class="mt-0.5 text-20 font-bold { (risiko?.hari_ini_r ?? 0) > 0 ? 'text-pos' : (risiko?.hari_ini_r ?? 0) < 0 ? 'text-neg' : 'text-text-3'}">
				{(risiko?.hari_ini_r ?? 0) > 0 ? '+' : ''}{angka(risiko?.hari_ini_r, 2)}R
			</div>
			<div class="text-10 text-text-3">{risiko?.total_trade ?? 0} trade tuntas</div>
		</div>
		<div class="rounded bg-surface border border-line p-2.5">
			<div class="text-10 uppercase tracking-wide text-text-3">Ruang risiko sisa</div>
			<div class="mt-0.5 text-20 font-bold text-text-2">{angka(risiko?.sisa_ruang_r, 2)}R</div>
			<div class="text-10 text-text-3">dari batas {angka(risiko?.batas_rugi_r, 2)}R</div>
		</div>
		<div class="rounded bg-surface border border-line p-2.5">
			<div class="text-10 uppercase tracking-wide text-text-3">Posisi terbuka</div>
			<div class="mt-0.5 text-20 font-bold text-text">{risiko?.posisi_terbuka ?? 0}<span class="text-13 text-text-3">/{risiko?.maks_posisi ?? '—'}</span></div>
			<div class="text-10 text-text-3">batas {risiko?.maks_posisi ?? '—'} posisi</div>
		</div>
	</div>

	{#if !sinyal?.tersedia}
		<div class="py-4 text-center text-12 text-text-3">
			Sinyal crypto belum tersedia ({sinyal?.alasan ?? 'ledger belum diimpor'}).
		</div>
	{:else}
		<!-- Dimensi gerbang: berapa kandidat lolos tiap syarat (tiru 'gate checks') -->
		{#if sinyal.dimensi?.length}
			<div class="mb-3">
				<div class="label-mikro mb-1.5 text-text-3">Dimensi gerbang (berapa kandidat lolos tiap syarat)</div>
				<div class="space-y-1">
					{#each sinyal.dimensi as d (d.dimensi)}
						<div class="flex items-center gap-2 text-11">
							<span class="w-40 shrink-0 text-text-2">{d.dimensi ?? '—'}</span>
							<div class="h-1.5 flex-1 overflow-hidden rounded-control bg-surface-3">
								<div class="h-full { (d.persen ?? 0) >= 50 ? 'bg-pos' : 'bg-accent' }" style={`width:${Math.min(100, d.persen ?? 0)}%`}></div>
							</div>
							<span class="angka w-20 shrink-0 text-right text-text-3">{d.lolos ?? 0}/{d.total ?? 0} · {d.persen ?? 0}%</span>
						</div>
					{/each}
				</div>
			</div>
		{/if}

		<!-- Sinyal aktif (mesin belum tutup) -->
		<div class="mb-1.5 flex items-center justify-between">
			<span class="label-mikro text-text-3">Sinyal aktif ({sinyal.aktif?.length ?? 0})</span>
			<span class="angka text-11 text-text-3">{sinyal.jumlah_lolos ?? 0} lolos · {sinyal.jumlah_verdict ?? 0} dinilai</span>
		</div>
		{#if sinyal.aktif?.length}
			<div class="overflow-x-auto">
				<table class="w-full text-left text-12 font-mono">
					<thead class="border-b border-line text-10 uppercase text-text-3">
						<tr>
							<th class="py-1.5 px-1.5 sm:px-2">Pair</th>
							<th class="py-1.5 px-1.5 sm:px-2">Arah</th>
							<th class="py-1.5 px-1.5 sm:px-2 text-right">Entry</th>
							<th class="py-1.5 px-1.5 sm:px-2 text-right">SL</th>
							<th class="py-1.5 px-1.5 sm:px-2 text-right">TP1</th>
							<th class="py-1.5 px-1.5 sm:px-2 text-right">R:R</th>
							<th class="py-1.5 px-1.5 sm:px-2 text-right">r</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-line-soft">
						{#each sinyal.aktif as e, i (String(e.pair) + i)}
							{@const naik = (e.arah ?? '').toUpperCase() === 'LONG'}
							<tr class="hover:bg-surface/50">
								<td class="py-1.5 px-1.5 font-bold text-text sm:px-2">{e.pair ?? '—'}</td>
								<td class="py-1.5 px-1.5 font-bold {naik ? 'text-pos' : 'text-neg'} sm:px-2">{e.arah ?? '—'}</td>
								<td class="py-1.5 px-1.5 text-right text-text-2 sm:px-2">{angka(e.entry, 5)}</td>
								<td class="py-1.5 px-1.5 text-right text-neg sm:px-2">{angka(e.sl, 5)}</td>
								<td class="py-1.5 px-1.5 text-right text-pos sm:px-2">{angka(e.tp1, 5)}</td>
								<td class="py-1.5 px-1.5 text-right text-text-3 sm:px-2">{e.r_r != null ? `${e.r_r}R` : '—'}</td>
								<td class="py-1.5 px-1.5 text-right { (e as any).r != null && (e as any).r < 0 ? 'text-neg' : 'text-text-3'} sm:px-2">{(e as any).r != null ? angka((e as any).r, 2) : '—'}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{:else}
			<p class="py-2 text-12 text-text-3">Tidak ada sinyal aktif di ledger.</p>
		{/if}

		<p class="mt-2 text-10 text-text-3">
			<b>Populasi:</b> sinyal aktif = baris mesin yang belum ditutup. Kolom <span class="font-mono">r</span> =
			hasil berjalan (bisa minus sebelum ditutup). Panel bursa (saldo/posisi OKX) sengaja tidak ada —
			butuh kredensial yang tidak diambil dari Tencent.
		</p>
		{#if sinyal.suplai?.mesin}
			<p class="mt-1 text-10 text-text-3">Mesin: <span class="font-mono">{sinyal.suplai.mesin}</span></p>
		{/if}
	{/if}
</div>
