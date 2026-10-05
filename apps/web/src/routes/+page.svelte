<script lang="ts">
	// Home — Cockpit sinyal lintas pasar (gaya A+B, 5 Okt 2026).
	//
	// Tata letak: strip ringkasan di atas (B), lalu kartu sinyal terbaik per pasar bertumpuk
	// (A). Aturan yang dipegang halaman ini:
	// - Angka yang belum lewat split beku WAJIB tampil sebagai klaim eksplorasi, bukan edge.
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
	import KartuSinyalPasar from '$lib/components/KartuSinyalPasar.svelte';
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

	// URL = satu-satunya sumber kebenaran untuk tab (pelajaran 5 Okt: state yang disalin
	// bisa menyimpang dari URL dan membuat tab macet).
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

	const daftar = $derived(sinyal?.sinyal ?? []);

	// Strip ringkasan (gaya B) — semuanya dihitung dari data yang benar-benar ada.
	const ringkas = $derived([
		{ n: daftar.length, t: 'Pasar dipantau', w: 'var(--text)' },
		{ n: daftar.filter((r) => r.ada).length, t: 'Ada sinyal', w: 'var(--accent)' },
		{
			n: daftar.filter((r) => r.ada && r.terverifikasi).length,
			t: 'Terverifikasi',
			w: 'var(--warn)'
		},
		{
			n: (kesegaran?.facts ?? []).filter((f) => f.status === 'basi').length,
			t: 'Fakta basi',
			w: 'var(--warn)'
		},
		{
			n: sehat?.status ?? '—',
			t: 'Layanan',
			w: sehat?.status === 'ok' ? 'var(--accent)' : 'var(--warn)'
		}
	]);

	// Sorotan (gaya B): sinyal berskor tertinggi yang benar-benar ada.
	const sorotan = $derived(
		daftar
			.filter((r) => r.ada && r.skor != null)
			.slice()
			.sort((a, b) => (b.skor ?? 0) - (a.skor ?? 0))[0] ?? null
	);
</script>

<svelte:head><title>Home — War Room</title></svelte:head>

