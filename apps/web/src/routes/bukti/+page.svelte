<script lang="ts">
	// Bukti — halaman kejujuran.
	//
	// Kebalikan dari halaman "track record" yang mengklaim: di sini ditampilkan angka mentah
	// yang benar-benar diukur, verdict gate apa adanya (termasuk kalau GAGAL / belum cukup),
	// sumber + umur setiap fakta, dan daftar eksplisit apa yang TIDAK kami klaim.
	//
	// Aturan: klien tidak menghitung ulang apa pun. Gate dievaluasi di server
	// (/api/v1/gate/evaluate); angka diambil dari `facts`, bukan dikarang di sini.
	import { getArea, nilaiGate } from '$lib/api/client';
	import type { AreaPayload, Fakta, HasilGate, MasukanGate } from '$lib/api/types';
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { AREAS } from '$lib/nav';
	import { umurDetik, waktuWIB } from '$lib/format';
	import Block from '$lib/components/Block.svelte';
	import SubNav from '$lib/components/SubNav.svelte';
	import FreshnessBadge from '$lib/components/FreshnessBadge.svelte';

	const areaBukti = AREAS.find((a) => a.kunci === 'bukti')!;
	let sub = $state(page.url.searchParams.get('sub') ?? 'evaluasi');

	$effect(() => {
		const s = page.url.searchParams.get('sub');
		if (s && areaBukti.anak.some((a) => a.slug === s)) {
			sub = s;
		}
	});

	function pilihSub(s: string) {
		sub = s;
		if (typeof window !== 'undefined') {
			void goto(`?sub=${s}`, { replaceState: true, keepFocus: true, noScroll: true });
		}
	}

	const VENUE: { area: string; label: string; catatan: string }[] = [
		{ area: 'polymarket', label: 'Polymarket', catatan: 'prediksi biner BTC/ETH jendela 5 menit' },
		{ area: 'crypto', label: 'Crypto', catatan: 'perpetual Binance/MEXC' },
		{ area: 'gmgn', label: 'GMGN', catatan: 'meme coin + LP' }
	];

	interface Baris {
		label: string;
		catatan: string;
		fakta: Fakta | null;
		hasil: HasilGate | null;
		galat: string | null;
	}

	let baris = $state<Baris[]>([]);
	let semuaFakta = $state<{ area: string; fakta: Fakta[] }[]>([]);
	let memuat = $state(true);

	/** Bentuk masukan gate dari fakta verdict/gate — sama persis dengan GateBlok: tidak menebak. */
	function masukanDari(fakta: Fakta[]): { m: MasukanGate; fakta: Fakta } | null {
		for (const f of fakta) {
			if (f.key !== 'verdict' && f.key !== 'gate') continue;
			const v = f.value as Record<string, unknown> | null;
			if (!v || typeof v !== 'object') continue;
			const n = Number(v.n);
			const win = Number(v.win ?? v.wins);
			const be = Number(v.be);
			if (!Number.isFinite(n) || !Number.isFinite(win) || !Number.isFinite(be)) continue;
			return {
				m: {
					n,
					win,
					be,
					ci: Number.isFinite(Number(v.ci)) ? Number(v.ci) : undefined,
					min_n: Number.isFinite(Number(v.min_n)) ? Number(v.min_n) : undefined,
					deff: Number.isFinite(Number(v.deff)) ? Number(v.deff) : undefined,
					split: typeof v.split === 'string' ? v.split : null,
					rule: typeof v.rule === 'string' ? v.rule : ''
				},
				fakta: f
			};
		}
		return null;
	}

	async function muat() {
		const hasil: Baris[] = [];
		const kumpulanFakta: { area: string; fakta: Fakta[] }[] = [];
		for (const v of VENUE) {
			const dasar: Baris = { label: v.label, catatan: v.catatan, fakta: null, hasil: null, galat: null };
			try {
				const area: AreaPayload = await getArea(v.area);
				kumpulanFakta.push({ area: v.label, fakta: area.facts ?? [] });
				const ketemu = masukanDari(area.facts ?? []);
				if (!ketemu) {
					dasar.galat = 'belum ada fakta verdict/gate yang memuat n, win, dan be';
				} else {
					dasar.fakta = ketemu.fakta;
					dasar.hasil = await nilaiGate(ketemu.m);
				}
			} catch (e) {
				dasar.galat = e instanceof Error ? e.message : String(e);
			}
			hasil.push(dasar);
		}
		baris = hasil;
		semuaFakta = kumpulanFakta;
		memuat = false;
	}

	$effect(() => {
		void muat();
		const t = setInterval(() => void muat(), 30000);
		return () => clearInterval(t);
	});

	function nadaVerdict(v: string | undefined): string {
		if (v === 'lolos') return 'text-up';
		if (v === 'gagal') return 'text-down';
		return 'text-text-2';
	}
