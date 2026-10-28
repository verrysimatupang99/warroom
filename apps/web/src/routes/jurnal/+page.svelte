<script lang="ts">
	// Jurnal forex — dibangun dari data lokal: telemetri MT5 (facts kind=mt5_snapshot)
	// dan fills.csv. Tidak ada angka karangan: blok yang sumbernya kosong menampilkan
	// alasan, bukan nol.
	import { urlApi } from '$lib/api/client';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import Skeleton from '$lib/components/Skeleton.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';

	type Angka = number | null;

	interface Stats {
		sumber?: string;
		akun?: string | number | null;
		saldo?: Angka;
		ekuitas?: Angka;
		pnl_hari_ini_usd?: Angka;
		trade_hari_ini?: Angka;
		menang?: Angka;
		kalah?: Angka;
		win_rate_hari_ini_pct?: Angka;
		posisi_terbuka?: Angka;
		n_fill_tercatat?: Angka;
		terakhir_terlihat?: string | null;
	}
	interface Sesi {
		spread_pts?: Angka;
		bid?: Angka;
		ask?: Angka;
		ekuitas?: Angka;
		terakhir_terlihat?: string | null;
	}
	interface Kinerja {
		n_titik?: number;
		ekuitas_awal?: Angka;
		ekuitas_akhir?: Angka;
		puncak?: Angka;
		perubahan_pct?: Angka;
		deret?: { t: string; equity: Angka }[];
	}
	interface Trade {
		iso?: string;
		symbol?: string;
		side?: string;
		volume?: string;
		price_filled?: string;
		slippage_pts?: string;
		latency_ms?: string;
	}
	interface Edge {
		per_jam?: Record<string, { n: number; slip_rata_pts: number; slip_terburuk_pts: number }>;
		latensi_rata_ms?: Angka;
		n?: number;
	}

	let stats = $state<Stats | null>(null);
	let sesi = $state<Sesi | null>(null);
	let kinerja = $state<Kinerja | null>(null);
	let trades = $state<Trade[]>([]);
	let edge = $state<Edge | null>(null);
	let galat = $state<Record<string, string>>({});
	let memuat = $state(true);

	async function ambil<T>(jalur: string): Promise<T | null> {
		try {
			const r = await fetch(urlApi(jalur), { credentials: 'include' });
			const isi = await r.json().catch(() => null);
			if (!r.ok) {
				const pesan =
					(isi && (isi?.error?.message || isi?.detail?.message || isi?.detail)) ??
					`HTTP ${r.status}`;
				galat[jalur] = typeof pesan === 'string' ? pesan : `HTTP ${r.status}`;
				galat = { ...galat };
				return null;
			}
			delete galat[jalur];
			galat = { ...galat };
			return isi as T;
		} catch (e) {
			galat[jalur] = e instanceof Error ? e.message : 'gagal menghubungi API';
			galat = { ...galat };
			return null;
		}
	}

	async function muat() {
		memuat = true;
		const [s, se, k, t, e] = await Promise.all([
			ambil<Stats>('/api/v1/journal/stats'),
			ambil<Sesi>('/api/v1/journal/session'),
			ambil<Kinerja>('/api/v1/journal/performance'),
			ambil<{ closed?: Trade[] }>('/api/v1/journal/trades'),
			ambil<Edge>('/api/v1/journal/edge')
		]);
		stats = s;
		sesi = se;
		kinerja = k;
		trades = t?.closed ?? [];
		edge = e;
		memuat = false;
	}

	$effect(() => {
		void muat();
	});

	function rp(v: Angka | undefined): string {
		if (v === null || v === undefined) return '—';
		return `$${v.toFixed(2)}`;
	}
	function angka(v: Angka | undefined, satuan = ''): string {
		if (v === null || v === undefined) return '—';
		return `${v}${satuan}`;
	}
	function pesanKosong(jalur: string, cadangan: string): string {
		return galat[jalur] ?? cadangan;
	}
</script>

