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
	import { getArea, getAreaFakta, getLiveArming, getPasarRingkas, getSinyalPerPasar, getSumber, getVerdict } from '$lib/api/client';
	import type { AreaPayload, MarketSignalList, LiveArming, MarketSummaryPayload, MarketSignal, SignalPayload, MarketVerdict } from '$lib/api/types';
	import { angka, umurDetik, waktuWIB } from '$lib/format';
	import Istilah from '$lib/components/Istilah.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
	// Komponen fondasi tema baru (DESIGN-USULAN 16 Okt): honesty-tag pada setiap
	// status verifikasi, track bar untuk skor ber-maksimum.
	import HonestyTag from '$lib/components/HonestyTag.svelte';
	import TrackBar from '$lib/components/TrackBar.svelte';

	let sinyal = $state<SignalPayload | null>(null);
	let kripto = $state<AreaPayload | null>(null);
	let akurasi = $state<MarketSummaryPayload | null>(null);
	let galat = $state<string | null>(null);
	// Sumber data tiap pasar (revisi pemilik 7 Okt): satu tempat, tidak perlu ditebak.
	let sumber = $state<{ pasar: string; label: string; sumber: string; keterangan: string }[]>([]);
	// Verdict kanonik (audit QA 7 Okt) — dipakai agar Home TIDAK menyusun kesimpulan sendiri.
	let verdictSemua = $state<MarketVerdict[]>([]);
	// Dompet paper $20 (15 Okt): angka NYATA dari fakta — crypto dari siklus paper20,
	// Polymarket dari arm D (band favorit). GMGN berjalan di mesin terpisah (link).
	let dompetCrypto = $state<Record<string, any> | null>(null);
	let dompetPoly = $state<number | null>(null);
	// Mode eksekusi global dari API arming — SATU-SATUNYA sumber badge mode di header Home.
	let arming = $state<LiveArming | null>(null);