</script>

<div class="space-y-4">
	<div class="border-b border-line pb-3">
		<div class="flex items-center gap-2">
			<h1 class="text-22 font-bold text-text font-display">Bukti &amp; Verifikasi Gate</h1>
			<span class="rounded bg-surface px-2 py-0.5 text-11 font-mono uppercase text-accent border border-line">
				RISK GATE (ADR-003)
			</span>
		</div>
		<p class="text-12 text-text-3 mt-1">
			Apa yang benar-benar diukur — dan apa yang belum. Angka diambil dari fakta berpenyedia,
			bukan diketik tangan. Tidak ada klaim sebelum interval kepercayaan bawah lolos batas break-even.
		</p>
	</div>

	<!-- Sub-navigasi Tabs -->
	<SubNav area={areaBukti} aktif={sub} onpilih={pilihSub} />

	{#if sub === 'evaluasi'}
		<Block judul="Evaluasi Gate per Venue" deskripsi="/api/v1/gate/evaluate — ci_low > break-even yang menentukan, bukan rata-rata" memuat={memuat && baris.length === 0}>
			{#if baris.length === 0}
				<p class="text-13 text-text-3">Belum ada yang bisa dinilai.</p>
			{:else}
				<div class="space-y-3">
					{#each baris as b (b.label)}
						<div class="rounded border border-line p-3">
							<div class="flex flex-wrap items-baseline gap-2">
								<span class="text-13 text-text font-bold">{b.label}</span>
								<span class="text-11 text-text-3">{b.catatan}</span>
								{#if b.hasil}
									<span class="angka font-bold {nadaVerdict(b.hasil.verdict)}">{b.hasil.verdict.toUpperCase()}</span>
									<span class="text-11 text-text-3">kebijakan {b.hasil.policy_version}{b.hasil.ci ? ` · CI ${b.hasil.ci}%` : ''}</span>
								{/if}
							</div>

							{#if b.galat}
								<p class="text-12 text-text-3 mt-2">— {b.galat}</p>
							{:else if b.hasil}
								<div class="angka mt-2 grid gap-2 text-13 sm:grid-cols-3 lg:grid-cols-6">
									<div class="rounded bg-surface p-2 border border-line">
										<span class="label-mikro block text-10 text-text-3">SAMPLE (N)</span>
										<span class="text-14 font-bold text-text">{b.hasil.n}</span>
									</div>
									<div class="rounded bg-surface p-2 border border-line">
										<span class="label-mikro block text-10 text-text-3">WIN RATE</span>
										<span class="text-14 font-bold text-text">{(b.hasil.win_rate * 100).toFixed(2)}%</span>
									</div>
									<div class="rounded bg-surface p-2 border border-line">
										<span class="label-mikro block text-10 text-text-3">BREAK-EVEN</span>
										<span class="text-14 font-bold text-text">{(b.hasil.be * 100).toFixed(2)}%</span>
									</div>
									<div class="rounded bg-surface p-2 border border-line">
										<span class="label-mikro block text-10 text-text-3">CI BAWAH</span>
										<span class="text-14 font-bold {b.hasil.ci_low > b.hasil.be ? 'text-pos' : 'text-neg'}">{(b.hasil.ci_low * 100).toFixed(2)}%</span>
									</div>
									<div class="rounded bg-surface p-2 border border-line">
										<span class="label-mikro block text-10 text-text-3">CI ATAS</span>
										<span class="text-14 font-bold text-text">{(b.hasil.ci_high * 100).toFixed(2)}%</span>
									</div>
									<div class="rounded bg-surface p-2 border border-line">
										<span class="label-mikro block text-10 text-text-3">N DIBUTUHKAN</span>
										<span class="text-14 font-bold text-text">{b.hasil.required_n ?? '—'}</span>
									</div>
								</div>
								<p class="mt-2 text-12 text-text-2">{b.hasil.reason}</p>
								{#if b.hasil.notes?.length}
									<ul class="mt-1 space-y-0.5 text-11 text-text-3">
										{#each b.hasil.notes as n (n)}
											<li>• {n}</li>
										{/each}
									</ul>
								{/if}
								{#if b.fakta}
									<p class="mt-2 flex flex-wrap items-center gap-2 text-11 text-text-3">
										<span>sumber <span class="angka font-mono">{b.fakta.source}</span></span>
										<span>· diambil {waktuWIB(b.fakta.observed_at)} ({umurDetik(b.fakta.age_s)})</span>
										<FreshnessBadge
											status={b.fakta.status}
											age_s={b.fakta.age_s}
											ttl_s={b.fakta.ttl_s}
											source={b.fakta.source}
										/>
									</p>
								{/if}
							{/if}
						</div>
					{/each}
				</div>
			{/if}
		</Block>

		<Block judul="Yang akan mengubah verdict" deskripsi="syarat, bukan janji">
			<ul class="space-y-1.5 text-13 text-text-2">
				<li>• Menambah sampel sampai <span class="angka font-mono text-accent">n</span> ≥ n yang dibutuhkan pada kebijakan yang sedang berlaku.</li>
				<li>• Interval kepercayaan bawah bergerak jelas di atas break-even setelah koreksi klaster.</li>
				<li>• Sampel baru dari periode yang belum pernah dilihat (holdout masa depan), bukan dari data yang sama.</li>
				<li>• Ambang dan rumus break-even hanya boleh diubah oleh pemilik, tidak pernah oleh agen.</li>
			</ul>
		</Block>
	{:else if sub === 'fakta'}
		<Block judul="Jejak Fakta Empiris &amp; Umur Data" deskripsi="Audit umur &amp; keaslian fakta yang dikonsumsi model verifikasi">
			{#if semuaFakta.length === 0}
				<p class="text-12 text-text-3">Memuat fakta venue...</p>
			{:else}
				<div class="space-y-4">
					{#each semuaFakta as v (v.area)}
						<div class="rounded-card border border-line bg-surface p-3">
							<div class="flex items-center justify-between mb-2 border-b border-line-soft pb-2">
								<h3 class="text-13 font-bold text-text">{v.area}</h3>
								<span class="text-11 font-mono text-text-3">{v.fakta.length} fakta terdaftar</span>
							</div>
							<div class="space-y-2">
								{#each v.fakta as f (f.key)}
									<div class="rounded border border-line bg-canvas p-2 text-11 flex flex-wrap items-center justify-between gap-2">
										<div>
											<span class="font-mono font-bold text-text mr-2">{f.key}</span>
											<span class="text-text-3">({f.kind})</span>
										</div>
										<div class="flex items-center gap-2 text-text-3">
											<span>{umurDetik(f.age_s)} lalu</span>
											<FreshnessBadge
												status={f.status}
												age_s={f.age_s}
												ttl_s={f.ttl_s}
												source={f.source}
											/>
										</div>
									</div>
								{/each}
							</div>
						</div>
					{/each}
				</div>
			{/if}
		</Block>
	{:else if sub === 'klaim'}
		<Block judul="Aturan Halaman Ini" deskripsi="kontrak kejujuran">
			<ul class="space-y-1.5 text-13 text-text-2">
				<li>• Jika angka belum cukup, verdict ditulis apa adanya <span class="angka text-warn font-semibold">belum cukup</span> — bukan dibulatkan jadi "menang".</li>
				<li>• Setiap angka membawa sumber dan umurnya. Data hilang ditulis <span class="angka font-mono text-text-3">—</span>, tidak pernah nol.</li>
				<li>• Klien tidak menghitung ulang: gate dievaluasi di server, dengan kebijakan yang dilabeli.</li>
			</ul>
		</Block>

		<Block judul="Yang TIDAK Kami Klaim" deskripsi="Batas integritas ADR-003">
			<ul class="space-y-2 text-13 text-text-2">
				<li>• <b>Tidak ada edge tanpa CI:</b> Kami tidak mengklaim edge di pasar mana pun sampai interval kepercayaan bawah benar-benar di atas break-even.</li>
				<li>• <b>Tanpa kartu pamer exchange:</b> Kami tidak menampilkan persentase cuan dari kartu bagikan exchange: kartu itu tidak memuat harga masuk, harga keluar, nominal, atau order id — jadi tidak bisa diverifikasi.</li>
				<li>• <b>Quote tersentuh ≠ Fill:</b> Kami tidak menyamakan <span class="angka font-mono">quote tersentuh</span> dengan <span class="angka font-mono">fill</span>, dan tidak menghitung PnL sebelum posisi benar-benar selesai.</li>
				<li>• <b>Pelabelan eksplorasi:</b> Angka hasil pencarian parameter dilabeli <span class="angka font-mono text-accent">eksplorasi</span>; promosi butuh sampel baru dengan split waktu yang dibekukan lebih dulu.</li>
				<li>• <b>IDX Sinyal-Saja:</b> IDX bersifat sinyal-saja: tidak ada auto-trade dari sekuritas mana pun, jadi tidak akan pernah ada klaim eksekusi di sana.</li>
			</ul>
		</Block>
	{/if}
</div>
