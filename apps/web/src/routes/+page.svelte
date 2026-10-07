<script lang="ts">
	// PRATINJAU arah baru (6 Okt 2026) — "Algentis gelap".
	//
	// Arah: algentis.xyz, tapi gelap (permintaan pemilik). Satu aksen MINT (#34E39A)
	// + merah + kuning. Font dipertahankan (Space Grotesk/Inter/JetBrains Mono).
	//
	// Tujuan 3 detik: "ada peluang atau tidak". Karena itu urutannya:
	//   1. Ticker pasar (denyut seluruh pasar, satu baris)
	//   2. SATU verdikt besar + alasan
	//   3. Baru rincian per pasar
	//
	// Ini halaman pratinjau: data nyata dari API, tidak ada yang dikarang.
	import { getArea, getPasarRingkas, getSinyalPerPasar, getSumber } from '$lib/api/client';
	import type { AreaPayload, PasarRingkasPayload, SinyalPasar, SinyalPayload } from '$lib/api/types';
	import { umurDetik, waktuWIB } from '$lib/format';

	let sinyal = $state<SinyalPayload | null>(null);
	let kripto = $state<AreaPayload | null>(null);
	let akurasi = $state<PasarRingkasPayload | null>(null);
	let galat = $state<string | null>(null);
	// Sumber data tiap pasar (revisi pemilik 7 Okt): satu tempat, tidak perlu ditebak.
	let sumber = $state<{ pasar: string; label: string; sumber: string; keterangan: string }[]>([]);

	async function muat() {
		const [s, k, a, sm] = await Promise.allSettled([
			getSinyalPerPasar(),
			getArea('crypto'),
			getPasarRingkas(),
			getSumber()
		]);
		if (sm.status === 'fulfilled') sumber = sm.value.sumber;
		if (s.status === 'fulfilled') { sinyal = s.value; galat = null; }
		else galat = s.reason instanceof Error ? s.reason.message : String(s.reason);
		if (k.status === 'fulfilled') kripto = k.value;
		if (a.status === 'fulfilled') akurasi = a.value;
	}
	$effect(() => {
		void muat();
		const t = setInterval(() => void muat(), 15000);
		return () => clearInterval(t);
	});

	const daftar = $derived(sinyal?.sinyal ?? []);
	// Sinyal PER MARKET (revisi pemilik 7 Okt): maks 3 terbaik per pasar + tautan
	// "lihat semua" ke halaman pasar. Status dipisah tegas supaya "tidak ada sinyal"
	// (mesin hidup, tak ada setup cocok) TIDAK pernah tertukar dengan "sistem gagal".
	const pasarDaftar = $derived(sinyal?.pasar ?? []);
	const MAKS_PER_MARKET = 3;

	// Ticker: dari bagian.crypto (pair + harga + chg24h) — angka nyata, bukan contoh.
	const ticker = $derived.by(() => {
		const bag = (kripto?.facts.find((f) => f.key === 'bagian')?.value ?? {}) as Record<string, unknown>;
		const rows = Array.isArray(bag.crypto) ? (bag.crypto as Record<string, unknown>[]) : [];
		return rows.slice(0, 8).map((r) => ({
			pair: String(r.pair ?? '—'),
			harga: typeof r.price === 'number' ? r.price : null,
			chg: typeof r.chg24h === 'number' ? r.chg24h : null
		}));
	});

	// Verdikt besar: berapa pasar punya peluang.
	//
	// Revisi pemilik 7 Okt: "Jika tidak ada sinyal, sebut no signal, bukan malah jurnal
	// mesin mati atau bla bla bla, karena itu artinya system failure, bukan gagal
	// generate sinyal akibat tidak match dengan strategi." — Justru karena pemilik
	// menegaskan yang pertama BUKAN kegagalan, keduanya tidak boleh disamarkan:
	//   - "kosong"  -> TIDAK ADA SINYAL (mesin hidup, tak ada setup cocok). Tenang.
	//   - "gagal"   -> GAGAL SISTEM (sumber/job tak terbaca). Harus berbunyi, karena
	//                  itulah failure yang sesungguhnya.
	const peluang = $derived(daftar.filter((r) => r.ada));
	const pasarAda = $derived(pasarDaftar.filter((p) => p.status_data === 'ada'));
	const pasarKosong = $derived(pasarDaftar.filter((p) => p.status_data === 'kosong'));
	const pasarGagal = $derived(pasarDaftar.filter((p) => p.status_data === 'gagal'));
	const verdikt = $derived.by(() => {
		if (pasarDaftar.length === 0 && daftar.length === 0)
			return { judul: 'BELUM ADA DATA', nada: 'netral', waktu: null, alasan: 'Sumber belum mengirim sinyal.' };

		if (pasarGagal.length) {
			return {
				judul: 'GAGAL SISTEM',
				nada: 'gagal',
				waktu: null,
				alasan:
					`${pasarGagal.length} pasar tidak bisa dibaca: ${pasarGagal.map((p) => p.label).join(', ')}. ` +
					'Ini bukan "tidak ada sinyal" — periksa job pengumpul di halaman Sistem.'
			};
		}
		if (pasarAda.length === 0) {
			return {
				judul: 'TIDAK ADA SINYAL',
				nada: 'diam',
				waktu: null,
				alasan:
					`Mesin berjalan (${pasarKosong.length} pasar dipindai) tetapi tidak ada setup yang ` +
					'lolos strategi saat ini. Itu hasil kerja sistem, bukan kegagalan — menunggu lebih baik daripada memaksa.'
			};
		}
		const sisaKosong = pasarKosong.length ? ` ${pasarKosong.length} pasar lain tanpa setup cocok.` : '';
		return {
			judul: `${pasarAda.length} PELUANG`,
			nada: 'ada',
			waktu: null,
			alasan:
				`Teratas: ${pasarAda[0].label}${pasarAda[0].sinyal[0]?.pair ? ` · ${pasarAda[0].sinyal[0].pair}` : ''}` +
				`${pasarAda[0].sinyal[0]?.skor != null ? ` · skor ${pasarAda[0].sinyal[0].skor}/100` : ''}.` +
				sisaKosong + ' Semua belum terverifikasi — lihat catatan tiap pasar.'
		};
	});

	const formatHarga = (n: number | null) =>
		n == null ? '—' : n >= 1000 ? n.toLocaleString('en-US', { maximumFractionDigits: 0 }) : n >= 1 ? n.toFixed(2) : n.toPrecision(4);

	// SETUP ENTRY — ini yang menjawab "masuk di mana". Datanya SUDAH ada di
	// `detail` tiap pasar; sebelumnya tidak ditampilkan sehingga verdikt "ADA
	// PELUANG" tak memberi harga masuk. Angka ditampilkan apa adanya; yang tidak
	// ada tidak dikarang (mis. forex/idx yang belum punya sinyal).
	type Setup = { label: string; nilai: string; nada?: 'masuk' | 'stop' | 'target' | 'netral' };
	const setupDari = (s: SinyalPasar): Setup[] => {
		const d = (s.detail ?? {}) as Record<string, unknown>;
		const out: Setup[] = [];
		const num = (v: unknown) => (typeof v === 'number' ? v : null);
		const f = (v: number | null) => (v == null ? '—' : formatHarga(v));

		if (s.pasar === 'crypto') {
			const e = num(d.entry), sl = num(d.sl), tp = num(d.tp1);
			if (e != null) out.push({ label: 'Masuk', nilai: f(e), nada: 'masuk' });
			if (sl != null) out.push({ label: 'Stop', nilai: f(sl), nada: 'stop' });
			if (tp != null) out.push({ label: 'Target', nilai: f(tp), nada: 'target' });
			// jarak stop dalam % — dari angka, bukan taksiran
			// QA 7 Okt: ini JARAK STOP, bukan risiko akun. Ukuran posisi menyesuaikan agar
			// risiko tepat 1% ekuitas (risk.py), jadi jangan diberi label "Risiko".
			if (e != null && sl != null) out.push({ label: 'Jarak stop', nilai: `${(Math.abs(e - sl) / e * 100).toFixed(2)}%` });
		} else if (s.pasar === 'polymarket') {
			const wr = num(d.winRate), be = num(d.breakEven_pct);
			if (wr != null) out.push({ label: 'Win-rate', nilai: `${wr.toFixed(2)}%` });
			if (be != null) out.push({ label: 'Break-even', nilai: `${be.toFixed(2)}%` });
			const n = num(d.n), need = num(d.nNeeded);
			if (n != null && need != null) out.push({ label: 'Sampel', nilai: `${n}/${need}` });
		} else if (s.pasar === 'gmgn') {
			const v = num(d.viable), p = num(d.pools);
			if (v != null && p != null) out.push({ label: 'Pool layak', nilai: `${v}/${p}` });
			const vl = num(d.avg_vl);
			if (vl != null) out.push({ label: 'V/L rata²', nilai: vl.toFixed(1) });
		} else if (s.pasar === 'lp') {
			const fee = num(d.fee_hari), umur = num(d.umur_hari);
			if (fee != null) out.push({ label: 'Fee/hari', nilai: `$${fee.toFixed(2)}` });
			if (umur != null) out.push({ label: 'Umur', nilai: `${umur.toFixed(1)} hr` });
		}
		return out;
	};
	const setupTeratas = $derived.by(() => {
		const ada = daftar.filter((r) => r.ada && r.pasar === 'crypto');
		const t = ada[0];
		return t ? setupDari(t) : [];
	});
	const subjekTeratas = $derived(daftar.find((r) => r.ada && r.pasar === 'crypto')?.subjek ?? null);
