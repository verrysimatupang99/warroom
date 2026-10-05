<script lang="ts">
	// Home — War Room, cangkang beebots (6 Okt 2026).
	//
	// TATA LETAK: mengikuti App.tsx beebots — header dengan kartu angka, lalu grid
	// "kolom utama + rail kanan". Bedanya satu hal, dan itu disengaja: beebots
	// menampilkan 3 kolom karena 3 lebah memang seragam. Di sini ada 6 pasar dengan
	// BENTUK DATA YANG BERBEDA (crypto punya entry/SL/TP, Polymarket punya win-rate vs
	// break-even, BSJP punya tier, LP punya IL, forex belum punya sinyal). Memaksakan
	// enam kolom seragam akan menghapus perbedaan itu — jadi dipakai SATU kolom penuh
	// yang isinya berganti sesuai pasar terpilih, dan rail kanan jadi pemilihnya.
	//
	// ATURAN YANG TIDAK BOLEH HILANG:
	// - Angka yang belum lewat split beku tampil sebagai klaim eksplorasi, bukan edge.
	// - Pasar tanpa sinyal tetap tampil dengan alasannya; skor "—", bukan 0.
	import { getAlerts, getArea, getKesegaran, getKesehatan, getSinyalPerPasar } from '$lib/api/client';
	import type {
		AlertsPayload,
		AreaPayload,
		Fakta,
		Kesehatan,
		KesegaranPayload,
		SinyalPayload
	} from '$lib/api/types';
	import { live } from '$lib/api/live.svelte';
	import { umurDetik } from '$lib/format';
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { AREAS } from '$lib/nav';
	import KolomPasar from '$lib/components/KolomPasar.svelte';
	import SubNav from '$lib/components/SubNav.svelte';
	import EquityCurve from '$lib/components/EquityCurve.svelte';
	import RiskMeter from '$lib/components/RiskMeter.svelte';
	import EventFeed from '$lib/components/EventFeed.svelte';
	import StrategyLeaderboard from '$lib/components/StrategyLeaderboard.svelte';
	import StatisticalEdgeCard from '$lib/components/StatisticalEdgeCard.svelte';
	import ErrorState from '$lib/components/ErrorState.svelte';
	import Skeleton from '$lib/components/Skeleton.svelte';

	let sinyal = $state<SinyalPayload | null>(null);
	let kesegaran = $state<KesegaranPayload | null>(null);
	let sehat = $state<Kesehatan | null>(null);
	let alerts = $state<AlertsPayload | null>(null);
	let kripto = $state<AreaPayload | null>(null);
	let polymarket = $state<AreaPayload | null>(null);
	let galat = $state<string | null>(null);
	let memuat = $state(true);

	// URL = satu-satunya sumber kebenaran (pelajaran 5 Okt: state yang disalin bisa
	// menyimpang dari URL). Pasar terpilih juga lewat query, supaya bisa di-bookmark
	// dan tombol Back bekerja.
	const areaHome = AREAS.find((a) => a.kunci === 'home')!;
	const sub = $derived.by(() => {
		const s = page.url.searchParams.get('sub');
		if (s && areaHome.anak.some((a) => a.slug === s)) return s;
		return areaHome.anak[0].slug;
	});

	function pilihSub(s: string) {
		if (typeof window !== 'undefined') {
			void goto(`?sub=${s}`, { keepFocus: true, noScroll: true });
		}
	}

	async function muat() {
		const [s, k, h, al, kr, pm] = await Promise.allSettled([
			getSinyalPerPasar(),
			getKesegaran(),
			getKesehatan(),
			getAlerts(),
			getArea('crypto'),
			getArea('polymarket')
		]);
		if (s.status === 'fulfilled') {
			sinyal = s.value;
			galat = null;
		} else {
			galat = s.reason instanceof Error ? s.reason.message : String(s.reason);
		}
		if (k.status === 'fulfilled') kesegaran = k.value;
		if (h.status === 'fulfilled') sehat = h.value;
		if (al.status === 'fulfilled') alerts = al.value;
		if (kr.status === 'fulfilled') kripto = kr.value;
		if (pm.status === 'fulfilled') polymarket = pm.value;
		memuat = false;
	}

	$effect(() => {
		void muat();
		const t = setInterval(() => void muat(), 15000);
		return () => clearInterval(t);
	});

	const cariFakta = (koleksi: Fakta[], kunci: string) =>
		koleksi.find((f) => f.key === kunci)?.value ?? null;

	const faktaKripto = $derived(kripto?.facts ?? []);
	const faktaPoly = $derived(polymarket?.facts ?? []);
	const dataEquity = $derived(
		(cariFakta(faktaKripto, 'equity') as {
			points?: { i: number; r: number }[];
			stats?: Record<string, number>;
		} | null) ?? null
	);
	const dataRisiko = $derived((cariFakta(faktaKripto, 'risiko') as Record<string, unknown>) ?? null);
	const dataVerdict = $derived(
		(cariFakta(faktaPoly, 'verdict') as {
			n?: number;
			win?: number;
			be?: number;
			ci?: number;
			ci95?: [number, number];
		} | null) ?? null
	);
	const dataPolyPaper = $derived(
		(cariFakta(faktaPoly, 'poly_paper') as {
			arms?: { nama: string; balance: number; pnl: number; wins: number; losses: number; entries: number; settled: number }[];
		} | null) ?? null
	);

	// Papan peringkat strategi — HANYA dari angka nyata (equity crypto + arm Polymarket).
	// Tidak ada baris contoh; kalau sumbernya kosong, kartunya menyatakan kosong.
	const strategiNyata = $derived.by(() => {
		type Baris = {
			rank: number;
			id: string;
			nama: string;
			venue: string;
			tipe: 'PAPER' | 'LIVE' | 'SIGNAL-ONLY' | 'RESEARCH';
			winrate_pct: number | null;
			total_r: number | null;
			expectancy_r: number | null;
			n_samples: number;
			max_dd_r: number | null;
			status: 'UNGGUL' | 'PENGUJIAN' | 'FLAG_EXIT' | 'MONITOR';
			status_detail: string;
			friksi_est_pct?: number | null;
		};
		const out: Baris[] = [];

		// 1) Crypto SMC — dari fakta `equity` (ledger paper nyata).
		const s = dataEquity?.stats as Record<string, number> | undefined;
		if (s && typeof s.trades === 'number' && s.trades > 0) {
			const wr = typeof s.winrate_pct === 'number' ? s.winrate_pct : null;
			out.push({
				rank: 0,
				id: 'crypto-smc',
				nama: 'Crypto SMC Multi-Timeframe (paper)',
				venue: 'MEXC / Binance Futures',
				tipe: 'PAPER',
				winrate_pct: wr,
				total_r: typeof s.total_r === 'number' ? s.total_r : null,
				expectancy_r: typeof s.expectancy_r === 'number' ? s.expectancy_r : null,
				n_samples: s.trades,
				max_dd_r: typeof s.max_drawdown_r === 'number' ? s.max_drawdown_r : null,
				status: 'MONITOR',
				status_detail: `Sampel ${s.trades} trade — belum cukup & belum split beku. Angka apa adanya dari ledger paper.`
			});
		}

		// 2) Arm Polymarket — dari fakta `poly_paper.arms` (ledger paper nyata).
		for (const a of dataPolyPaper?.arms ?? []) {
			const n = (a.wins ?? 0) + (a.losses ?? 0);
			const wr = n > 0 ? ((a.wins ?? 0) / n) * 100 : null;
			out.push({
				rank: 0,
				id: `poly-${a.nama.replace(/\s+/g, '-').toLowerCase()}`,
				nama: `Polymarket ${a.nama}`,
				venue: 'Polymarket CLOB 5m',
				tipe: 'PAPER',
				winrate_pct: wr,
				// PnL arm dalam USD, BUKAN R — jangan salah label sebagai R.
				total_r: null,
				expectancy_r: null,
				n_samples: a.settled ?? n,
				max_dd_r: null,
				status: (a.pnl ?? 0) > 0 ? 'PENGUJIAN' : (a.pnl ?? 0) < 0 ? 'FLAG_EXIT' : 'MONITOR',
				status_detail: `PnL ${a.pnl >= 0 ? '+' : ''}$${a.pnl.toFixed(2)} (USD, bukan R) · balance $${a.balance.toFixed(2)} · ${a.settled} settled. Edge belum lolos gate.`
			});
		}

		// Urut: yang punya R di atas (urut R), sisanya urut winrate. Kosong di bawah.
		out.sort((a, b) => {
			if (a.total_r != null && b.total_r != null) return b.total_r - a.total_r;
			if (a.total_r != null) return -1;
			if (b.total_r != null) return 1;
			return (b.winrate_pct ?? -1) - (a.winrate_pct ?? -1);
		});
		out.forEach((r, i) => (r.rank = i + 1));
		return out;
	});

	const daftar = $derived(sinyal?.sinyal ?? []);

	// Kartu angka header — semuanya dihitung dari data yang benar-benar ada.
	const ringkas = $derived([
		{ n: daftar.length, t: 'Pasar dipantau', sub: 'multi-market', w: 'var(--text-2)' },
		{
			n: daftar.filter((r) => r.ada).length,
			t: 'Ada sinyal',
			sub: 'dari konfigurasi terukur',
			w: 'var(--accent)'
		},
		{
			n: daftar.filter((r) => r.ada && r.terverifikasi).length,
			t: 'Terverifikasi',
			sub: 'lolos split beku',
			w: 'var(--color-pos)'
		},
		{
			n: (kesegaran?.facts ?? []).filter((f) => f.status === 'basi').length,
			t: 'Fakta basi',
			sub: 'perlu disegarkan',
			w: 'var(--warn)'
		}
	]);

	// Urutan rail: berskor tinggi di atas, yang kosong di bawah. Sama seperti
	// leaderboard beebots, tapi urutannya berguna untuk memilih.
	const pasarTerurut = $derived(
		daftar.slice().sort((a, b) => {
			if (a.skor == null && b.skor == null) return a.label.localeCompare(b.label);
			if (a.skor == null) return 1;
			if (b.skor == null) return -1;
			return (b.skor ?? 0) - (a.skor ?? 0);
		})
	);

	const pasarDipilih = $derived.by(() => {
		const p = page.url.searchParams.get('pasar');
		const ada = pasarTerurut.find((r) => r.pasar === p);
		return ada ?? pasarTerurut[0] ?? null;
	});

	function pilihPasar(p: string) {
		if (typeof window !== 'undefined') {
			const url = new URL(window.location.href);
			url.searchParams.set('pasar', p);
			void goto(url.pathname + url.search, { keepFocus: true, noScroll: true });
		}
	}

	const peringkatTerpilih = $derived(
		Math.max(1, pasarTerurut.findIndex((r) => r.pasar === pasarDipilih?.pasar) + 1)
	);