<div class="space-y-5">
	<PageHeader
		eyebrow="War Room · Jurnal"
		title="Jurnal Forex"
		tag="LOKAL"
		description="Rekaman eksekusi dan ekuitas EA MT5, dibangun dari telemetri yang disimpan tiap menit dan catatan fill. Data jurnal lama di node luar tidak dipulihkan; rekaman dimulai dari nol."
		terverifikasi={true}
		sumber={stats?.sumber ?? 'lokal:mt5'}
	/>

	{#if memuat}
		<Skeleton baris={4} tinggi={48} />
	{:else}
		<!-- Ringkasan akun -->
		<section class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
			<div class="rounded-card border border-line bg-surface p-4">
				<div class="label-mikro text-text-3 font-mono">AKUN</div>
				<div class="mt-1 text-18 font-bold text-text font-mono">{stats?.akun ?? '—'}</div>
				<div class="mt-1 text-11 text-text-3">
					{stats?.terakhir_terlihat ? `terlihat ${stats.terakhir_terlihat.slice(0, 19)}` : 'belum ada telemetri'}
				</div>
			</div>
			<div class="rounded-card border border-line bg-surface p-4">
				<div class="label-mikro text-text-3 font-mono">EKUITAS</div>
				<div class="mt-1 text-18 font-bold text-text font-mono">{rp(stats?.ekuitas)}</div>
				<div class="mt-1 text-11 text-text-3">saldo {rp(stats?.saldo)}</div>
			</div>
			<div class="rounded-card border border-line bg-surface p-4">
				<div class="label-mikro text-text-3 font-mono">PnL HARI INI</div>
				<div
					class="mt-1 text-18 font-bold font-mono"
					class:text-pos={((stats?.pnl_hari_ini_usd as number) ?? 0) > 0}
					class:text-neg={((stats?.pnl_hari_ini_usd as number) ?? 0) < 0}
				>
					{rp(stats?.pnl_hari_ini_usd)}
				</div>
				<div class="mt-1 text-11 text-text-3">
					{angka(stats?.trade_hari_ini)} trade · W {angka(stats?.menang)} / L {angka(stats?.kalah)}
				</div>
			</div>
			<div class="rounded-card border border-line bg-surface p-4">
				<div class="label-mikro text-text-3 font-mono">POSISI</div>
				<div class="mt-1 text-18 font-bold text-text font-mono">{angka(stats?.posisi_terbuka)}</div>
				<div class="mt-1 text-11 text-text-3">fill tercatat {angka(stats?.n_fill_tercatat)}</div>
			</div>
		</section>

		<!-- Sesi & kinerja -->
		<section class="grid gap-3 lg:grid-cols-2">
			<div class="rounded-card border border-line bg-surface p-4">
				<h2 class="text-13 font-bold text-text">Kondisi sesi</h2>
				{#if sesi}
					<dl class="mt-2 grid grid-cols-2 gap-2 text-12">
						<dt class="text-text-3">Spread</dt>
						<dd class="text-right font-mono text-text">{angka(sesi.spread_pts, ' pts')}</dd>
						<dt class="text-text-3">Bid</dt>
						<dd class="text-right font-mono text-text">{angka(sesi.bid)}</dd>
						<dt class="text-text-3">Ask</dt>
						<dd class="text-right font-mono text-text">{angka(sesi.ask)}</dd>
					</dl>
				{:else}
					<EmptyState
						judul="Telemetri belum masuk"
						pesan={pesanKosong('/api/v1/journal/session', 'EA belum mengirim status sesi.')}
						ringkas={true}
						onulang={() => void muat()}
					/>
				{/if}
			</div>

			<div class="rounded-card border border-line bg-surface p-4">
				<h2 class="text-13 font-bold text-text">Kinerja</h2>
				{#if kinerja && (kinerja.n_titik ?? 0) > 0}
					<dl class="mt-2 grid grid-cols-2 gap-2 text-12">
						<dt class="text-text-3">Titik rekaman</dt>
						<dd class="text-right font-mono text-text">{kinerja.n_titik}</dd>
						<dt class="text-text-3">Ekuitas awal</dt>
						<dd class="text-right font-mono text-text">{rp(kinerja.ekuitas_awal)}</dd>
						<dt class="text-text-3">Ekuitas akhir</dt>
						<dd class="text-right font-mono text-text">{rp(kinerja.ekuitas_akhir)}</dd>
						<dt class="text-text-3">Puncak</dt>
						<dd class="text-right font-mono text-text">{rp(kinerja.puncak)}</dd>
						<dt class="text-text-3">Perubahan</dt>
						<dd class="text-right font-mono text-text">{angka(kinerja.perubahan_pct, ' %')}</dd>
					</dl>
					<p class="mt-2 text-11 text-text-3">
						Rekaman bertambah satu titik per menit selama EA aktif. Riwayat lama tidak
						tersedia karena sebelumnya hanya disimpan di memori.
					</p>
				{:else}
					<EmptyState
						judul="Belum ada riwayat ekuitas"
						pesan={pesanKosong('/api/v1/journal/performance', 'Rekaman dimulai saat EA mengirim telemetri.')}
						ringkas={true}
						onulang={() => void muat()}
					/>
				{/if}
			</div>
		</section>

		<!-- Tabel fill -->
		<section class="rounded-card border border-line bg-surface p-4">
			<div class="flex items-center justify-between gap-3">
				<h2 class="text-13 font-bold text-text">Catatan fill</h2>
				<span class="text-11 text-text-3 font-mono">{trades.length} baris</span>
			</div>
			{#if trades.length === 0}
				<EmptyState
					judul="Belum ada fill"
					pesan={pesanKosong(
						'/api/v1/journal/trades',
						'EA belum pernah melaporkan eksekusi. Slippage dan latensi baru bisa diukur setelah fill pertama masuk.'
					)}
					ringkas={true}
					onulang={() => void muat()}
				/>
			{:else}
				<div class="mt-2 overflow-x-auto">
					<table class="w-full text-11 text-left">
						<thead class="text-10 text-text-3 border-b border-line">
							<tr>
								<th class="py-1.5 px-2">Waktu</th>
								<th class="py-1.5 px-2">Simbol</th>
								<th class="py-1.5 px-2">Sisi</th>
								<th class="py-1.5 px-2 text-right">Volume</th>
								<th class="py-1.5 px-2 text-right">Terisi</th>
								<th class="py-1.5 px-2 text-right">Slip (pts)</th>
								<th class="py-1.5 px-2 text-right">Latensi (ms)</th>
							</tr>
						</thead>
						<tbody class="divide-y divide-line-soft">
							{#each trades.slice(0, 50) as t}
								<tr class="hover:bg-surface-2/60">
									<td class="py-1.5 px-2 text-text-3 font-mono">{t.iso}</td>
									<td class="py-1.5 px-2 text-text font-mono">{t.symbol}</td>
									<td class="py-1.5 px-2 text-text">{t.side}</td>
									<td class="py-1.5 px-2 text-right font-mono text-text">{t.volume}</td>
									<td class="py-1.5 px-2 text-right font-mono text-text">{t.price_filled}</td>
									<td class="py-1.5 px-2 text-right font-mono text-text">{t.slippage_pts}</td>
									<td class="py-1.5 px-2 text-right font-mono text-text-3">{t.latency_ms}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{/if}
		</section>

		<!-- Edge eksekusi -->
		<section class="rounded-card border border-line bg-surface p-4">
			<h2 class="text-13 font-bold text-text">Edge eksekusi (slippage per jam)</h2>
			{#if edge && edge.per_jam && Object.keys(edge.per_jam).length > 0}
				<div class="mt-2 grid gap-1 text-11 sm:grid-cols-2 lg:grid-cols-4">
					{#each Object.entries(edge.per_jam) as [jam, v]}
						<div class="flex items-center justify-between rounded border border-line px-2 py-1">
							<span class="font-mono text-text-3">{jam}:00</span>
							<span class="font-mono text-text">
								{v.slip_rata_pts} pts · n={v.n}
							</span>
						</div>
					{/each}
				</div>
				<p class="mt-2 text-11 text-text-3">
					Latensi rata-rata {angka(edge.latensi_rata_ms, ' ms')} dari {edge.n} fill.
				</p>
			{:else}
				<EmptyState
					judul="Edge belum bisa dihitung"
					pesan={pesanKosong(
						'/api/v1/journal/edge',
						'Butuh fill nyata. Angka nol akan menyesatkan, jadi blok ini dibiarkan kosong sampai ada eksekusi.'
					)}
					ringkas={true}
					onulang={() => void muat()}
				/>
			{/if}
		</section>
	{/if}
</div>
