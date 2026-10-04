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
	import { umurDetik, waktuWIB } from '$lib/format';
	import Block from '$lib/components/Block.svelte';
	import FreshnessBadge from '$lib/components/FreshnessBadge.svelte';

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
		for (const v of VENUE) {
			const dasar: Baris = { label: v.label, catatan: v.catatan, fakta: null, hasil: null, galat: null };
			try {
				const area: AreaPayload = await getArea(v.area);
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

<div class="space-y-3">
	<div>
		<h1 class="text-19 text-text">Bukti</h1>
		<p class="text-12 text-text-3">
			Apa yang benar-benar diukur — dan apa yang belum. Angka diambil dari fakta berpenyedia,
			bukan diketik tangan.
		</p>
	</div>

	<Block judul="Aturan halaman ini" deskripsi="kontrak kejujuran">
		<ul class="space-y-1 text-13">
			<li>
				Jika angka belum cukup, verdict ditulis apa adanya <span class="angka">belum cukup</span>
				— bukan dibulatkan jadi "menang".
			</li>
			<li>Setiap angka membawa sumber dan umurnya. Data hilang ditulis <span class="angka">—</span>, tidak pernah nol.</li>
			<li>Klien tidak menghitung ulang: gate dievaluasi di server, dengan kebijakan yang dilabeli.</li>
		</ul>
	</Block>

	<Block judul="Gate per venue" deskripsi="/api/v1/gate/evaluate — ci_low > break-even yang menentukan, bukan rata-rata" memuat={memuat && baris.length === 0}>
		{#if baris.length === 0}
			<p class="text-13 text-text-3">Belum ada yang bisa dinilai.</p>
		{:else}
			<div class="space-y-3">
				{#each baris as b (b.label)}
					<div class="rounded border border-line p-3">
						<div class="flex flex-wrap items-baseline gap-2">
							<span class="text-13 text-text">{b.label}</span>
							<span class="text-11 text-text-3">{b.catatan}</span>
							{#if b.hasil}
								<span class="angka {nadaVerdict(b.hasil.verdict)}">{b.hasil.verdict}</span>
								<span class="text-11 text-text-3">kebijakan {b.hasil.policy_version}{b.hasil.ci ? ` · CI ${b.hasil.ci}%` : ''}</span>
							{/if}
						</div>

						{#if b.galat}
							<p class="text-12 text-text-3">— {b.galat}</p>
						{:else if b.hasil}
							<div class="angka mt-2 grid gap-2 text-13 sm:grid-cols-3 lg:grid-cols-6">
								<p><span class="label-mikro block">n</span>{b.hasil.n}</p>
								<p><span class="label-mikro block">win rate</span>{(b.hasil.win_rate * 100).toFixed(2)}%</p>
								<p><span class="label-mikro block">break-even</span>{(b.hasil.be * 100).toFixed(2)}%</p>
								<p><span class="label-mikro block">ci bawah</span>{(b.hasil.ci_low * 100).toFixed(2)}%</p>
								<p><span class="label-mikro block">ci atas</span>{(b.hasil.ci_high * 100).toFixed(2)}%</p>
								<p>
									<span class="label-mikro block">n dibutuhkan</span>{b.hasil.required_n ?? '—'}
								</p>
							</div>
							<p class="mt-2 text-12 text-text-2">{b.hasil.reason}</p>
							{#if b.hasil.notes?.length}
								<ul class="mt-1 space-y-0.5 text-11 text-text-3">
									{#each b.hasil.notes as n (n)}
										<li>{n}</li>
									{/each}
								</ul>
							{/if}
							{#if b.fakta}
								<p class="mt-2 flex flex-wrap items-center gap-2 text-11 text-text-3">
									<span>sumber <span class="angka">{b.fakta.source}</span></span>
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

	<Block judul="Yang TIDAK kami klaim">
		<ul class="space-y-1 text-13">
			<li>Kami tidak mengklaim edge di pasar mana pun sampai interval kepercayaan bawah benar-benar di atas break-even.</li>
			<li>Kami tidak menampilkan persentase cuan dari kartu bagikan exchange: kartu itu tidak memuat harga masuk, harga keluar, nominal, atau order id — jadi tidak bisa diverifikasi.</li>
			<li>Kami tidak menyamakan <span class="angka">quote tersentuh</span> dengan <span class="angka">fill</span>, dan tidak menghitung PnL sebelum posisi benar-benar selesai.</li>
			<li>Angka hasil pencarian parameter dilabeli <span class="angka">eksplorasi</span>; promosi butuh sampel baru dengan split waktu yang dibekukan lebih dulu.</li>
			<li>IDX bersifat sinyal-saja: tidak ada auto-trade dari sekuritas mana pun, jadi tidak akan pernah ada klaim eksekusi di sana.</li>
		</ul>
	</Block>

	<Block judul="Yang akan mengubah verdict" deskripsi="syarat, bukan janji">
		<ul class="space-y-1 text-13">
			<li>Menambah sampel sampai <span class="angka">n</span> ≥ n yang dibutuhkan pada kebijakan yang sedang berlaku.</li>
			<li>Interval kepercayaan bawah bergerak jelas di atas break-even setelah koreksi klaster.</li>
			<li>Sampel baru dari periode yang belum pernah dilihat (holdout masa depan), bukan dari data yang sama.</li>
			<li>Ambang dan rumus break-even hanya boleh diubah oleh pemilik, tidak pernah oleh agen.</li>
		</ul>
	</Block>
</div>