</script>

<svelte:head><title>War Room — satu layar, semua pasar</title></svelte:head>

<div class="pratinjau">
	<!-- 1. TICKER — DENYUT PASAR, BERJALAN (revisi pemilik 7 Okt: "kalo bisa jalan
	     dan realtime"). Dua hal yang membuatnya benar:
	     (a) BERJALAN — daftar yang sama digambar DUA KALI di dalam satu jalur yang
	         digeser animasi ke kiri; saat salinan pertama habis, salinan kedua sudah
	         tepat di belakangnya -> mulus tanpa lompat. Saat kursor/fokus di atasnya,
	         animasi berhenti (orang butuh membaca angka diam).
	     (b) REALTIME — data di-refresh tiap 15 s dari `bagian.crypto` (harga & chg24h
	         nyata dari MEXC, bukan contoh). Umur data ditulis apa adanya di ekornya. -->
	<div class="ticker" aria-label="Harga pasar (berjalan)">
		<div class="ticker-jalur" class:sepi={ticker.length === 0}>
			{#if ticker.length === 0}
				<span class="tick dim">ticker belum tersedia</span>
			{:else}
				{#each [0, 1] as salinan (salinan)}
					<div class="ticker-set" aria-hidden={salinan === 1}>
						{#each ticker as t (t.pair + '-' + salinan)}
							<span class="tick">
								<span class="tick-pair">{t.pair.replace('USDT', '')}</span>
								<span class="tick-harga angka">{formatHarga(t.harga)}</span>
								{#if t.chg != null}
									<span class="tick-chg angka" class:naik={t.chg >= 0} class:turun={t.chg < 0}>
										{t.chg >= 0 ? '▲' : '▼'}{Math.abs(t.chg).toFixed(2)}%
									</span>
								{/if}
							</span>
						{/each}
					</div>
				{/each}
			{/if}
		</div>
	</div>

	<div class="isi">
		{#if sumber.length}
			<!-- Sumber data: pemilik menyebutkannya eksplisit (Crypto MEXC, IDX Stock Arjum,
			     Forex TVC, Polymarket Dokumentasi PM, Meme GMGN/FOMO, LP Meteora & Uniswap) —
			     sekarang tertulis di halaman, bukan tersembunyi di kepala orang. -->
			<div class="sumber-strip" aria-label="Sumber data tiap pasar">
				<span class="sumber-judul">Sumber data</span>
				{#each sumber as s (s.pasar)}
					<span class="sumber-chip" title={s.keterangan}>
						<span class="sumber-pasar">{s.label}</span>
						<span class="sumber-nama">{s.sumber}</span>
					</span>
				{/each}
			</div>
		{/if}

		<header class="kepala">
			<h1 class="merek">War<span>Room</span></h1>
			<span class="mode">PAPER</span>
			<span class="dim">multi-market · {daftar.length} pasar</span>
			<span class="spacer"></span>
			<span class="dim angka">{umurDetik(kripto?.facts?.[0]?.age_s ?? null)} lalu</span>
		</header>

		<!-- 2. CARD GABUNGAN (revisi pemilik 7 Okt): "card status hari ini X peluang
		     digabung sama card Akurasi & PnL per Market". Alasan di baliknya masuk akal:
		     dua-duanya menjawab pertanyaan yang sama — "hari ini bagaimana?" — dan
		     memisahkannya memaksa mata melompat. Sinyalnya dipindah KE BAWAH card ini
		     (bagian 3 di bawah), bukan hilang. -->
		<section class="kartu-gabung" aria-label="Status hari ini dan akurasi pasar">
		<div class="verdikt {verdikt.nada}" aria-live="polite">
			<p class="verdikt-label">Status hari ini</p>
			<p class="verdikt-judul">{verdikt.judul}</p>
			{#if verdikt.waktu}
				<p class="verdikt-waktu angka">Sinyal digenerate: {verdikt.waktu}</p>
			{/if}
			<p class="verdikt-alasan">{verdikt.alasan}</p>

			<!-- Sinyalnya kini di bagian 3 ("Sinyal per Market") — di sini hanya jumlah
			     dan alasan, supaya card tetap menjawab dalam 3 detik. -->

			<!-- SETUP ENTRY: jawaban "masuk di mana". Hanya bila datanya ada. -->
			{#if setupTeratas.length}
				<div class="setup" aria-label="Setup entry pasar teratas">
					<span class="setup-judul">
						Setup entry{subjekTeratas ? ` · ${subjekTeratas}` : ''}
					</span>
					<div class="setup-baris">
						{#each setupTeratas as st (st.label)}
							<div class="setup-item">
								<span class="setup-label">{st.label}</span>
								<span class="setup-nilai angka {st.nada ?? ''}">{st.nilai}</span>
							</div>
						{/each}
					</div>
				</div>
			{/if}
		</div>

		<!-- 2b. AKURASI & PnL per market (6 Okt) — sekarang DI DALAM card gabungan.
		     Sengaja TIDAK menjumlahkan R dan USD — satuannya beda; kolomnya dipisah. -->
		<div class="pasar akurasi-dalam" aria-label="Akurasi dan PnL per market">
			<div class="judul-bagian">
				<h2>Akurasi &amp; PnL per Market</h2>
				<p class="dim">Dari ledger nyata tiap market. Tingkat pakem: <span class="angka">INSUFFICIENT → DIRECTIONAL → PRELIMINARY → TUNING</span> (n efektif per hari).</p>
			</div>
			{#if akurasi}
				<div class="tabel-wrap">
					<table class="tabel-pasar angka">
						<thead>
							<tr>
								<!-- QA 7 Okt: "n" harus menyebut populasi. Di sini = trade TUNTAS per market. -->
								<th>Market</th><th>Setup terbesar</th><th class="ka" title="Trade TUNTAS (sudah ditutup) — bukan sinyal dinilai, bukan kandidat aktif">Tuntas (n)</th><th class="ka">Hari</th>
								<th class="ka">WR</th><th class="ka">Mean R</th><th class="ka">P&amp;L</th><th>Pakem</th>
							</tr>
						</thead>
						<tbody>
							{#each Object.values(akurasi.pasar) as r (r.pasar)}
								<tr class:kosong={!r.tersedia}>
									<td class="nama-pasar">{r.label ?? r.pasar}</td>
									<td class="dim">{r.setup ?? '—'} <span class="dim">({r.jumlah_setup} setup)</span></td>
									<td class="ka">{r.n ?? '—'}</td>
									<td class="ka">{r.n_hari ?? '—'}</td>
									<td class="ka">{r.winrate_pct != null ? `${r.winrate_pct}%` : '—'}</td>
									<td class="ka {r.mean_r != null && r.mean_r > 0 ? 'pos' : r.mean_r != null && r.mean_r < 0 ? 'neg' : ''}">
										{r.mean_r != null ? `${r.mean_r > 0 ? '+' : ''}${r.mean_r}` : '—'}
									</td>
									<td class="ka">
										{#if r.total_r != null}<span class={r.total_r > 0 ? 'pos' : r.total_r < 0 ? 'neg' : ''}>{r.total_r > 0 ? '+' : ''}{r.total_r} R</span>{/if}
										{#if r.pnl_usd != null}<span class={r.pnl_usd > 0 ? 'pos' : r.pnl_usd < 0 ? 'neg' : ''}>{r.pnl_usd > 0 ? '+' : ''}{r.pnl_usd} USD</span>{/if}
										{#if r.total_r == null && r.pnl_usd == null}—{/if}
									</td>
									<td>
										<span class="pakem pakem-{r.tingkat ?? 'INSUFFICIENT'}">{r.tingkat ?? '—'}</span>
									</td>
								</tr>
								{#if !r.tersedia && r.alasan}
									<tr class="kosong"><td colspan="8" class="dim catatan-alasan">{r.alasan}</td></tr>
								{/if}
							{/each}
						</tbody>
					</table>
				</div>
				<div class="pakem-legend">
					<span class="pakem pakem-INSUFFICIENT">INSUFFICIENT</span> <span class="dim">&lt;10 hari — belum boleh diklaim apa pun</span>
					<span class="pisah">·</span>
					<span class="pakem pakem-DIRECTIONAL">DIRECTIONAL</span> <span class="dim">&lt;30 hari — arah saja, dilarang klaim profit</span>
					<span class="pisah">·</span>
					<span class="pakem pakem-PRELIMINARY">PRELIMINARY</span> <span class="dim">&lt;100 hari — evaluasi awal</span>
					<span class="pisah">·</span>
					<span class="pakem pakem-TUNING">TUNING</span> <span class="dim">≥100 hari — baru boleh tuning</span>
				</div>
				<p class="dim kaki-tabel">
					<b>Populasi:</b> semua kolom di tabel ini dihitung dari <b>trade TUNTAS</b> (sudah ditutup) —
					bukan sinyal yang dinilai, bukan kandidat aktif, bukan posisi berjalan. Angka "n" di narasi
					atau halaman lain bisa berasal dari populasi berbeda; bandingkan hanya yang sama.<br />
					Kolom <b>Setup terbesar</b> = setup dengan trade tuntas terbanyak di market itu (yang lain ada di halaman market).
					<b>Mean R</b> dirata-rata per trade; <b>R</b> tidak bisa dibandingkan antar-market — pakai dompet Rp 10 juta di halaman Riset.
				</p>
			{:else}
				<p class="dim">Ringkasan akurasi belum tersedia.</p>
			{/if}
		</div>
		</section>

		<!-- 3. SINYAL PER MARKET (revisi pemilik 7 Okt).
		     Aturan yang dikodekan di sini, kata per kata dari pemilik:
		       - "hanya ditampilkan 3 terbaik per market" -> slice(MAKS_PER_MARKET)
		       - "jika sinyal harian lebih dari 3 ada tombol klik lainnya yang mengarah
		         ke halaman tiap market" -> tombol "Lihat semua (N)" muncul HANYA bila
		         jumlahnya benar-benar lebih dari 3.
		       - "jika tidak ada sinyal, sebut no signal, bukan jurnal mesin mati" ->
		         "kosong" (mesin hidup) ditulis "tidak ada sinyal · alasan yang bisa
		         dibaca manusia"; "gagal" (mesin mati) TETAP berbunyi sebagai kegagalan
		         sistem, karena itu memang failure — dua hal ini tidak boleh seragam. -->
		<section class="pasar" aria-label="Sinyal per market">
			<div class="judul-bagian">
				<h2>Sinyal per Market</h2>
				<p class="dim">
					Maks {MAKS_PER_MARKET} terbaik per market, urut skor aturan. Tanda
					<b>tidak ada sinyal</b> = mesin hidup tetapi tidak ada setup yang cocok;
					<b class="neg">gagal sistem</b> = sumber/job tak terbaca — dua hal berbeda.
				</p>
			</div>
			<div class="sinyal-grid">
				{#each pasarDaftar as p (p.pasar)}
					<article class="sinyal-kartu {p.status_data}">
						<header class="sinyal-kepala">
							<div class="sinyal-judul">
								<h3>{p.label}</h3>
								<!-- QA 7 Okt: setiap kartu market wajib menyebut LIVE/PAPER/HISTORIS.
								     Tanpa ini pembaca menebak apakah angka masih hidup; IDX misalnya
								     HISTORIS karena mesinnya dibekukan. -->
								{#if p.mode}
									<span class="mode-badge mode-{p.mode.toLowerCase()}" title={p.catatan_mode ?? ''}>{p.mode}</span>
								{/if}
							</div>
							{#if p.jumlah > MAKS_PER_MARKET}
								<a class="lihat-semua" href={p.rute}>Lihat semua ({p.jumlah}) →</a>
							{:else if p.status_data === 'ada'}
								<a class="lihat-semua" href={p.rute}>Buka {p.label.split(' (')[0]} →</a>
							{/if}
						</header>
						{#if p.sumber}
							<p class="sinyal-sumber">
								sumber: {p.sumber}{#if p.sinyal[0]?.umur_s != null} · data {umurDetik(p.sinyal[0].umur_s)} lalu{/if}
							</p>
						{/if}

						{#if p.status_data === 'ada'}
							{#each p.sinyal.slice(0, MAKS_PER_MARKET) as s, i (s.pair ?? i)}
								<div class="sinyal-baris">
									<div class="sinyal-kiri">
										<span class="sinyal-pair angka">{s.pair ?? '—'}</span>
										{#if s.arah}<span class="sinyal-arah {s.arah === 'LONG' || s.arah === 'BELI' ? 'pos' : 'neg'}">{s.arah}</span>{/if}
										{#if s.tier}<span class="sinyal-tier">{s.tier}</span>{/if}
									</div>
									<div class="sinyal-kanan angka dim">
										{#if s.entry != null}<span>e {formatHarga(typeof s.entry === 'number' ? s.entry : Number(s.entry))}</span>{/if}
										{#if s.sl != null}<span>s {formatHarga(typeof s.sl === 'number' ? s.sl : Number(s.sl))}</span>{/if}
										{#if s.tp1 != null}<span>t {formatHarga(typeof s.tp1 === 'number' ? s.tp1 : Number(s.tp1))}</span>{/if}
										{#if s.umur_s != null}<span class="umur">{umurDetik(s.umur_s)} lalu</span>{/if}
									</div>
								</div>
							{/each}
						{:else if p.status_data === 'kosong'}
							<p class="sinyal-kosong">Tidak ada sinyal. {p.alasan}</p>
						{:else}
							<p class="sinyal-gagal">⚠ {p.alasan}</p>
						{/if}
					</article>
				{/each}
				{#if pasarDaftar.length === 0}
					<p class="dim">Daftar sinyal per market belum tersedia{galat ? `: ${galat}` : '.'}</p>
				{/if}
			</div>
		</section>

		<!-- 4. STATUS per pasar — murni catatan kejujuran & skor. Daftar sinyalnya ada di
		     bagian 3; mengulang setup di sini membuat satu halaman memuat dua daftar yang
		     sama (keluhan pemilik: "card dibawahnya belum tersusun rapi"). -->
		<section class="pasar" aria-label="Rincian per pasar">
			{#each daftar as s (s.pasar)}
				<article class="baris" class:kosong={!s.ada}>
					<div class="baris-kiri">
						<span class="nama">{s.label}</span>
						{#if s.subjek}<span class="subjek angka">{s.subjek}</span>{/if}
					</div>
					<div class="baris-kanan">
						{#if s.skor != null}
							<span class="skor angka">{s.skor}<span class="dari">/100</span></span>
						{:else}
							<span class="skor angka kosong">—</span>
						{/if}
						<span class="tanda" class:ada={s.ada} class:belum={!s.ada}>
							{s.ada ? (s.arah ?? 'ADA') : 'TIDAK ADA'}
						</span>
					</div>
					{#if s.dibuat_pada}
						<p class="mini-waktu angka">
							🕒 dibuat {waktuWIB(s.dibuat_pada)}{s.umur_sinyal_s != null ? ` · ${umurDetik(s.umur_sinyal_s)} lalu` : ''}
						</p>
					{/if}
					{#if s.catatan_kejujuran}
						<p class="catatan">{s.catatan_kejujuran}</p>
					{/if}

				</article>
			{/each}
			{#if daftar.length === 0}
				<p class="dim">Belum ada pasar yang bisa ditampilkan{galat ? `: ${galat}` : '.'}</p>
			{/if}
		</section>

		<p class="kaki dim">
			Ticker denyut pasar, satu verdikt besar, lalu rincian per pasar. Angka apa adanya
			dari sumber; yang belum ada ditandai "—".
		</p>
	</div>
</div>

<style>
	/* Arah ini SUDAH dipromosikan: nilainya kini token global di app.css
	   (lapis primitive --p-mint-400 dst), jadi tidak ada nilai mentah di sini. */
	.pratinjau {
		--mint: var(--color-accent);
		--kuning: var(--color-warn);
		--merah: var(--color-neg);
		--latar: var(--color-bg);
		--permukaan: var(--color-surface);
		--garis: var(--color-line);
		--tinta: var(--color-text);
		--redup: var(--color-text-3);
	}

	.peluang-daftar { display: flex; flex-wrap: wrap; gap: 0.4rem; margin: 0.5rem 0 0.25rem; }
	.peluang-chip {
		display: inline-flex; align-items: center; gap: 0.4rem;
		border: 1px solid var(--garis); border-radius: 999px;
		padding: 0.2rem 0.65rem; font-size: 0.75rem; text-decoration: none;
		background: var(--permukaan); color: var(--tinta);
	}
	.peluang-chip:hover { border-color: var(--mint); }
	.chip-nama { color: var(--redup); }
	.chip-subjek { font-weight: 700; }
	.chip-arah { color: var(--mint); font-weight: 700; font-size: 0.68rem; }
	.pakem-legend { display: flex; flex-wrap: wrap; gap: 0.35rem; align-items: center; margin-top: 0.5rem; font-size: 0.7rem; }
	.pakem-legend .pisah { color: var(--redup); }

	.judul-bagian { margin: 0.5rem 0 0.75rem; }
	.judul-bagian h2 { font-size: 1.05rem; margin: 0 0 0.15rem; letter-spacing: 0.01em; }
	.tabel-wrap { overflow-x: auto; border: 1px solid var(--garis); border-radius: 0.75rem; background: var(--permukaan); }
	.tabel-pasar { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
	.tabel-pasar th { text-align: left; font-weight: 500; color: var(--redup); padding: 0.6rem 0.75rem; border-bottom: 1px solid var(--garis); white-space: nowrap; }
	.tabel-pasar td { padding: 0.55rem 0.75rem; border-bottom: 1px solid var(--garis); vertical-align: top; }
	.tabel-pasar tr:last-child td { border-bottom: none; }
	.tabel-pasar .ka { text-align: right; }
	.tabel-pasar .nama-pasar { text-transform: capitalize; font-weight: 600; }
	.tabel-pasar tr.kosong { opacity: 0.75; }
	.catatan-alasan { font-size: 0.75rem; padding-top: 0 !important; }
	.kaki-tabel { margin-top: 0.5rem; font-size: 0.72rem; }
	.pakem { display: inline-block; padding: 0.1rem 0.45rem; border-radius: 0.45rem; border: 1px solid var(--garis); font-size: 0.68rem; font-weight: 700; letter-spacing: 0.02em; }
	.pakem-INSUFFICIENT { color: var(--merah); border-color: var(--merah); }
	.pakem-DIRECTIONAL { color: var(--kuning); border-color: var(--kuning); }
	.pakem-PRELIMINARY { color: var(--mint); border-color: var(--mint); }
	.pakem-TUNING { color: var(--tinta); border-color: var(--tinta); }
	.pos { color: var(--mint); }
	.neg { color: var(--merah); }

	.verdikt-waktu { font-size: 0.78rem; color: var(--redup); margin: 0.1rem 0 0.35rem; }
	.mini-waktu { font-size: 0.72rem; color: var(--redup); margin: 0.2rem 0 0; }

	/* Ticker BERJALAN: dua salinan identik di dalam satu jalur; jalur digeser -50%
	   (tepat selebar satu salinan) sehingga terlihat mulus tanpa lompat. */
	.ticker {
		display: flex;
		align-items: center;
		padding: 0.5rem 0;
		border-bottom: 1px solid var(--garis);
		background: var(--permukaan);
		overflow: hidden;
		white-space: nowrap;
	}
	.ticker-jalur {
		display: flex;
		flex-shrink: 0;
		width: max-content;
		animation: geser-ticker 45s linear infinite;
	}
	.ticker-jalur.sepi { animation: none; padding: 0 1rem; width: auto; }
	.ticker:hover .ticker-jalur, .ticker:focus-within .ticker-jalur { animation-play-state: paused; }
	.ticker-set { display: flex; gap: 1.75rem; padding-right: 1.75rem; flex-shrink: 0; }
	@keyframes geser-ticker { from { transform: translateX(0); } to { transform: translateX(-50%); } }
	@media (prefers-reduced-motion: reduce) { .ticker-jalur { animation: none; } }

	/* Card gabungan status + akurasi (revisi 7 Okt) */
	.kartu-gabung {
		border: 1px solid var(--garis);
		border-radius: 1rem;
		background: var(--permukaan);
		overflow: hidden;
	}
	.akurasi-dalam { border-top: 1px solid var(--garis); padding: 1rem; margin: 0; }
	.verdikt { border-radius: 0; border: none; }

	/* Sinyal per market */
	.sinyal-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(19rem, 1fr)); gap: 0.75rem; }
	.sinyal-kartu {
		border: 1px solid var(--garis); border-radius: 0.75rem;
		background: var(--permukaan); padding: 0.75rem 0.85rem;
	}
	.sinyal-kartu.gagal { border-color: var(--merah); }
	.sinyal-kepala { display: flex; align-items: baseline; justify-content: space-between; gap: 0.5rem; margin-bottom: 0.4rem; }
	.sinyal-kepala h3 { font-size: 0.85rem; margin: 0; letter-spacing: 0.01em; }
	.sinyal-judul { display: inline-flex; align-items: baseline; gap: 0.4rem; }
	.mode-badge {
		font-size: 0.6rem; font-weight: 700; letter-spacing: 0.06em;
		border: 1px solid var(--garis); border-radius: 0.35rem; padding: 0.05rem 0.3rem;
		color: var(--redup);
	}
	.mode-badge.mode-paper { color: var(--kuning); border-color: var(--kuning); }
	.mode-badge.mode-historis { color: var(--redup); border-style: dashed; }
	.mode-badge.mode-live { color: var(--mint); border-color: var(--mint); }
	.sinyal-sumber { font-size: 0.66rem; color: var(--redup); margin: 0 0 0.35rem; }
	.lihat-semua { font-size: 0.7rem; color: var(--mint); text-decoration: none; white-space: nowrap; }
	.lihat-semua:hover { text-decoration: underline; }
	.sinyal-baris { display: flex; justify-content: space-between; gap: 0.5rem; padding: 0.3rem 0; border-top: 1px dashed var(--garis); align-items: baseline; }
	.sinyal-baris:first-of-type { border-top: none; }
	.sinyal-kiri { display: inline-flex; align-items: baseline; gap: 0.4rem; }
	.sinyal-pair { font-weight: 700; font-size: 0.82rem; }
	.sinyal-arah { font-weight: 700; font-size: 0.68rem; letter-spacing: 0.03em; }
	.sinyal-tier { font-size: 0.62rem; color: var(--redup); border: 1px solid var(--garis); border-radius: 0.35rem; padding: 0 0.3rem; }
	.sinyal-kanan { font-size: 0.7rem; display: inline-flex; gap: 0.5rem; }
	.sinyal-kanan .umur { color: var(--redup); }
	.sinyal-kosong { font-size: 0.74rem; color: var(--redup); margin: 0.2rem 0 0; }
	.sinyal-gagal { font-size: 0.74rem; color: var(--merah); margin: 0.2rem 0 0; }
	.verdikt.gagal { border-left: 3px solid var(--merah); }
	.tick {
		display: inline-flex;
		align-items: baseline;
		gap: 0.4rem;
		font-size: 0.75rem;
	}
	.tick-pair {
		color: var(--redup);
		font-weight: 600;
		letter-spacing: 0.04em;
	}
	.tick-harga {
		color: var(--tinta);
		font-weight: 600;
	}
	.tick-chg {
		font-weight: 600;
	}
	.tick-chg.naik {
		color: var(--mint);
	}
	.tick-chg.turun {
		color: var(--merah);
	}

	.isi {
		max-width: 62rem;
		margin: 0 auto;
		padding: 1.5rem 1rem 3rem;
		display: flex;
		flex-direction: column;
		gap: 1.25rem;
	}

	.sumber-strip { display: flex; flex-wrap: wrap; gap: 0.4rem; align-items: center; }
	.sumber-judul { font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--redup); }
	.sumber-chip {
		display: inline-flex; align-items: baseline; gap: 0.35rem;
		border: 1px solid var(--garis); border-radius: 999px; padding: 0.15rem 0.6rem;
		font-size: 0.7rem; background: var(--permukaan);
	}
	.sumber-pasar { color: var(--redup); }
	.sumber-nama { font-weight: 600; color: var(--tinta); }

	.kepala {
		display: flex;
		align-items: baseline;
		gap: 0.75rem;
		flex-wrap: wrap;
	}
	.merek {
		font-family: var(--font-display);
		font-size: 1.5rem;
		font-weight: 700;
		letter-spacing: -0.02em;
		margin: 0;
	}
	.merek span {
		color: var(--mint);
	}
	.mode {
		font-size: 0.7rem;
		font-weight: 700;
		letter-spacing: 0.1em;
		padding: 0.15rem 0.5rem;
		border: 1px solid var(--mint);
		color: var(--mint);
		border-radius: 999px;
	}
	.spacer {
		flex: 1;
	}

	/* Verdikt: satu blok besar, ini jawaban 3 detik. */
	.verdikt {
		border: 1px solid var(--garis);
		border-radius: 14px;
		padding: 1.5rem 1.5rem 1.35rem;
		background: var(--permukaan);
	}
	.verdikt.ada {
		border-color: color-mix(in srgb, var(--mint) 45%, var(--garis));
		background: linear-gradient(180deg, color-mix(in srgb, var(--mint) 8%, var(--permukaan)), var(--permukaan));
	}
	.verdikt.diam {
		border-color: var(--garis);
	}
	.verdikt-label {
		font-size: 0.7rem;
		font-weight: 700;
		letter-spacing: 0.14em;
		text-transform: uppercase;
		color: var(--redup);
		margin: 0 0 0.35rem;
	}
	.verdikt-judul {
		font-family: var(--font-display);
		font-size: clamp(2rem, 6vw, 3.25rem);
		font-weight: 700;
		letter-spacing: -0.03em;
		line-height: 1;
		margin: 0;
	}
	.verdikt.ada .verdikt-judul {
		color: var(--mint);
	}
	.verdikt-alasan {
		margin: 0.75rem 0 0;
		font-size: 0.9rem;
		color: var(--tinta);
		opacity: 0.85;
		max-width: 46rem;
	}

	.pasar {
		display: flex;
		flex-direction: column;
		border: 1px solid var(--garis);
		border-radius: 14px;
		overflow: hidden;
		background: var(--permukaan);
	}
	.baris {
		display: grid;
		grid-template-columns: 1fr auto;
		gap: 0.25rem 1rem;
		padding: 0.85rem 1.1rem;
		border-bottom: 1px solid var(--garis);
	}
	.baris:last-child {
		border-bottom: 0;
	}
	.baris.kosong {
		background: color-mix(in srgb, var(--latar) 55%, var(--permukaan));
	}
	.baris-kiri {
		display: flex;
		align-items: baseline;
		gap: 0.6rem;
		min-width: 0;
	}
	.nama {
		font-weight: 600;
	}
	.subjek {
		font-size: 0.8rem;
		color: var(--redup);
	}
	.baris-kanan {
		display: flex;
		align-items: baseline;
		gap: 0.75rem;
	}
	.skor {
		font-size: 1.35rem;
		font-weight: 700;
	}
	.skor.kosong {
		color: var(--redup);
	}
	.dari {
		font-size: 0.7rem;
		font-weight: 400;
		color: var(--redup);
	}
	.tanda {
		font-size: 0.68rem;
		font-weight: 700;
		letter-spacing: 0.08em;
		padding: 0.15rem 0.5rem;
		border-radius: 999px;
		border: 1px solid;
		white-space: nowrap;
	}
	.tanda.ada {
		color: var(--mint);
		border-color: color-mix(in srgb, var(--mint) 45%, transparent);
		background: color-mix(in srgb, var(--mint) 10%, transparent);
	}
	.tanda.belum {
		color: var(--redup);
		border-color: var(--garis);
	}
	.catatan {
		grid-column: 1 / -1;
		margin: 0.35rem 0 0;
		font-size: 0.78rem;
		color: var(--redup);
		line-height: 1.45;
	}
	.kaki {
		font-size: 0.78rem;
		line-height: 1.5;
		margin: 0;
	}

	/* Setup entry — blok "masuk di mana" di dalam verdikt. */
	.setup {
		margin-top: 1.1rem;
		padding-top: 1rem;
		border-top: 1px solid var(--garis);
	}
	.setup-judul {
		display: block;
		font-size: 0.7rem;
		font-weight: 700;
		letter-spacing: 0.12em;
		text-transform: uppercase;
		color: var(--redup);
		margin-bottom: 0.6rem;
	}
	.setup-baris {
		display: flex;
		flex-wrap: wrap;
		gap: 1.75rem;
	}
	.setup-item {
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
	}
	.setup-label {
		font-size: 0.68rem;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--redup);
	}
	.setup-nilai {
		font-size: 1.15rem;
		font-weight: 700;
	}
	.setup-nilai.masuk {
		color: var(--mint);
	}
	.setup-nilai.stop {
		color: var(--merah);
	}
	.setup-nilai.target {
		color: var(--kuning);
	}

	/* Setup ringkas di tiap baris pasar. */
	.setup-mini {
		grid-column: 1 / -1;
		margin: 0.45rem 0 0;
		font-size: 0.78rem;
		color: var(--redup);
		display: flex;
		flex-wrap: wrap;
		gap: 0.3rem;
		align-items: baseline;
	}
	.setup-mini-label {
		margin-right: 0.25rem;
	}
	.pisah {
		margin: 0 0.35rem;
		opacity: 0.5;
	}
	.setup-mini-nilai {
		color: var(--tinta);
		font-weight: 600;
	}
	.setup-mini-nilai.masuk {
		color: var(--mint);
	}
	.setup-mini-nilai.stop {
		color: var(--merah);
	}
	.setup-mini-nilai.target {
		color: var(--kuning);
	}
	.dim {
		color: var(--redup);
	}
	.angka {
		font-family: var(--font-mono);
		font-variant-numeric: tabular-nums;
	}
</style>