<div class="ruang">
	<header class="kepala">
		<div>
			<h1>Sinyal per pasar</h1>
			<p>
				Satu sinyal terbaik tiap pasar dari konfigurasi terukur. Status verifikasi selalu
				ditampilkan — angka yang belum lewat split beku adalah klaim eksplorasi, bukan edge.
			</p>
		</div>
		<div class="status">
			<span class="pil-mikro">
				<span class="titik" style="--w:{live.status === 'live' ? 'var(--pos)' : 'var(--warn)'}"></span>
				SSE {live.status}
			</span>
			<span class="pil-mikro">DB {sehat?.db ? 'ok' : '—'}</span>
			{#if kesegaran?.checked_at}
				<span class="pil-mikro">kesegaran {umurDetik(kesegaran.facts?.[0]?.age_s ?? null)}</span>
			{/if}
		</div>
	</header>

	<!-- Sub-nav Home: URL = SSOT, jadi tiap tab benar-benar punya tampilan sendiri. -->
	<SubNav area={areaHome} aktif={sub} onpilih={pilihSub} />

	{#if alerts && alerts.terbuka > 0}
		<div class="banner" data-testid="alert-banner">
			<span>⚠</span>
			<span><b class="angka">{alerts.terbuka}</b> alert butuh perhatian</span>
			<a href="/sistem">Buka Sistem →</a>
		</div>
	{/if}

	{#if galat}
		<ErrorState pesan={galat} onulang={() => void muat()} />
	{:else if memuat}
		<Skeleton tinggi={84} />
		<Skeleton tinggi={150} />
		<Skeleton tinggi={150} />
	{:else if sub === 'kinerja'}
		<section class="kinerja" aria-label="Kinerja">
			<StrategyLeaderboard />
			<div class="dua-kolom">
				<div class="kolom">
					<EquityCurve points={dataEquity?.points} stats={dataEquity?.stats} />
					<StatisticalEdgeCard verdict={dataVerdict} judul="Polymarket 5m Statistical Gate" />
				</div>
				<div class="kolom">
					<RiskMeter risiko={dataRisiko} />
					<div class="kartu-kejadian">
						<div class="kepala-kejadian">
							<h3>Kejadian Real-Time</h3>
							<span class="label-mikro">{live.status}</span>
						</div>
						<EventFeed
							kejadian={live.kejadian}
							memuat={live.status === 'menyambung'}
							galat={live.pesan}
						/>
					</div>
				</div>
			</div>
		</section>
	{:else}
		<!-- Tab "sinyal" (default): strip ringkasan (B) + kartu per pasar (A) -->
		<section class="strip" aria-label="Ringkasan">
			{#each ringkas as r (r.t)}
				<div class="chip">
					<b class="angka" style="--w:{r.w}">{r.n}</b>
					<span class="label-mikro">{r.t}</span>
				</div>
			{/each}
		</section>

		<!-- Sorotan (B): satu keputusan jelas saat pertama buka -->
		{#if sorotan}
			<section class="sorotan" aria-label="Sinyal terkuat">
				<span class="label-mikro">Sinyal terkuat saat ini · {sorotan.label}</span>
				<div class="baris">
					<span class="subjek angka">{sorotan.subjek ?? '—'}</span>
					{#if sorotan.arah}<span class="arah">{sorotan.arah}</span>{/if}
					{#if sorotan.skor != null}<span class="skor-besar angka">{sorotan.skor}</span>{/if}
				</div>
				<p class="alasan">{sorotan.alasan}</p>
				{#if !sorotan.terverifikasi}
					<p class="jujur" role="note">{sorotan.catatan_kejujuran}</p>
				{/if}
			</section>
		{/if}

		<!-- Kartu per pasar (A) -->
		<section class="daftar" aria-label="Sinyal tiap pasar">
			{#each daftar as s (s.pasar)}
				<KartuSinyalPasar {s} utama={s.pasar === sorotan?.pasar} />
			{/each}
		</section>

		{#if daftar.length > 0 && !sinyal?.ada}
			<p class="catatan">
				Belum ada pasar yang menghasilkan sinyal. Tiap kartu menyebutkan alasannya — sengaja
				tidak diisi angka 0 supaya tidak terlihat seperti data.
			</p>
		{/if}
	{/if}
</div>

<style>
	.ruang {
		display: flex;
		flex-direction: column;
		gap: 16px;
	}
	.kepala {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 16px;
		flex-wrap: wrap;
	}
	h1 {
		font-family: var(--font-display);
		font-size: 22px;
		margin: 0 0 4px;
	}
	.kepala p {
		margin: 0;
		font-size: 12px;
		color: var(--text-3);
		max-width: 64ch;
	}
	.status {
		display: flex;
		gap: 6px;
		flex-wrap: wrap;
	}
	.pil-mikro {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		font-family: var(--font-mono);
		font-size: 10px;
		color: var(--text-3);
		border: 1px solid var(--line);
		border-radius: var(--radius-pil);
		padding: 3px 9px;
	}
	.titik {
		width: 7px;
		height: 7px;
		border-radius: 50%;
		background: var(--w);
	}
	.banner {
		display: flex;
		align-items: center;
		gap: 10px;
		font-size: 12px;
		color: var(--text-2);
		background: color-mix(in srgb, var(--warn) 10%, transparent);
		border: 1px solid color-mix(in srgb, var(--warn) 40%, transparent);
		border-radius: var(--radius-card);
		padding: 10px 14px;
	}
	.banner a {
		margin-left: auto;
		color: var(--warn);
	}
	.strip {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(118px, 1fr));
		gap: 8px;
	}
	.chip {
		background: var(--surface);
		border: 1px solid var(--line-soft);
		border-radius: var(--radius-card);
		padding: 10px 12px;
		display: flex;
		flex-direction: column;
		gap: 2px;
	}
	.chip b {
		font-size: 18px;
		font-weight: 700;
		color: var(--w, var(--text));
	}
	.sorotan {
		background: linear-gradient(160deg, var(--surface-2), var(--surface));
		border: 1px solid color-mix(in srgb, var(--accent) 35%, transparent);
		border-radius: var(--radius-card);
		padding: 16px;
	}
	.baris {
		display: flex;
		align-items: baseline;
		gap: 10px;
		flex-wrap: wrap;
		margin-top: 6px;
	}
	.subjek {
		font-size: 28px;
		font-weight: 700;
		letter-spacing: -0.02em;
	}
	.arah {
		font-family: var(--font-mono);
		font-size: 12px;
		padding: 2px 8px;
		border-radius: 6px;
		color: var(--accent);
		background: color-mix(in srgb, var(--accent) 14%, transparent);
		border: 1px solid color-mix(in srgb, var(--accent) 30%, transparent);
	}
	.skor-besar {
		font-size: 22px;
		font-weight: 700;
		color: var(--accent);
		margin-left: auto;
	}
	.alasan {
		margin: 10px 0 0;
		font-size: 12px;
		color: var(--text-2);
	}
	.daftar {
		display: flex;
		flex-direction: column;
		gap: 12px;
	}
	/* Catatan kejujuran — elemen paling khas di produk ini, jadi TIDAK boleh memakai
	   pola generik (border kiri tebal) yang justru jadi penanda UI hasil AI. Dipakai
	   penanda teks + latar tipis: tetap menonjol, tapi jelas disengaja. */
	.jujur {
		margin: 10px 0 0;
		font-size: 11px;
		line-height: 1.5;
		color: var(--warn);
		background: color-mix(in srgb, var(--warn) 7%, transparent);
		border-radius: 6px;
		padding: 7px 10px 7px 26px;
		position: relative;
	}
	.jujur::before {
		content: '!';
		position: absolute;
		left: 9px;
		top: 8px;
		width: 12px;
		height: 12px;
		border-radius: 50%;
		background: var(--warn);
		color: var(--bg);
		font-size: 9px;
		font-weight: 700;
		line-height: 12px;
		text-align: center;
	}
	.catatan {
		font-size: 12px;
		color: var(--text-3);
		margin: 0;
	}
	.kinerja {
		display: flex;
		flex-direction: column;
		gap: 16px;
	}
	.dua-kolom {
		display: grid;
		grid-template-columns: 1fr;
		gap: 16px;
	}
	.kolom {
		display: flex;
		flex-direction: column;
		gap: 16px;
	}
	@media (min-width: 1024px) {
		.dua-kolom {
			grid-template-columns: 7fr 5fr;
		}
	}
	.kartu-kejadian {
		background: var(--surface-2);
		border: 1px solid var(--line);
		border-radius: var(--radius-card);
		padding: 12px;
	}
	.kepala-kejadian {
		display: flex;
		align-items: center;
		justify-content: space-between;
		border-bottom: 1px solid var(--line-soft);
		padding-bottom: 8px;
		margin-bottom: 8px;
	}
	.kepala-kejadian h3 {
		font-size: 13px;
		font-weight: 500;
		margin: 0;
	}
</style>