async function muat() {
	const [s, k, a, sm, m, sys, poly] = await Promise.allSettled([
		getSinyalPerPasar(),
		getArea('crypto'),
		getPasarRingkas(),
		getSumber(),
		getLiveArming(),
		getAreaFakta('sistem'),
		getArea('polymarket')
	]);
	if (sm.status === 'fulfilled') sumber = sm.value.sumber;
	try {
		verdictSemua = (await getVerdict()).verdict;
	} catch {
		/* verdict opsional di Home; kalau gagal, judul memakai hitungan lama */
	}
	if (s.status === 'fulfilled') { sinyal = s.value; galat = null; }
	else galat = s.reason instanceof Error ? s.reason.message : String(s.reason);
	if (k.status === 'fulfilled') kripto = k.value;
	if (a.status === 'fulfilled') akurasi = a.value;
	if (m.status === 'fulfilled') arming = m.value;
	if (sys.status === 'fulfilled') {
		const f = (sys.value.facts ?? []).find((x: any) => x.kind === 'paper20' && x.key === 'dompet');
		dompetCrypto = f ? (f.value as Record<string, any>) : null;
	} else dompetCrypto = null;
	if (poly.status === 'fulfilled') {
		const pp = (poly.value.facts ?? []).find((x: any) => x.key === 'poly_paper');
		const arms = ((pp?.value as any)?.arms ?? []) as any[];
		const d = arms.find((x) => x.nama === 'D favorit');
		dompetPoly = d ? Number(d.balance ?? 20) : null;
	} else dompetPoly = null;
}
	$effect(() => {
		void muat();
		const t = setInterval(() => void muat(), 15000);
		return () => clearInterval(t);
	});

	const daftar = $derived(sinyal?.sinyal ?? []);
	const pasarDaftar = $derived(sinyal?.pasar ?? []);
	// Kejujuran per kartu: MarketSignal (daftar) membawa `terverifikasi`, `catatan_kejujuran`,
	// `umur_sinyal_s`, `dibuat_pada` — MarketSignalList (pasar) belum. Gabungkan per pasar supaya
	// tiap kartu menampilkan status verifikasi + umur SINYALNYA (bukan umur fakta crypto).
	const jujurPerPasar = $derived.by(() => {
		const m = new Map<string, MarketSignal>();
		for (const s of sinyal?.sinyal ?? []) m.set(s.pasar, s);
		return m;
	});
	const kartuJujur = (p: MarketSignalList) => {
		const s = jujurPerPasar.get(p.pasar);
		const terverifikasi = p.terverifikasi ?? s?.terverifikasi ?? null;
		const catatan = p.catatan_kejujuran || s?.catatan_kejujuran || '';
		const umur_s = p.umur_sinyal_s ?? s?.umur_sinyal_s ?? p.sinyal[0]?.umur_s ?? null;
		const dibuat = p.dibuat_pada ?? s?.dibuat_pada ?? null;
		return { terverifikasi, catatan, umur_s, dibuat };
	};
	const ringkasCatatan = (t: string) => (t.length > 140 ? `${t.slice(0, 137).trimEnd()}…` : t);
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

	// SSOT: Kandidat teratas yang disorot di teks verdikt dan kartu setup entry
	const pasarTeratas = $derived(pasarAda[0] ?? null);
	const sinyalTeratas = $derived(pasarTeratas?.sinyal?.[0] ?? null);

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
		// PRIORITAS 3 AUDIT: satu angka untuk banyak arti menyesatkan. "6 peluang" dulu
		// mencampur kandidat, posisi paper, dan hasil yang belum lewat gate — pembaca
		// menyimpulkan "ada 6 yang layak dieksekusi". Sekarang dipisah tegas:
		//   KANDIDAT  = ada sesuatu untuk dipantau (belum tentu layak)
		//   PROMOTABLE= lolos SEMUA gate (angka ini biasanya 0, dan itu JUJUR)
		// 9 Okt 2026 — bahasa manusia: pemilik keluh "terlalu pro, targetnya bot trading doang".
		// Judul tidak lagi memakai "KANDIDAT/lolos gate" (jargon) di baris utama; jargonnya
		// turun ke alasan (dengan <Istilah>) supaya yang awam paham detik pertama.
		const promotable = verdictSemua.filter((v) => v.promotable_edge).length;
		const judul = promotable
			? `${promotable} pasar layak dibeli`
			: `Bot memantau ${pasarAda.length} pasar · belum ada yang layak dibeli`;
		return {
			judul,
			nada: 'ada',
			waktu: null,
			alasan:
				(promotable
					? `Ada ${promotable} pasar yang sudah lulus semua pemeriksaan wajib. `
					: 'Ada yang dipantau, tetapi belum ada yang lulus semua pemeriksaan wajib. Ini normal: lebih baik menunggu daripada memaksa beli. ') +
				(pasarTeratas
					? `Teratas: ${pasarTeratas.label}${sinyalTeratas?.pair ? ` · ${sinyalTeratas.pair}` : ''}` +
					  `${sinyalTeratas?.skor != null ? ` · skor ${sinyalTeratas.skor}/100` : ''}.`
					: '') +
				sisaKosong
		};
	});

	const formatHarga = (n: number | null) =>
		n == null ? '—' : n >= 1000 ? angka(n, { desimal: 0 }) : angka(n, { desimal: 2 });

	// SETUP ENTRY — ini yang menjawab "masuk di mana". Datanya SUDAH ada di
	// `detail` tiap pasar; sebelumnya tidak ditampilkan sehingga verdikt "ADA
	// PELUANG" tak memberi harga masuk. Angka ditampilkan apa adanya; yang tidak
	// ada tidak dikarang (mis. forex/idx yang belum punya sinyal).
	type Setup = { label: string; nilai: string; nada?: 'masuk' | 'stop' | 'target' | 'netral' };
	const setupDari = (s: MarketSignal): Setup[] => {
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
			if (e != null && sl != null) out.push({ label: 'Jarak stop', nilai: `${angka((Math.abs(e - sl) / e) * 100)}%` });
		} else if (s.pasar === 'polymarket') {
			const wr = num(d.winRate), be = num(d.breakEven_pct);
			if (wr != null) out.push({ label: 'Win-rate', nilai: `${angka(wr)}%` });
			if (be != null) out.push({ label: 'Break-even', nilai: `${angka(be)}%` });
			const n = num(d.n), need = num(d.nNeeded);
			if (n != null && need != null) out.push({ label: 'Sampel', nilai: `${n}/${need}` });
		} else if (s.pasar === 'gmgn') {
			const v = num(d.viable), p = num(d.pools);
			if (v != null && p != null) out.push({ label: 'Pool layak', nilai: `${v}/${p}` });
			const vl = num(d.avg_vl);
			if (vl != null) out.push({ label: 'V/L rata²', nilai: angka(vl, { desimal: 1 }) });
		} else if (s.pasar === 'lp') {
			const fee = num(d.fee_hari), umur = num(d.umur_hari);
			if (fee != null) out.push({ label: 'Fee/hari', nilai: `$${angka(fee)}` });
			if (umur != null) out.push({ label: 'Umur', nilai: `${angka(umur, { desimal: 1 })} hr` });
		}
		return out;
	};

	const setupTeratas = $derived.by(() => {
		if (!pasarTeratas) return [];
		const out: Setup[] = [];
		const num = (v: unknown) => (typeof v === 'number' ? v : null);
		const f = (v: number | null) => (v == null ? '—' : formatHarga(v));

		if (pasarTeratas.pasar === 'crypto' && sinyalTeratas) {
			const e = num(sinyalTeratas.entry), sl = num(sinyalTeratas.sl), tp = num(sinyalTeratas.tp1);
			if (e != null) out.push({ label: 'Masuk', nilai: f(e), nada: 'masuk' });
			if (sl != null) out.push({ label: 'Stop', nilai: f(sl), nada: 'stop' });
			if (tp != null) out.push({ label: 'Target', nilai: f(tp), nada: 'target' });
			if (e != null && sl != null && e > 0) out.push({ label: 'Jarak stop', nilai: `${angka((Math.abs(e - sl) / e) * 100)}%` });
			if (out.length) return out;
		}

		// Fallback ke detail dari bentuk legacy (daftar/MarketSignal) bila pasar non-crypto
		const sp = daftar.find((r) => r.ada && r.pasar === pasarTeratas.pasar);
		return sp ? setupDari(sp) : [];
	});

	const subjekTeratas = $derived.by(() => {
		if (sinyalTeratas?.pair) return sinyalTeratas.pair;
		if (pasarTeratas) {
			return daftar.find((r) => r.ada && r.pasar === pasarTeratas.pasar)?.subjek ?? null;
		}
		return null;
	});

	const verdictTeratas = $derived(
		sinyalTeratas?.autotrade_verdict ?? pasarTeratas?.autotrade_verdict ?? 'PANTAU'
	);
	const confluenceTeratas = $derived(
		(sinyalTeratas?.confluence && sinyalTeratas.confluence.length > 0)
			? sinyalTeratas.confluence
			: (pasarTeratas?.confluence ?? [])
	);
	const metricsTeratas = $derived(
		sinyalTeratas?.metrics && Object.keys(sinyalTeratas.metrics).length > 0
			? sinyalTeratas.metrics
			: (pasarTeratas?.metrics ?? {})
	);
	const alasanTeratas = $derived(
		sinyalTeratas?.alasan_eksekusi ?? pasarTeratas?.alasan_eksekusi ?? ''
	);
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
	         nyata dari OKX, bukan contoh). Umur data ditulis apa adanya di ekornya. -->
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
										{t.chg >= 0 ? '▲' : '▼'}{angka(Math.abs(t.chg))}%
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
			<section class="dompet20-strip" aria-label="Dompet paper $20 per market">
				<span class="sumber-judul">Dompet paper $20</span>
				<div class="dompet-grid">
					<div class="dompet-chip">
						<span class="sumber-pasar">Crypto</span>
						<span class="angka sumber-nama">
							{dompetCrypto ? `$${dompetCrypto.equity_usd} · ${dompetCrypto.n_posisi} posisi` : 'menunggu siklus'}
						</span>
					</div>
					<div class="dompet-chip">
						<span class="sumber-pasar">Poly arm D</span>
						<span class="angka sumber-nama">{dompetPoly !== null ? `$${dompetPoly.toFixed(2)}` : '—'}</span>
					</div>
					<div class="dompet-chip">
						<span class="sumber-pasar">Memecoin GMGN</span>
						<span class="angka sumber-nama">$20 · <a href="/gmgn/" class="text-accent">/gmgn</a></span>
					</div>
				</div>
			</section>
		{/if}
		{#if sumber.length}
			<!-- Sumber data: pemilik menyebutkannya eksplisit (Crypto OKX, IDX Stock Arjum,
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

		<!-- Kepala halaman diseragamkan 28 Okt 2026: sebelumnya Beranda memakai hero
		     merek sendiri (`.kepala` / `.merek`) sehingga ritmenya berbeda dari 13
		     halaman lain. Isi blok di bawah tidak diubah. -->
		<PageHeader
			eyebrow="War Room · Beranda"
			title="Ringkasan hari ini"
			tag={arming ? (arming.armed ? 'LIVE' : 'PAPER') : null}
			description={`Multi-market · ${daftar.length} pasar · data terakhir ${umurDetik(kripto?.facts?.[0]?.age_s ?? null)} lalu`}
			sumber="pasar/ringkas + sinyal/per-pasar"
			terverifikasi={true}
		/>

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

			<!-- SETUP ENTRY: jawaban "masuk di mana" dengan format konfluensi terpadu. -->
			{#if Object.keys(metricsTeratas).length || setupTeratas.length}
				<div class="setup" aria-label="Setup entry pasar teratas">
					<div class="setup-kepala">
						<span class="setup-judul">
							Setup entry{subjekTeratas ? ` · ${subjekTeratas}` : ''}
						</span>
						<span class="badge-verdict {verdictTeratas.toLowerCase()}">
							{#if verdictTeratas === 'OKE'}
								● OKE AUTOTRADE
							{:else if verdictTeratas === 'PANTAU'}
								● PANTAU / KANDIDAT
							{:else}
								● SKIP / TOLAK
							{/if}
						</span>
					</div>

					{#if confluenceTeratas.length}
						<div class="setup-confluence">
							<span class="section-label">Konfluensi Pemicu</span>
							<div class="confluence-grid">
								{#each confluenceTeratas as c}
									<div class="confluence-pill">{c}</div>
								{/each}
							</div>
						</div>
					{/if}

					{#if Object.keys(metricsTeratas).length}
						<div class="setup-bento">
							{#each Object.entries(metricsTeratas) as [label, nilai]}
								<div class="bento-box">
									<span class="bento-lbl">{label}</span>
									<span class="bento-val angka">{nilai}</span>
								</div>
							{/each}
						</div>
					{:else}
						<div class="setup-baris">
							{#each setupTeratas as st (st.label)}
								<div class="setup-item">
									<span class="setup-label">{st.label}</span>
									<span class="setup-nilai angka {st.nada ?? ''}">{st.nilai}</span>
								</div>
							{/each}
						</div>
					{/if}

					{#if alasanTeratas}
						<p class="setup-alasan">
							<span class="dim">Alasan eksekusi:</span> <b>{alasanTeratas}</b>
						</p>
					{/if}
				</div>
			{/if}
		</div>

		<!-- 2b. AKURASI & PnL per market (6 Okt) — sekarang DI DALAM card gabungan.
		     Sengaja TIDAK menjumlahkan R dan USD — satuannya beda; kolomnya dipisah. -->
		<!-- Lapisan 2 (bukti ringkas) — tetap di dalam card gabungan, tetapi tabelnya
		     dilipat: yang dibutuhkan saat memindai adalah JUDUL + kesimpulan; tabel 5 baris
		     dibuka saat pembaca memang mau membandingkan. -->
		<details class="pasar akurasi-dalam lipat-akurasi" aria-label="Akurasi dan PnL per market">
			<summary>
				<span class="ringkas-judul">Akurasi &amp; PnL per Market</span>
				<span class="dim">dari ledger nyata · trade tuntas</span>
				<span class="petunjuk">buka tabel</span>
			</summary>
			<div class="isi-lipat">
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
									<td class="nama-pasar">
										{r.label ?? r.pasar}
										<!-- QA 7 Okt: Forex belum cost-adjusted (spread/komisi broker tak ada
										     di jurnal). Ditandai agar tidak dibandingkan langsung dengan yang net. -->
										{#if r.pasar === 'forex' || r.pasar === 'lp'}
											<span class="tanda-biaya" title="Angka bruto — biaya broker/on-chain belum tercatat">BRUTO</span>
										{/if}
									</td>
									<td class="dim">{r.setup ?? '—'} <span class="dim">({r.jumlah_setup} setup)</span></td>
									<td class="ka">{r.n ?? '—'}</td>
									<td class="ka">{r.n_hari ?? '—'}</td>
									<td class="ka">{r.winrate_pct != null ? `${angka(r.winrate_pct)}%` : '—'}</td>
									<td class="ka {r.mean_r != null && r.mean_r > 0 ? 'pos' : r.mean_r != null && r.mean_r < 0 ? 'neg' : ''}">
										{r.mean_r != null ? `${r.mean_r > 0 ? '+' : ''}${angka(r.mean_r)}` : '—'}
									</td>
									<td class="ka">
										{#if r.total_r != null}<span class={r.total_r > 0 ? 'pos' : r.total_r < 0 ? 'neg' : ''}>{r.total_r > 0 ? '+' : ''}{angka(r.total_r)} R</span>{/if}
										{#if r.pnl_usd != null}<span class={r.pnl_usd > 0 ? 'pos' : r.pnl_usd < 0 ? 'neg' : ''}>{r.pnl_usd > 0 ? '+' : ''}{angka(r.pnl_usd)} USD</span>{/if}
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
		</details>
		</section>

		<!-- 3. SINYAL PER MARKET (revisi pemilik 7 Okt).
		     Format Seragam DEX Confluence Alert (Threads):
		       - Identitas Aset & Chain / Venue & Waktu
		       - Badge Verdikt Autotrade Seketika (OKE / PANTAU / SKIP)
		       - 3 Poin Konfluensi Pemicu
		       - Bento 4 Metrik Inti
		       - Alasan Eksekusi / Catatan Keputusan -->
		<section class="pasar" aria-label="Sinyal per market">
			<div class="judul-bagian">
				<h2>Sinyal per Market</h2>
				<p class="dim">
					Format seragam DEX Confluence Alert: verdikt autotrade seketika, konfluensi pemicu,
					dan metrik terukur per pasar.
				</p>
			</div>
			<div class="sinyal-grid">
				{#each pasarDaftar as p (p.pasar)}
					{@const jujur = kartuJujur(p)}
					<article class="sinyal-kartu {p.status_data}">
						<header class="sinyal-kepala">
							<div class="sinyal-baris-atas">
								<h3>{p.label}</h3>
								{#if p.jumlah > MAKS_PER_MARKET}
									<a class="lihat-semua" href={p.rute}>Lihat semua ({p.jumlah}) →</a>
								{:else if p.status_data === 'ada'}
									<a class="lihat-semua" href={p.rute}>Buka {p.label.split(' (')[0]} →</a>
								{/if}
							</div>
							<div class="sinyal-badges">
								{#if p.mode}
									<span class="mode-badge mode-{p.mode.toLowerCase()}" title={p.catatan_mode ?? ''}>{p.mode}</span>
								{/if}
								<!-- honesty-tag motif baru: TERUKUR solid / BELUM TERVERIFIKASI dashed -->
								<HonestyTag terverifikasi={jujur.terverifikasi} sumber={p.sumber} alasan={p.alasan_eksekusi ?? null} />
								{#if p.autotrade_verdict}
									<span class="badge-autotrade {p.autotrade_verdict.toLowerCase()}">
										{#if p.autotrade_verdict === 'OKE'}
											● OKE AUTOTRADE
										{:else if p.autotrade_verdict === 'PANTAU'}
											● PANTAU / KANDIDAT
										{:else}
											● SKIP / TOLAK
										{/if}
									</span>
								{/if}
							</div>
						</header>

						{#if p.sumber}
							<p class="sinyal-sumber">
								sumber: {p.sumber}{#if jujur.umur_s != null} · sinyal {umurDetik(jujur.umur_s)} lalu{/if}
							</p>
						{:else if jujur.umur_s != null}
							<p class="sinyal-sumber">
								sinyal {umurDetik(jujur.umur_s)} lalu
							</p>
						{/if}
						{#if jujur.dibuat}
							<p class="sinyal-waktu angka">dibuat {waktuWIB(jujur.dibuat)}</p>
						{/if}

						{#if p.status_data === 'ada'}
							{#if p.sinyal[0]?.pair}
								<div class="lead-pair-baris">
									<span class="lead-pair angka">{p.sinyal[0].pair}</span>
									{#if p.sinyal[0].arah}
										<span class="lead-arah {p.sinyal[0].arah === 'LONG' || p.sinyal[0].arah === 'BELI' ? 'pos' : 'neg'}">{p.sinyal[0].arah}</span>
									{/if}
									{#if p.sinyal[0].tier}
										<span class="lead-tier">{p.sinyal[0].tier}</span>
									{/if}
									{#if p.sinyal[0].skor != null}
										<span class="lead-skor angka">{p.sinyal[0].skor}<span class="dari">/100</span></span>
									{/if}
								</div>
							{/if}

							<!-- Track bar (pola warisan .bar, kini komponen): skor vs 100. -->
							{#if p.sinyal[0]?.skor != null}
								<TrackBar
									label="SKOR VALIDASI"
									nilai={p.sinyal[0].skor}
									ambang={75}
									nada={p.sinyal[0].skor >= 75 ? 'terkukur' : 'netral'}
									teksAmbang={p.sinyal[0].skor >= 75 ? `AMBANG: 75` : 'AMBANG: 75 (DI BAWAH)'}
								/>
							{/if}

							<!-- 3 Poin Konfluensi Pemicu -->
							{#if p.confluence && p.confluence.length}
								<div class="card-confluence">
									<span class="section-label">Konfluensi Pemicu</span>
									<div class="confluence-items">
										{#each p.confluence as item}
											<div class="confluence-pill">{item}</div>
										{/each}
									</div>
								</div>
							{/if}

							<!-- Bento 4 Metrik Inti -->
							{#if p.metrics && Object.keys(p.metrics).length}
								<div class="card-bento">
									{#each Object.entries(p.metrics) as [label, val]}
										<div class="bento-cell">
											<span class="bento-lbl">{label}</span>
											<span class="bento-val angka">{val}</span>
										</div>
									{/each}
								</div>
							{/if}

							<!-- Alasan Eksekusi -->
							{#if p.alasan_eksekusi}
								<p class="card-alasan">
									<span class="dim">Eksekusi:</span> <b>{p.alasan_eksekusi}</b>
								</p>
							{/if}

							<!-- Catatan kejujuran ringkas — selalu di kartu (bukan hanya <details> audit).
							     Teks penuh tetap ada di lipatan "Catatan & skor per pasar". -->
							{#if jujur.catatan}
								<p class="card-jujur" title={jujur.catatan}>{ringkasCatatan(jujur.catatan)}</p>
							{/if}

							<!-- Kandidat lain bila ada lebih dari 1 -->
							{#if p.sinyal.length > 1}
								<div class="kandidat-sekunder">
									<span class="section-label">Kandidat Lain ({p.sinyal.length - 1})</span>
									{#each p.sinyal.slice(1, MAKS_PER_MARKET) as s, idx (s.pair ?? idx)}
										<div class="sinyal-baris-mini">
											<div class="sinyal-kiri">
												<span class="sinyal-pair angka">{s.pair ?? '—'}</span>
												{#if s.arah}<span class="sinyal-arah {s.arah === 'LONG' || s.arah === 'BELI' ? 'pos' : 'neg'}">{s.arah}</span>{/if}
												{#if s.tier}<span class="sinyal-tier">{s.tier}</span>{/if}
											</div>
											<div class="sinyal-kanan angka dim">
												{#if s.entry != null}<span>e {formatHarga(typeof s.entry === 'number' ? s.entry : Number(s.entry))}</span>{/if}
												{#if s.sl != null}<span>s {formatHarga(typeof s.sl === 'number' ? s.sl : Number(s.sl))}</span>{/if}
												{#if s.tp1 != null}<span>t {formatHarga(typeof s.tp1 === 'number' ? s.tp1 : Number(s.tp1))}</span>{/if}
												{#if s.autotrade_verdict}
													<span class="badge-mini {s.autotrade_verdict === 'OKE' ? 'pos' : 'warn'}">{s.autotrade_verdict}</span>
												{/if}
											</div>
										</div>
									{/each}
								</div>
							{/if}
						{:else if p.status_data === 'kosong'}
							<p class="sinyal-kosong">Tidak ada sinyal. {p.alasan}</p>
							{#if p.alasan_eksekusi}
								<p class="card-alasan dim">{p.alasan_eksekusi}</p>
							{/if}
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

		<!-- 4. STATUS per pasar — LAPISAN AUDIT (audit QA putaran 4, prioritas 4:
		     "kurangi density, progressive disclosure"). Daftar sinyalnya sudah ada di
		     bagian 3; di sini hanya catatan kejujuran per pasar. Karena isinya panjang
		     tetapi jarang dibutuhkan saat memindai, bagian ini TERLIPAT secara default —
		     kepala tetap terlihat sehingga pembaca tahu ada apa di dalamnya. -->
		<details class="pasar lipat-status">
			<summary>
				<span class="ringkas-judul">Catatan &amp; skor per pasar</span>
				<span class="dim angka">{daftar.length} pasar</span>
				<span class="petunjuk">buka untuk audit</span>
			</summary>
			<div class="isi-lipat">
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
						{#if s.terverifikasi === true}
							<span class="tanda ada">✓ TERVERIFIKASI</span>
						{:else if s.terverifikasi === false}
							<span class="tanda belum">○ BELUM TERVERIFIKASI</span>
						{/if}
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
			</div>
		</details>

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
		/* Tema 16 Okt: amber = aksen fokus; mint = nilai positif TERUKUR. Nama lama
		   dipertahankan agar diff halaman tetap kecil. */
		--mint: var(--color-pos);
		--amber: var(--color-accent);
		--kuning: var(--color-accent);
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
		border: 1px solid var(--garis); border-radius: var(--radius-track);
		padding: 0.2rem 0.65rem; font-size: 0.75rem; text-decoration: none;
		background: var(--permukaan); color: var(--tinta);
	}
	.peluang-chip:hover { border-color: var(--mint); }
	.chip-nama { color: var(--redup); }
	.chip-subjek { font-weight: 700; }
	.chip-arah { color: var(--mint); font-weight: 700; font-size: 0.68rem; }
	.tanda-biaya {
		margin-left: 0.3rem; font-size: 0.6rem; font-weight: 700; letter-spacing: 0.04em;
		border: 1px solid var(--kuning); color: var(--kuning); border-radius: var(--radius-card);
		padding: 0 0.25rem; vertical-align: middle;
	}
	.pakem-legend { display: flex; flex-wrap: wrap; gap: 0.35rem; align-items: center; margin-top: 0.5rem; font-size: 0.7rem; }
	.pakem-legend .pisah { color: var(--redup); }

	.judul-bagian { margin: 0.5rem 0 0.75rem; }
	.judul-bagian h2 { font-size: 1.05rem; margin: 0 0 0.15rem; letter-spacing: 0.01em; }
	.tabel-wrap { overflow-x: auto; border: 1px solid var(--garis); border-radius: var(--radius-card); background: var(--permukaan); }
	.tabel-pasar { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
	.tabel-pasar th { text-align: left; font-weight: 500; color: var(--redup); padding: 0.6rem 0.75rem; border-bottom: 1px solid var(--garis); white-space: nowrap; }
	.tabel-pasar td { padding: 0.55rem 0.75rem; border-bottom: 1px solid var(--garis); vertical-align: top; }
	.tabel-pasar tr:last-child td { border-bottom: none; }
	.tabel-pasar .ka { text-align: right; }
	.tabel-pasar .nama-pasar { text-transform: capitalize; font-weight: 600; }
	.tabel-pasar tr.kosong { opacity: 0.75; }
	.catatan-alasan { font-size: 0.75rem; padding-top: 0 !important; }
	.kaki-tabel { margin-top: 0.5rem; font-size: 0.72rem; }
	.pakem { display: inline-block; padding: 0.1rem 0.45rem; border-radius: var(--radius-card); border: 1px solid var(--garis); font-size: 0.68rem; font-weight: 700; letter-spacing: 0.02em; }
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
		padding: 0.6rem 0;
		border-bottom: 1px solid var(--garis);
		/* FLAT: gradient latar dihapus (design 16 Okt). */
		/* 29 Okt: tanpa overflow-hidden, jalur marquee (1768px) melebarkan
		   dokumen sampai 1784px dan halaman bisa digeser ke samping di ponsel. */
		overflow: hidden;
		max-width: 100%;
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
	/* Gaya lipatan bersama (details/summary) — dipakai lipat-status & lipat-akurasi. */
	.lipat-akurasi { border-top: 1px solid var(--garis); }
	.lipat-akurasi > summary {
		display: flex; align-items: center; gap: 0.6rem; flex-wrap: wrap;
		min-height: 44px; padding: 0.5rem 0.85rem; cursor: pointer; list-style: none;
	}
	.lipat-akurasi > summary::-webkit-details-marker { display: none; }
	.lipat-akurasi > summary::after { content: '▾'; margin-left: auto; color: var(--redup); }
	.lipat-akurasi[open] > summary::after { content: '▴'; }
	.lipat-akurasi .ringkas-judul { font-size: 0.95rem; font-weight: 600; }
	.lipat-akurasi .petunjuk { font-size: 0.68rem; color: var(--redup); }
	.lipat-akurasi .isi-lipat { padding: 0 0.85rem 0.75rem; }

	.lipat-status {
		border: 1px solid var(--garis); border-radius: var(--radius-card); background: var(--permukaan);
		padding: 0;
	}
	.lipat-status > summary {
		display: flex; align-items: center; gap: 0.6rem;
		min-height: 44px; padding: 0.5rem 0.85rem; cursor: pointer; list-style: none;
	}
	.lipat-status > summary::-webkit-details-marker { display: none; }
	.lipat-status > summary::after { content: '▾'; margin-left: auto; color: var(--redup); }
	.lipat-status[open] > summary::after { content: '▴'; }
	.lipat-status .ringkas-judul { font-size: 0.9rem; font-weight: 600; }
	.lipat-status .petunjuk { font-size: 0.68rem; color: var(--redup); }
	.lipat-status .isi-lipat { padding: 0 0.85rem 0.75rem; border-top: 1px solid var(--garis); }

	.kartu-gabung {
		border: 1px solid var(--garis);
		border-radius: var(--radius-card);
		background: var(--permukaan);
		overflow: hidden;
	}
	.akurasi-dalam { border-top: 1px solid var(--garis); padding: 1rem; margin: 0; }
	.verdikt { border-radius: 0; border: none; }

	/* Sinyal per market */
	.sinyal-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(20rem, 1fr)); gap: 0.85rem; }
	.sinyal-kartu {
		border: 1px solid var(--garis); border-radius: var(--radius-card);
		background: var(--permukaan); padding: 0.85rem 1rem;
		transition: border-color 160ms var(--ease-out), box-shadow 160ms var(--ease-out);
	}
	.sinyal-kartu:hover {
		border-color: color-mix(in srgb, var(--amber) 35%, var(--garis));
	}
	.sinyal-kartu.gagal { border-color: var(--merah); }
	.sinyal-kepala { display: flex; flex-direction: column; gap: 0.35rem; margin-bottom: 0.45rem; }
	.sinyal-baris-atas { display: flex; align-items: center; justify-content: space-between; gap: 0.5rem; }
	.sinyal-baris-atas h3 { font-size: 0.88rem; font-weight: 700; margin: 0; letter-spacing: 0.01em; }
	.sinyal-badges { display: flex; align-items: center; gap: 0.4rem; flex-wrap: wrap; }
	.mode-badge {
		font-size: 0.6rem; font-weight: 700; letter-spacing: 0.06em;
		border: 1px solid var(--garis); border-radius: var(--radius-card); padding: 0.05rem 0.3rem;
		color: var(--redup);
	}
	.mode-badge.mode-paper { color: var(--kuning); border-color: var(--kuning); background: color-mix(in srgb, var(--kuning) 8%, transparent); }
	.mode-badge.mode-historis { color: var(--redup); border-style: dashed; }
	.mode-badge.mode-live { color: var(--mint); border-color: var(--mint); background: color-mix(in srgb, var(--mint) 8%, transparent); }
	.verif-badge {
		font-size: 0.6rem; font-weight: 700; letter-spacing: 0.06em;
		border: 1px solid var(--garis); border-radius: var(--radius-card); padding: 0.05rem 0.3rem;
		white-space: nowrap;
	}
	.verif-badge.verif-ok { color: var(--mint); border-color: var(--mint); background: color-mix(in srgb, var(--mint) 8%, transparent); }
	.verif-badge.verif-belum { color: var(--kuning); border-color: var(--kuning); background: color-mix(in srgb, var(--kuning) 8%, transparent); }
	.sinyal-waktu { font-size: 0.66rem; color: var(--redup); margin: 0 0 0.35rem; }
	.card-jujur {
		font-size: 0.72rem; color: var(--redup); margin: 0.4rem 0 0; line-height: 1.4;
		border-left: 2px solid var(--garis); padding-left: 0.5rem;
	}
	.sinyal-sumber { font-size: 0.66rem; color: var(--redup); margin: 0 0 0.35rem; }
	.lihat-semua {
		font-size: 0.7rem; color: var(--mint); text-decoration: none; white-space: nowrap;
		/* Target sentuh ≥44 px (audit QA 7 Okt). Teks tetap kecil; area klik dibesarkan
		   dengan padding vertikal + inline-flex supaya tidak mengubah tata letak baris. */
		display: inline-flex; align-items: center; min-height: 44px; padding: 0 0.25rem;
	}
	.lihat-semua:hover { text-decoration: underline; }
	.sinyal-baris { display: flex; justify-content: space-between; gap: 0.5rem; padding: 0.3rem 0; border-top: 1px dashed var(--garis); align-items: baseline; }
	.sinyal-baris:first-of-type { border-top: none; }
	.sinyal-kiri { display: inline-flex; align-items: baseline; gap: 0.4rem; }
	.sinyal-pair { font-weight: 700; font-size: 0.82rem; }
	.sinyal-arah { font-weight: 700; font-size: 0.68rem; letter-spacing: 0.03em; }
	.sinyal-tier { font-size: 0.62rem; color: var(--redup); border: 1px solid var(--garis); border-radius: var(--radius-card); padding: 0 0.3rem; }
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
		border: 1px solid var(--garis); border-radius: var(--radius-track); padding: 0.15rem 0.6rem;
		font-size: 0.7rem; background: var(--permukaan);
	}
	.sumber-pasar { color: var(--redup); }
	.sumber-nama { font-weight: 600; color: var(--tinta); }
	/* Dompet paper $20 (15 Okt) — strip dengan chip yang lebih besar dari sumber data
	   supaya hierarki jelas: dompet = angka yang owner pantau, sumber = metadata. */
	.dompet20-strip {
		display: flex; flex-wrap: wrap; gap: 0.5rem; align-items: center;
		border: 1px solid color-mix(in srgb, var(--mint) 28%, var(--garis));
		border-radius: var(--radius-card);
		padding: 0.45rem 0.7rem; background: var(--permukaan);
	}
	.dompet-grid { display: flex; flex-wrap: wrap; gap: 0.5rem; flex: 1; }
	.dompet-chip {
		display: inline-flex; flex-direction: column; gap: 0.1rem;
		border: 1px solid var(--garis); border-radius: var(--radius-card); padding: 0.3rem 0.65rem;
		background: var(--latar);
		transition: border-color 160ms var(--ease-out), background 160ms var(--ease-out);
	}
	.dompet-chip:hover {
		border-color: color-mix(in srgb, var(--mint) 40%, var(--garis));
		/* FLAT */
	}
	.dompet-chip .angka { font-size: 0.8rem; font-family: var(--font-mono); color: var(--mint); }
	.dompet-chip a { color: var(--accent); }
	.sumber-chip {
		transition: border-color 160ms var(--ease-out);
	}
	.sumber-chip:hover { border-color: color-mix(in srgb, var(--mint) 30%, var(--garis)); }
	
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
		color: var(--amber);
	}
	.mode {
		font-size: 0.7rem;
		font-weight: 700;
		letter-spacing: 0.1em;
		padding: 0.15rem 0.5rem;
		border: 1px solid var(--mint);
		color: var(--mint);
		border-radius: var(--radius-track);
	}
	.spacer {
		flex: 1;
	}

	/* Verdikt: satu blok besar, ini jawaban 3 detik. */
	.verdikt {
		border: 1px solid var(--garis);
		border-radius: var(--radius-card);
		padding: 1.5rem 1.5rem 1.35rem;
		background: var(--permukaan);
		position: relative;
		transition: border-color 160ms var(--ease-out), box-shadow 160ms var(--ease-out);
	}
	.verdikt:hover {
		border-color: color-mix(in srgb, var(--amber) 50%, var(--garis));
	}
	.verdikt.ada {
		/* Pita keputusan fokus: border amber solid, latar FLAT (mockup home). */
		border-color: var(--amber);
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
		border-radius: var(--radius-card);
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
		border-radius: var(--radius-track);
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

	/* Setup entry — blok "masuk di mana" dengan format konfluensi terpadu. */
	.setup {
		margin-top: 1.1rem;
		padding-top: 1rem;
		border-top: 1px solid var(--garis);
	}
	.setup-kepala {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.75rem;
		margin-bottom: 0.75rem;
		flex-wrap: wrap;
	}
	.setup-judul {
		font-size: 0.75rem;
		font-weight: 700;
		letter-spacing: 0.12em;
		text-transform: uppercase;
		color: var(--redup);
	}
	.badge-verdict, .badge-autotrade {
		font-size: 0.65rem;
		font-weight: 700;
		letter-spacing: 0.05em;
		padding: 0.15rem 0.55rem;
		border-radius: var(--radius-track);
		border: 1px solid;
		white-space: nowrap;
	}
	.badge-verdict.oke, .badge-autotrade.oke {
		color: var(--mint);
		border-color: color-mix(in srgb, var(--mint) 45%, transparent);
		background: color-mix(in srgb, var(--mint) 12%, transparent);
	}
	.badge-verdict.pantau, .badge-autotrade.pantau {
		color: var(--kuning);
		border-color: color-mix(in srgb, var(--kuning) 45%, transparent);
		background: color-mix(in srgb, var(--kuning) 12%, transparent);
	}
	.badge-verdict.skip, .badge-autotrade.skip {
		color: var(--merah);
		border-color: color-mix(in srgb, var(--merah) 45%, transparent);
		background: color-mix(in srgb, var(--merah) 12%, transparent);
	}

	.section-label {
		display: block;
		font-size: 0.62rem;
		font-weight: 700;
		letter-spacing: 0.1em;
		text-transform: uppercase;
		color: var(--redup);
		margin-bottom: 0.35rem;
	}
	.setup-confluence {
		margin-bottom: 0.75rem;
	}
	.confluence-grid, .confluence-items {
		display: flex;
		flex-direction: column;
		gap: 0.3rem;
	}
	.confluence-pill {
		font-size: 0.74rem;
		color: var(--tinta);
		padding: 0.3rem 0.6rem;
		background: color-mix(in srgb, var(--latar) 65%, var(--permukaan));
		border: 1px solid var(--garis);
		border-radius: var(--radius-card);
		line-height: 1.35;
	}

	.setup-bento {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(7.5rem, 1fr));
		gap: 0.5rem;
		margin-bottom: 0.75rem;
	}
	.bento-box {
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
		padding: 0.5rem 0.7rem;
		background: color-mix(in srgb, var(--latar) 60%, var(--permukaan));
		border: 1px solid var(--garis);
		border-radius: var(--radius-card);
	}
	.bento-lbl {
		font-size: 0.62rem;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--redup);
	}
	.bento-val {
		font-size: 1.05rem;
		font-weight: 700;
		color: var(--tinta);
	}
	.setup-alasan {
		font-size: 0.8rem;
		color: var(--tinta);
		margin: 0.5rem 0 0;
		line-height: 1.4;
	}

	/* Card Sinyal per Market Elements */
	.lead-pair-baris {
		display: flex;
		align-items: baseline;
		gap: 0.5rem;
		margin: 0.35rem 0 0.5rem;
	}
	.lead-pair {
		font-size: 1.05rem;
		font-weight: 700;
		color: var(--tinta);
		letter-spacing: 0.01em;
	}
	.lead-arah {
		font-size: 0.72rem;
		font-weight: 700;
		padding: 0.05rem 0.35rem;
		border-radius: var(--radius-card);
	}
	.lead-tier {
		font-size: 0.65rem;
		color: var(--redup);
		border: 1px solid var(--garis);
		padding: 0 0.3rem;
		border-radius: var(--radius-card);
	}
	.lead-skor {
		font-size: 0.85rem;
		font-weight: 700;
		margin-left: auto;
		color: var(--tinta);
	}
	.card-confluence {
		margin: 0.5rem 0 0.6rem;
	}
	.card-bento {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(5.2rem, 1fr));
		gap: 0.4rem;
		margin: 0.5rem 0;
	}
	.bento-cell {
		display: flex;
		flex-direction: column;
		gap: 0.1rem;
		padding: 0.35rem 0.5rem;
		background: color-mix(in srgb, var(--latar) 55%, var(--permukaan));
		border: 1px solid var(--garis);
		border-radius: var(--radius-card);
	}
	.card-alasan {
		font-size: 0.72rem;
		color: var(--tinta);
		margin: 0.4rem 0 0;
		line-height: 1.35;
	}
	.kandidat-sekunder {
		margin-top: 0.65rem;
		padding-top: 0.5rem;
		border-top: 1px dashed var(--garis);
	}
	.sinyal-baris-mini {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		gap: 0.4rem;
		padding: 0.25rem 0;
		font-size: 0.72rem;
	}
	.badge-mini {
		font-size: 0.58rem;
		font-weight: 700;
		padding: 0.05rem 0.25rem;
		border-radius: var(--radius-card);
	}
	.badge-mini.pos {
		color: var(--mint);
		background: color-mix(in srgb, var(--mint) 12%, transparent);
	}
	.badge-mini.warn {
		color: var(--kuning);
		background: color-mix(in srgb, var(--kuning) 12%, transparent);
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