</script>

<svelte:head><title>Home — War Room</title></svelte:head>

<div class="app">
	<!-- ---------- header (mengikuti .top beebots) ---------- -->
	<header class="top">
		<div>
			<h1 class="logo">War<span>Room</span></h1>
			<div class="brand-sub">
				<span class="mode mode-paper">PAPER</span>
				<span class="dim">multi-market · 7 area &amp; riset</span>
			</div>
		</div>

		<div class="counters">
			{#each ringkas as r (r.t)}
				<div class="counter">
					<div class="eyebrow">{r.t}</div>
					<div class="counter-value" style="color:{r.w}">{r.n}</div>
					<div class="counter-sub">{r.sub}</div>
				</div>
			{/each}
		</div>

		<div class="top-right">
			<div class="recon recon-{live.status === 'live' ? 'ok' : 'idle'}">
				<span class="recon-light" aria-hidden="true"></span>
				<div>
					<div class="eyebrow">Aliran</div>
					<div class="recon-text">SSE {live.status}</div>
				</div>
			</div>
			{#if alerts && alerts.terbuka > 0}
				<a class="eyebrow" href="/sistem" style="text-decoration:none">
					⚠ {alerts.terbuka} alert butuh perhatian →
				</a>
			{/if}
		</div>
	</header>

	<!-- Sub-nav Home: URL = SSOT. -->
	<SubNav area={areaHome} aktif={sub} onpilih={pilihSub} />

	{#if galat}
		<ErrorState pesan={galat} onulang={() => void muat()} />
	{:else if memuat}
		<Skeleton tinggi={84} />
		<Skeleton tinggi={220} />
	{:else if sub === 'kinerja'}
		<!-- ---------- tab Kinerja ---------- -->
		<section class="grid" aria-label="Kinerja">
			<h2 class="sr-only">Kinerja</h2>
			<div class="kolom">
				<StrategyLeaderboard strategies={strategiNyata} />
				<EquityCurve points={dataEquity?.points} stats={dataEquity?.stats} />
				<StatisticalEdgeCard verdict={dataVerdict} judul="Polymarket 5m Statistical Gate" />
			</div>
			<aside class="rail">
				<RiskMeter risiko={dataRisiko} />
				<section class="rail-card">
					<div class="rail-head">
						<span class="eyebrow">Kejadian real-time</span>
						<span class="dim">{live.status}</span>
					</div>
					<EventFeed
						kejadian={live.kejadian}
						memuat={live.status === 'menyambung'}
						galat={live.pesan}
					/>
				</section>
			</aside>
		</section>
	{:else}
		<!-- ---------- tab Sinyal (bawaan) ---------- -->
		<section class="grid" aria-label="Sinyal per pasar">
			<h2 class="sr-only">Sinyal per pasar</h2>
			<!-- Kolom utama: SATU pasar penuh, isinya berganti sesuai pilihan rail. -->
			<div>
				{#if pasarDipilih}
					<KolomPasar s={pasarDipilih} peringkat={peringkatTerpilih} />
				{:else}
					<p class="dim">
						Belum ada pasar yang bisa ditampilkan. Tiap pasar menyebutkan alasannya — sengaja
						tidak diisi angka 0 supaya tidak terlihat seperti data.
					</p>
				{/if}
			</div>

			<!-- Rail kanan: pemilih pasar + ringkasan. -->
			<aside class="rail">
				<section class="rail-card board">
					<div class="rail-head">
						<span class="eyebrow">Pasar</span>
						<span class="dim">skor</span>
					</div>
					{#each pasarTerurut as r, i (r.pasar)}
						<button
							class="board-row"
							aria-current={r.pasar === pasarDipilih?.pasar}
							style="--bee:{r.ada ? 'var(--accent)' : 'var(--text-3)'}"
							onclick={() => pilihPasar(r.pasar)}
						>
							<span class="board-rank">{i + 1}</span>
							<span class="board-name">{r.label}</span>
							<span class="board-eq">{r.skor != null ? r.skor : '—'}</span>
							<span class="board-bar">
								<span style="transform:scaleX({r.skor != null ? r.skor / 100 : 0})"></span>
							</span>
						</button>
					{/each}
				</section>

				<section class="rail-card">
					<div class="rail-head">
						<span class="eyebrow">Kesegaran</span>
						<span class="dim">{sehat?.db ? 'db ok' : 'db —'}</span>
					</div>
					<div class="dim text-13">
						{#if kesegaran?.checked_at}
							Diperiksa {umurDetik(kesegaran.facts?.[0]?.age_s ?? null)} lalu
						{:else}
							Belum ada pemeriksaan
						{/if}
					</div>
				</section>

				{#if daftar.length > 0 && !sinyal?.ada}
					<section class="rail-card">
						<div class="eyebrow">Catatan</div>
						<p class="dim text-13 mt-1.5">
							Belum ada pasar yang menghasilkan sinyal. Tiap pasar menyebutkan alasannya —
							sengaja tidak diisi angka 0 supaya tidak terlihat seperti data.
						</p>
					</section>
				{/if}
			</aside>
		</section>
	{/if}
</div>

<style>
	.kolom {
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}
</style>
