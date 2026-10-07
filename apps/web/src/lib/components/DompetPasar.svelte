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
		/** Berapa trade di setup ini yang rugi melebihi 1R (breach/gap). */
		lewat_1r?: number;
		lewat_1r_pct?: number;
		rugi_ekstrem_5r?: number;
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
		mark_baris?: number | null;
		titik?: TitikDompet[];
		per_setup?: Record<string, SetupDompet>;
		biaya_tercatat?: boolean;
		sumber?: string;
		catatan?: string[];
		/** Invariant risiko (temuan QA 7 Okt): berapa trade tuntas yang rugi > 1R,
		 *  diklasifikasi gap/dalam/ekstrem, plus trade terburuk. */
		invariant?: {
			pelanggaran_1r: number;
			kelas_loss: { wajar: number; gap: number; dalam: number; ekstrem: number };
			terburuk?: { signal_id?: string; pair?: string; setup?: string; r: number; result?: string; closed_at?: string } | null;
			model_breach: boolean;
			penjelasan: string;
		} | null;
		/** Sinyal CREATED yang tak pernah tuntas (mesin beku) — BUKAN posisi berjalan. */
		sinyal_yatim?: { jumlah: number; tertua: string | null } | null;
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
	// Saldo NEGATIF bukan angka biasa: ia konsekuensi langsung dari trade yang rugi
	// melebihi 1R (temuan QA putaran 2). Kalau disajikan telanjang, pembaca bisa
	// menyangka "batas rugi 1% per trade" masih berlaku — padahal tidak.
	const saldoNegatif = $derived(
		(d?.saldo_akhir_idr ?? null) != null && Number(d?.saldo_akhir_idr) < 0
	);
	const saldoUsdNegatif = $derived(
		(d?.saldo_akhir_usd ?? null) != null && Number(d?.saldo_akhir_usd) < 0
	);
	const saldoMinus = $derived(saldoNegatif || saldoUsdNegatif);

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
		{#if saldoMinus}
			<!-- Temuan QA putaran 2: "saldo negatif tetap berbahaya bila disalahartikan
			     sebagai batas rugi". Peringatan ini duduk TEPAT di atas angka saldo, bukan
			     di catatan kaki — supaya tidak mungkin terbaca tanpa konteksnya. -->
			<div class="mb-2 rounded-card border border-neg/60 bg-neg/10 p-2.5" role="alert">
				<div class="flex flex-wrap items-center gap-2">
					<span class="rounded border border-neg/60 bg-neg/20 px-1.5 py-0.5 text-10 font-bold text-neg">SALDO NEGATIF</span>
					<span class="text-11 text-text-2">
						Dompet paper ini <b>habis melewati nol</b> — akibat langsung dari trade yang rugi
						melebihi 1R (lihat MODEL BREACH). Dengan uang nyata, posisi seperti ini sudah
						<b>tidak bisa dibuka lagi</b>: tidak ada sisa modal untuk mempertaruhkan 1% berikutnya.
					</span>
				</div>
			</div>
		{/if}

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
					{#if saldoMinus}
						<div class="text-10 font-normal text-neg">modal habis — bukan sekadar rugi</div>
					{/if}
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
				<div class="text-10 text-text-3">{d.mark_baris ? 'POSISI LP' : 'TRADE TUNTAS'}</div>
				<div class="text-13 font-bold text-text">{d.trade ?? 0}</div>
				{#if d.mark_baris}
					<div class="text-10 text-text-3">{d.mark_baris} baris mark (dinilai berkala)</div>
				{/if}
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
								<th class="py-1.5 px-1.5 text-right" title="Jumlah trade rugi melebihi 1R (breach/gap) di setup ini">Breach</th>
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
									<td class="py-1.5 px-1.5 text-right {s.lewat_1r ? 'text-neg font-bold' : 'text-text-3'}"
										title={s.rugi_ekstrem_5r ? `termasuk ${s.rugi_ekstrem_5r} trade rugi >5R` : ''}>
										{s.lewat_1r ? `${s.lewat_1r}/${s.n} (${s.lewat_1r_pct}%)` : '0'}
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

		<!-- MODEL BREACH (temuan QA eksternal 7 Okt, P0). Banner ini menjawab langsung:
		     "satu trade tidak boleh menghasilkan R < −1R kecuali diberi status khusus".
		     Kenyataannya BISA (gap di open sesi berikutnya), dan itu bukan alasan untuk
		     menyembunyikan angka — melainkan alasan untuk MENANDAI. Tampil juga di mode
		     ringkas: ini peringatan risiko, bukan detail. -->
		{#if d.invariant?.model_breach}
			<div class="mt-2 rounded-card border border-neg/50 bg-neg/10 p-2.5" role="alert">
				<div class="flex flex-wrap items-center gap-2">
					<span class="rounded border border-neg/50 bg-neg/20 px-1.5 py-0.5 text-10 font-bold text-neg">⚠ MODEL BREACH</span>
					<span class="text-11 text-text-2">
						<b>{d.invariant.pelanggaran_1r}</b> dari <b>{d.trade ?? '—'}</b> trade tuntas rugi <b>melebihi 1R</b>
						{#if d.invariant.terburuk}
							· terburuk <span class="font-mono text-neg">{d.invariant.terburuk.r}R</span>
							<span class="font-mono text-text-3">({d.invariant.terburuk.pair ?? '—'} · {d.invariant.terburuk.setup ?? '—'})</span>
						{/if}
					</span>
				</div>
				<div class="mt-1.5 flex flex-wrap gap-2 text-10 font-mono text-text-3">
					<span>≤1R: {d.invariant.kelas_loss.wajar}</span>
					<span>gap 1–2R: {d.invariant.kelas_loss.gap}</span>
					<span>dalam 2–5R: {d.invariant.kelas_loss.dalam}</span>
					<span class="text-neg">ekstrem &gt;5R: {d.invariant.kelas_loss.ekstrem}</span>
				</div>
				<p class="mt-1.5 text-11 text-text-2">{d.invariant.penjelasan}</p>
				<p class="mt-1 text-10 text-text-3">
					Penyebab: posisi ditahan sampai <b>open sesi berikutnya</b> (BSJP/ARA_HUNTER), sehingga gap
					pembukaan bisa jauh melewati stop yang direncanakan. Kalau setup ini dipakai dengan uang
					nyata, "rugi maksimal 1R" <b>tidak berlaku</b> — ukuran posisi wajib diperkecil atau setup
					diperlakukan sebagai berisiko tak terbatas.
				</p>
			</div>
		{/if}

		<!-- Sinyal yatim: CREATED yang tak pernah tuntas karena mesin dibekukan.
		     Menyebutnya "posisi berjalan" adalah kesalahan yang dilaporkan QA. -->
		{#if (d.sinyal_yatim?.jumlah ?? 0) > 0}
			<p class="mt-1.5 text-11 text-text-3">
				⏳ <b>{d.sinyal_yatim?.jumlah}</b> sinyal berstatus <span class="font-mono">CREATED</span> tidak pernah tuntas
				(tertua {d.sinyal_yatim?.tertua?.slice(0, 10) ?? '—'}) — mesin dibekukan, jadi ini <b>bukan</b> posisi berjalan.
			</p>
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
