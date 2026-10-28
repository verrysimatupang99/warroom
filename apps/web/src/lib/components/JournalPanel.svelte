<script lang="ts">
	// Panel jurnal lintas market. Dipakai di tab Eksekusi tiap market dan di /jurnal.
	// Angka kosong selalu disertai alasan: tidak ada nol palsu.
	import { urlApi } from '$lib/api/client';
	import EmptyState from './EmptyState.svelte';
	import Skeleton from './Skeleton.svelte';

	interface Props {
		market?: 'all' | 'forex' | 'crypto';
		ringkas?: boolean;
	}
	let { market = 'all', ringkas = false }: Props = $props();

	type Angka = number | null;
	interface Stats {
		market?: string;
		akun?: string | number | null;
		saldo?: Angka;
		ekuitas?: Angka;
		pnl_hari_ini_usd?: Angka;
		win_rate_hari_ini_pct?: Angka;
		posisi_terbuka?: Angka;
		n_fill_forex?: Angka;
		n_fill_crypto?: Angka;
		crypto?: { aktif?: boolean; koin?: Angka; modal?: Angka; ekuitas?: Angka; return_pct?: Angka; posisi?: Angka; trade?: Angka };
		terakhir_terlihat?: string | null;
	}
	interface Trade {
		iso?: string; symbol?: string; side?: string; volume?: string;
		price_filled?: string; slippage_pts?: string; latency_ms?: string;
		market?: string; pnl_pct?: string;
	}
	interface Edge {
		per_jam?: Record<string, { n: number; slip_rata_pts: number }>;
		latensi_rata_ms?: Angka; n?: Angka;
	}
	interface Kinerja {
		n_titik?: number; ekuitas_awal?: Angka; ekuitas_akhir?: Angka;
		puncak?: Angka; perubahan_pct?: Angka;
	}

	let stats = $state<Stats | null>(null);
	let trades = $state<Trade[]>([]);
	let edge = $state<Edge | null>(null);
	let kinerja = $state<Kinerja | null>(null);
	let galat = $state<Record<string, string>>({});
	let memuat = $state(true);

	async function ambil<T>(jalur: string): Promise<T | null> {
		try {
			const r = await fetch(urlApi(`${jalur}?market=${market}`), { credentials: 'include' });
			const isi = await r.json().catch(() => null);
			if (!r.ok) {
				const p = isi?.error?.message ?? isi?.detail?.message ?? isi?.detail ?? `HTTP ${r.status}`;
				galat[jalur] = typeof p === 'string' ? p : `HTTP ${r.status}`;
				galat = { ...galat };
				return null;
			}
			return isi as T;
		} catch (e) {
			galat[jalur] = e instanceof Error ? e.message : 'gagal menghubungi API';
			galat = { ...galat };
			return null;
		}
	}

	async function muat() {
		memuat = true;
		const [s, t, e, k] = await Promise.all([
			ambil<Stats>('/api/v1/journal/stats'),
			ambil<{ closed?: Trade[] }>('/api/v1/journal/trades'),
			ambil<Edge>('/api/v1/journal/edge'),
			ambil<Kinerja>('/api/v1/journal/performance')
		]);
		stats = s;
		trades = t?.closed ?? [];
		edge = e;
		kinerja = k;
		memuat = false;
	}

	$effect(() => {
		void market;
		void muat();
	});

	function rp(v: Angka | undefined) {
		return v == null ? '—' : `$${v.toFixed(2)}`;
	}
	function alasan(jalur: string, cadangan: string) {
		return galat[jalur] ?? cadangan;
	}
</script>

{#if memuat}
	<Skeleton baris={3} tinggi={44} />
{:else}
	<div class="space-y-4">
		<section class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
			<div class="rounded-card border border-line bg-surface p-4">
				<div class="label-mikro text-text-3 font-mono">FOREX · EKUITAS</div>
				<div class="mt-1 text-17 font-bold font-mono text-text">{rp(stats?.ekuitas)}</div>
				<div class="mt-1 text-11 text-text-3">saldo {rp(stats?.saldo)}</div>
			</div>
			<div class="rounded-card border border-line bg-surface p-4">
				<div class="label-mikro text-text-3 font-mono">FOREX · PNL HARI INI</div>
				<div class="mt-1 text-17 font-bold font-mono text-text">{rp(stats?.pnl_hari_ini_usd)}</div>
				<div class="mt-1 text-11 text-text-3">fill {stats?.n_fill_forex ?? 0}</div>
			</div>
			<div class="rounded-card border border-line bg-surface p-4">
				<div class="label-mikro text-text-3 font-mono">CRYPTO · EKUITAS</div>
				<div class="mt-1 text-17 font-bold font-mono text-text">{rp(stats?.crypto?.ekuitas)}</div>
				<div class="mt-1 text-11 text-text-3">
					{stats?.crypto?.aktif ? `${stats.crypto.koin ?? 0} koin · ${stats.crypto.posisi ?? 0} posisi` : 'paper trader belum jalan'}
				</div>
			</div>
			<div class="rounded-card border border-line bg-surface p-4">
				<div class="label-mikro text-text-3 font-mono">CRYPTO · RETURN</div>
				<div class="mt-1 text-17 font-bold font-mono text-text">
					{stats?.crypto?.return_pct == null ? '—' : `${stats.crypto.return_pct} %`}
				</div>
				<div class="mt-1 text-11 text-text-3">trade {stats?.crypto?.trade ?? 0}</div>
			</div>
		</section>

		<section class="rounded-card border border-line bg-surface p-4">
			<div class="flex items-center justify-between">
				<h2 class="text-13 font-bold text-text">Trade tercatat</h2>
				<span class="font-mono text-11 text-text-3">{trades.length} baris</span>
			</div>
			{#if trades.length === 0}
				<EmptyState
					judul="Belum ada trade"
					pesan={alasan('/api/v1/journal/trades', 'Belum ada eksekusi yang dilaporkan untuk market ini.')}
					ringkas={true}
					onulang={() => void muat()}
				/>
			{:else}
				<div class="mt-2 overflow-x-auto">
					<table class="w-full text-11 text-left">
						<thead class="border-b border-line text-10 text-text-3">
							<tr>
								<th class="px-2 py-1.5">Waktu</th>
								<th class="px-2 py-1.5">Market</th>
								<th class="px-2 py-1.5">Simbol</th>
								<th class="px-2 py-1.5">Sisi</th>
								<th class="px-2 py-1.5 text-right">Harga</th>
								<th class="px-2 py-1.5 text-right">P/L %</th>
								<th class="px-2 py-1.5 text-right">Slip</th>
							</tr>
						</thead>
						<tbody class="divide-y divide-line-soft">
							{#each trades.slice(0, ringkas ? 8 : 60) as t}
								<tr class="hover:bg-surface-2/60">
									<td class="px-2 py-1.5 font-mono text-text-3">{t.iso ?? '—'}</td>
									<td class="px-2 py-1.5 uppercase text-text-3">{t.market ?? '—'}</td>
									<td class="px-2 py-1.5 font-mono text-text">{t.symbol ?? '—'}</td>
									<td class="px-2 py-1.5 text-text">{t.side ?? '—'}</td>
									<td class="px-2 py-1.5 text-right font-mono text-text">{t.price_filled ?? '—'}</td>
									<td class="px-2 py-1.5 text-right font-mono text-text">{t.pnl_pct || '—'}</td>
									<td class="px-2 py-1.5 text-right font-mono text-text-3">{t.slippage_pts || '—'}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{/if}
		</section>

		{#if !ringkas}
			<section class="grid gap-3 lg:grid-cols-2">
				<div class="rounded-card border border-line bg-surface p-4">
					<h2 class="text-13 font-bold text-text">Kinerja ekuitas</h2>
					{#if kinerja && (kinerja.n_titik ?? 0) > 0}
						<dl class="mt-2 grid grid-cols-2 gap-1.5 text-12">
							<dt class="text-text-3">Titik rekaman</dt>
							<dd class="text-right font-mono text-text">{kinerja.n_titik}</dd>
							<dt class="text-text-3">Ekuitas awal</dt>
							<dd class="text-right font-mono text-text">{rp(kinerja.ekuitas_awal)}</dd>
							<dt class="text-text-3">Ekuitas akhir</dt>
							<dd class="text-right font-mono text-text">{rp(kinerja.ekuitas_akhir)}</dd>
							<dt class="text-text-3">Perubahan</dt>
							<dd class="text-right font-mono text-text">
								{kinerja.perubahan_pct == null ? '—' : `${kinerja.perubahan_pct} %`}
							</dd>
						</dl>
					{:else}
						<EmptyState
							judul="Belum ada riwayat ekuitas"
							pesan={alasan('/api/v1/journal/performance', 'Rekaman dimulai saat sumber mengirim data.')}
							ringkas={true}
							onulang={() => void muat()}
						/>
					{/if}
				</div>

				<div class="rounded-card border border-line bg-surface p-4">
					<h2 class="text-13 font-bold text-text">Edge eksekusi (slippage per jam)</h2>
					{#if edge?.per_jam && Object.keys(edge.per_jam).length > 0}
						<div class="mt-2 grid gap-1 text-11 sm:grid-cols-2">
							{#each Object.entries(edge.per_jam) as [jam, v]}
								<div class="flex items-center justify-between rounded border border-line px-2 py-1">
									<span class="font-mono text-text-3">{jam}:00</span>
									<span class="font-mono text-text">{v.slip_rata_pts} pts · n={v.n}</span>
								</div>
							{/each}
						</div>
						<p class="mt-2 text-11 text-text-3">Latensi rata-rata {edge.latensi_rata_ms ?? '—'} ms.</p>
					{:else}
						<EmptyState
							judul="Edge belum bisa dihitung"
							pesan={alasan('/api/v1/journal/edge', 'Butuh fill nyata. Nol akan menyesatkan.')}
							ringkas={true}
							onulang={() => void muat()}
						/>
					{/if}
				</div>
			</section>
		{/if}
	</div>
{/if}
