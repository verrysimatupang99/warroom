<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { AREAS, SLUG_LAMA } from '$lib/nav';
	import { getAreaFakta, getLiveArming } from '$lib/api/client';
	import type { AreaPayload, Fact, LiveArming } from '$lib/api/types';
	import MarketShell from '$lib/components/MarketShell.svelte';
	import Skeleton from '$lib/components/Skeleton.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import BatasPasar from '$lib/components/BatasPasar.svelte';
	import PolyAltBtc5m from '$lib/components/PolyAltBtc5m.svelte';
	import GateBlok from '$lib/components/GateBlok.svelte';
	import DatasetExplorer from '$lib/components/DatasetExplorer.svelte';

	const area = AREAS.find((a) => a.kunci === 'polymarket')!;
	const sub = $derived.by(() => {
		const s = page.url.searchParams.get('sub') ?? 'ringkas';
		return SLUG_LAMA[s] ?? s;
	});

	let payload = $state<AreaPayload | null>(null);
	let arming = $state<LiveArming | null>(null);
	let memuat = $state(true);
	let galat = $state<string | null>(null);

	async function muat() {
		memuat = true;
		galat = null;
		const [a, l] = await Promise.allSettled([getAreaFakta('polymarket'), getLiveArming()]);
		if (a.status === 'fulfilled') {
			payload = a.value;
		} else {
			galat = a.reason instanceof Error ? a.reason.message : 'Gagal memuat fakta Polymarket';
		}
		if (l.status === 'fulfilled') {
			arming = l.value;
		}
		memuat = false;
	}

	onMount(() => {
		void muat();
	});

	function cariFakta(kind: string, key: string): Fact | null {
		if (!payload?.facts) return null;
		return payload.facts.find((f) => f.kind === kind && f.key === key) ?? null;
	}

	const verdict = $derived(
		(cariFakta('poly.verdict', 'verdict')?.value ?? payload?.data?.verdict ?? null) as Record<string, any> | null
	);
	const agen = $derived(
		(cariFakta('poly.agent', 'ringkas')?.value ?? payload?.data?.ringkas ?? null) as Record<string, any> | null
	);
	const drift = $derived(
		(cariFakta('poly.parity', 'drift')?.value ?? payload?.data?.drift ?? null) as Record<string, any> | null
	);
	const klaim = $derived(
		(cariFakta('poly.money', 'klaim-pilot')?.value ?? payload?.data?.['klaim-pilot'] ?? null) as Record<string, any> | null
	);
	const polyAltFakta = $derived(cariFakta('poly.alt', 'btc-5m'));
	const polyAlt = $derived(
		(polyAltFakta?.value ?? payload?.data?.['btc-5m'] ?? null) as Record<string, any> | null
	);
	const recorderFakta = $derived(cariFakta('poly.dataset', 'recorder'));
	const cakupanFakta = $derived(cariFakta('poly.akses', 'cakupan'));

	const ARMS_URUTAN = [
		{ key: 'D-favorit', label: 'Arm D · Favorit (45–119s)', fokus: 'Blok awal odds tinggi 0,70–0,95' },
		{ key: 'B-kandidat', label: 'Arm B · Kandidat (45–240s)', fokus: 'Mirror aturan favorit standar' },
		{ key: 'A-shadow', label: 'Arm A · Shadow (0,15–0,48)', fokus: 'Eksplorasi underdog / harga murah' },
		{ key: 'C-fade', label: 'Arm C · Fade (Invert)', fokus: 'Lawan arah sinyal (eksperimen)' }
	] as const;

	const armsData = $derived.by(() => {
		return ARMS_URUTAN.map((item) => {
			const f = cariFakta('poly.arm', item.key);
			const v = (f?.value ?? payload?.data?.[item.key] ?? null) as Record<string, any> | null;
			const s = (v?.summary ?? {}) as Record<string, any>;
			const strat = (s?.strategi ?? {}) as Record<string, any>;
			const tot = (s?.totals ?? s) as Record<string, any>;
			const settled = typeof s.settled === 'number' ? s.settled : typeof tot.settled === 'number' ? tot.settled : typeof tot.entries === 'number' ? tot.entries : null;
			const wins = typeof s.wins === 'number' ? s.wins : typeof tot.wins === 'number' ? tot.wins : null;
			const losses = typeof s.losses === 'number' ? s.losses : typeof tot.losses === 'number' ? tot.losses : null;
			const wr = settled && settled > 0 && wins != null ? (wins / settled) * 100 : null;
			return {
				...item,
				tersedia: Boolean(v),
				statusSummary: s.status ?? v?.state_status ?? '—',
				mode: s.mode ?? 'paper-mirror',
				entryLo: s.entryLo ?? strat.entryLo ?? null,
				entryHi: s.entryHi ?? strat.entryHi ?? null,
				windowSec: strat.decideWindowSeconds ?? '45-240',
				invert: Boolean(strat.invert),
				balance: typeof s.balance === 'number' ? s.balance : typeof s.equity === 'number' ? s.equity : null,
				initialBalance: typeof s.initialBalance === 'number' ? s.initialBalance : null,
				pnl: typeof s.pnl === 'number' ? s.pnl : null,
				settled,
				wins,
				losses,
				wr,
				masuk400: v?.masuk_400_baris ?? null,
				tolak400: v?.tolak_400_baris ?? null,
				mtime: v?.state_mtime ?? null
			};
		});
	});

	const agenSum = $derived((agen?.summary ?? null) as Record<string, any> | null);
	const agenState = $derived((agen?.state ?? null) as Record<string, any> | null);
	const agenCfg = $derived((agenSum?.config ?? null) as Record<string, any> | null);
	const agenHb = $derived((agen?.heartbeat ?? null) as Record<string, any> | null);
	const settledList = $derived(((agen?.settled_terakhir ?? []) as Record<string, any>[]));
	const eventsList = $derived(((agen?.events_terakhir ?? []) as Record<string, any>[]));
	const diterapkanList = $derived(((agen?.diterapkan_200 ?? []) as Record<string, any>[]));
	const ditolakList = $derived(((agen?.ditolak_200 ?? []) as Record<string, any>[]));
	const polyAltLedger = $derived(((polyAlt?.ledger?.terakhir ?? []) as Record<string, any>[]));

	function angka(v: number | null | undefined, digit = 2): string {
		if (v == null || !Number.isFinite(v)) return '—';
		return v.toLocaleString('id-ID', { minimumFractionDigits: digit, maximumFractionDigits: digit });
	}
	function usd(v: number | null | undefined, digit = 2): string {
		if (v == null || !Number.isFinite(v)) return '—';
		const tanda = v < 0 ? '−' : '';
		return `${tanda}$${Math.abs(v).toLocaleString('id-ID', { minimumFractionDigits: digit, maximumFractionDigits: digit })}`;
	}
	function usdSigned(v: number | null | undefined, digit = 2): string {
		if (v == null || !Number.isFinite(v)) return '—';
		const tanda = v > 0 ? '+' : v < 0 ? '−' : '';
		return `${tanda}$${Math.abs(v).toLocaleString('id-ID', { minimumFractionDigits: digit, maximumFractionDigits: digit })}`;
	}
	function waktuTs(ts: number | string | null | undefined): string {
		if (!ts) return '—';
		const d = typeof ts === 'number' ? new Date(ts > 1e12 ? ts : ts * 1000) : new Date(ts);
		if (Number.isNaN(d.getTime())) return String(ts);
		return d.toLocaleString('id-ID', {
			day: '2-digit',
			month: 'short',
			hour: '2-digit',
			minute: '2-digit',
			timeZone: 'Asia/Jakarta'
		});
	}
</script>

<svelte:head><title>Polymarket | War Room</title></svelte:head>

<MarketShell
	{area}
	aktif={sub}
	judul="Polymarket"
	tag="PAPER"
	deskripsi="Prediksi pasar biner BTC & ETH 5m (Arm Favorit 0,70–0,95 & AI Agent Harness). Eksekusi live CLOB ditangguhkan sementara; mode paper, evaluasi verdict, dan riset berjalan aktif."
	sumber="poly-agent + favorite-live-verdict + polybtc-5m"
	terverifikasi={true}
>
	{#if memuat && !payload}
		<Skeleton baris={5} tinggi={44} />
	{:else if galat && !payload}
		<EmptyState judul="Data Polymarket belum tersedia" pesan={galat} onulang={() => void muat()} />
	{:else if sub === 'ringkas'}
		<div class="space-y-4">
			<!-- 4 Kartu KPI Utama (seragam dgn Forex, Crypto, IDX) -->
			<section class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
				<div class="rounded-card border border-line bg-surface p-4">
					<div class="label-mikro font-mono text-text-3">VERDICT FAVORIT (0.70–0.95)</div>
					<div class="mt-1 flex items-baseline gap-2">
						<span class="font-mono text-17 font-bold text-pos">
							{verdict?.winRate != null ? `${angka(verdict.winRate, 2)}%` : '—'}
						</span>
						{#if verdict?.verdict_alat}
							<span class="rounded border border-pos/40 bg-pos/10 px-1.5 py-0.5 font-mono text-10 font-bold text-pos">
								{verdict.verdict_alat}
							</span>
						{/if}
					</div>
					<div class="mt-1 font-mono text-11 text-text-3">
						{verdict?.win != null && verdict?.n != null
							? `${verdict.win.toLocaleString('id-ID')}W / ${verdict.n.toLocaleString('id-ID')} sampel (${(verdict.windows ?? 0).toLocaleString('id-ID')} window)`
							: 'menunggu verdict-sync'}
					</div>
				</div>

				<div class="rounded-card border border-line bg-surface p-4">
					<div class="label-mikro font-mono text-text-3">BREAK-EVEN & EV / STAKE</div>
					<div class="mt-1 flex items-baseline gap-2">
						<span class="font-mono text-17 font-bold text-text">
							{verdict?.breakEven_pct != null ? `${angka(verdict.breakEven_pct, 2)}%` : '—'}
						</span>
						{#if verdict?.evPerStake != null}
							<span class="font-mono text-12 font-bold {verdict.evPerStake >= 0 ? 'text-pos' : 'text-neg'}">
								EV {verdict.evPerStake >= 0 ? '+' : ''}{angka(verdict.evPerStake, 2)}%
							</span>
						{/if}
					</div>
					<div class="mt-1 font-mono text-11 text-text-3">
						{#if Array.isArray(verdict?.ci95)}
							CI 95%: {angka(verdict.ci95[0], 2)}%–{angka(verdict.ci95[1], 2)}% · deff {angka(verdict?.deff, 3)}
						{:else}
							Wilson 95% + koreksi klaster
						{/if}
					</div>
				</div>

				<div class="rounded-card border border-line bg-surface p-4">
					<div class="label-mikro font-mono text-text-3">POLY AI AGENT (PAPER)</div>
					<div class="mt-1 flex items-baseline gap-2">
						<span class="font-mono text-17 font-bold text-text">
							{usd(agenState?.balance ?? agenSum?.balance)}
						</span>
						{#if (agenState?.pnl ?? agenSum?.pnl) != null}
							{@const p = Number(agenState?.pnl ?? agenSum?.pnl)}
							<span class="font-mono text-12 font-bold {p >= 0 ? 'text-pos' : 'text-neg'}">
								({usdSigned(p)})
							</span>
						{/if}
					</div>
					<div class="mt-1 font-mono text-11 text-text-3">
						{#if (agenState?.settled ?? agenSum?.settled) != null}
							{@const st = Number(agenState?.settled ?? agenSum?.settled)}
							{@const wn = Number(agenState?.wins ?? agenSum?.wins ?? 0)}
							{@const ls = Number(agenState?.losses ?? agenSum?.losses ?? 0)}
							{st} settled ({wn}W / {ls}L · WR {st > 0 ? angka((wn / st) * 100, 1) : '0'}%)
						{:else}
							modal awal $100,00 paper
						{/if}
					</div>
				</div>

				<div class="rounded-card border border-line bg-surface p-4">
					<div class="label-mikro font-mono text-text-3">STATUS ENGINE & SAMPEL</div>
					<div class="mt-1 flex items-center gap-2">
						<span class="font-mono text-14 font-bold {agenHb?.phase === 'loop' ? 'text-pos' : 'text-text'}">
							{agenHb?.phase === 'loop' ? '● LOOP AKTIF' : '○ PAPER MIRROR'}
						</span>
					</div>
					<div class="mt-1 font-mono text-11 text-text-3">
						{#if verdict?.n != null && verdict?.nNeeded != null}
							Target konfirmasi: {verdict.n.toLocaleString('id-ID')} / {verdict.nNeeded.toLocaleString('id-ID')} ({angka((verdict.n / verdict.nNeeded) * 100, 1)}%)
						{:else}
							Eksekusi CLOB live ditangguhkan sementara
						{/if}
					</div>
				</div>
			</section>

			<!-- Perbandingan 4 Arm Paper Polymarket -->
			<section class="rounded-card border border-line bg-surface p-4">
				<div class="flex flex-wrap items-center justify-between gap-2">
					<div>
						<h2 class="text-13 font-bold text-text">Matriks 4 Arm Eksperimen Polymarket (Paper Mirror)</h2>
						<p class="mt-0.5 text-11 text-text-3">
							Perbandingan performa antar-arm di <code class="font-mono">/var/lib/poly-paper*</code> beserta keputusan 400 evaluasi terakhir.
						</p>
					</div>
					<span class="font-mono text-10 text-text-3">sumber: job poly-sync</span>
				</div>

				<div class="mt-3 overflow-x-auto">
					<table class="w-full text-left text-11">
						<thead class="border-b border-line font-mono text-10 text-text-3">
							<tr>
								<th class="px-2 py-1.5">Arm & Fokus</th>
								<th class="px-2 py-1.5">Band Odds</th>
								<th class="px-2 py-1.5">Window</th>
								<th class="px-2 py-1.5 text-right">Settled (W/L)</th>
								<th class="px-2 py-1.5 text-right">Win Rate</th>
								<th class="px-2 py-1.5 text-right">Saldo Paper</th>
								<th class="px-2 py-1.5 text-right">PnL Bersih</th>
								<th class="px-2 py-1.5 text-right">Ekor 400 (Masuk/Tolak)</th>
							</tr>
						</thead>
						<tbody class="divide-y divide-line-soft font-mono">
							{#each armsData as a (a.key)}
								<tr class="hover:bg-surface-2/60">
									<td class="px-2 py-2">
										<div class="font-bold text-text">{a.label}</div>
										<div class="font-sans text-10 text-text-3">{a.fokus}</div>
									</td>
									<td class="px-2 py-2 text-text-2">
										{a.entryLo != null && a.entryHi != null ? `${a.entryLo} – ${a.entryHi}` : '—'}
										{#if a.invert}
											<span class="ml-1 rounded bg-warn/15 px-1 py-0.5 text-9 text-warn">INVERT</span>
										{/if}
									</td>
									<td class="px-2 py-2 text-text-3">{a.windowSec}s</td>
									<td class="px-2 py-2 text-right text-text">
										{#if a.settled != null}
											{a.settled} <span class="text-text-3">({a.wins ?? 0}W/{a.losses ?? 0}L)</span>
										{:else}
											—
										{/if}
									</td>
									<td class="px-2 py-2 text-right font-bold {(a.wr ?? 0) >= 75 ? 'text-pos' : 'text-text'}">
										{a.wr != null ? `${angka(a.wr, 1)}%` : '—'}
									</td>
									<td class="px-2 py-2 text-right text-text">{usd(a.balance)}</td>
									<td class="px-2 py-2 text-right font-bold {(a.pnl ?? 0) > 0 ? 'text-pos' : (a.pnl ?? 0) < 0 ? 'text-neg' : 'text-text-3'}">
										{usdSigned(a.pnl)}
									</td>
									<td class="px-2 py-2 text-right text-text-2">
										{a.masuk400 != null ? `${a.masuk400} / ${a.tolak400 ?? 0}` : '—'}
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</section>

			<!-- Ringkasan Settlement Terakhir di Ringkas -->
			{#if settledList.length > 0}
				<section class="rounded-card border border-line bg-surface p-4">
					<div class="flex flex-wrap items-center justify-between gap-2">
						<h2 class="text-13 font-bold text-text">Settlement Paper Terbaru (poly-agent)</h2>
						<span class="font-mono text-10 text-text-3">5 penyelesaian terakhir · detail lengkap di tab Eksekusi</span>
					</div>
					<div class="mt-2 overflow-x-auto">
						<table class="w-full text-left font-mono text-11">
							<thead class="border-b border-line text-10 text-text-3">
								<tr>
									<th class="px-2 py-1.5">Waktu</th>
									<th class="px-2 py-1.5">Kontrak</th>
									<th class="px-2 py-1.5">Arah</th>
									<th class="px-2 py-1.5 text-right">Harga Entry</th>
									<th class="px-2 py-1.5 text-right">Skor</th>
									<th class="px-2 py-1.5 text-right">Hasil & PnL</th>
									<th class="px-2 py-1.5 text-right">Saldo Setelah</th>
								</tr>
							</thead>
							<tbody class="divide-y divide-line-soft">
								{#each settledList.slice(0, 5) as s, idx (`${s.key}-${idx}`)}
									<tr class="hover:bg-surface-2/60">
										<td class="px-2 py-1.5 text-text-3">{waktuTs(s.ts)}</td>
										<td class="px-2 py-1.5 font-bold uppercase text-text">{s.coin ?? '—'} <span class="font-normal text-10 text-text-3">{s.key ?? ''}</span></td>
										<td class="px-2 py-1.5 {s.side === 'Up' ? 'text-pos' : 'text-warn'}">{s.side ?? '—'}</td>
										<td class="px-2 py-1.5 text-right text-text">{angka(s.price, 2)}</td>
										<td class="px-2 py-1.5 text-right text-text-2">{angka(s.score, 3)}</td>
										<td class="px-2 py-1.5 text-right font-bold {s.won ? 'text-pos' : 'text-neg'}">
											{s.won ? 'MENANG' : 'KALAH'} ({usdSigned(s.pnl)})
										</td>
										<td class="px-2 py-1.5 text-right text-text">{usd(s.balanceAfter)}</td>
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				</section>
			{/if}

			<BatasPasar market="polymarket" />
		</div>

	{:else if sub === 'sinyal'}
		<div class="space-y-4">
			<!-- Parameter Konfigurasi & Bobot Sinyal AI Agent -->
			<section class="rounded-card border border-line bg-surface p-4">
				<div class="flex flex-wrap items-center justify-between gap-2">
					<div>
						<h2 class="text-13 font-bold text-text">Konfigurasi & Bobot Sinyal Poly-Agent (v{agenCfg?.version ?? '—'})</h2>
						<p class="mt-0.5 text-11 text-text-3">
							Parameter aktif yang dipakai mesin <code class="font-mono">poly-agent</code> untuk menilai window 5 menit BTC & ETH.
						</p>
					</div>
					<span class="font-mono text-10 text-text-3">
						diperbarui: {waktuTs(agenCfg?.updated)}
					</span>
				</div>

				{#if agenCfg}
					<div class="mt-3 grid gap-3 sm:grid-cols-3 lg:grid-cols-6 font-mono text-12">
						<div class="rounded border border-line bg-surface-2 p-2.5">
							<div class="label-mikro text-text-3">THRESHOLD SKOR</div>
							<div class="mt-1 text-15 font-bold text-accent">{angka(agenCfg.threshold, 2)}</div>
						</div>
						<div class="rounded border border-line bg-surface-2 p-2.5">
							<div class="label-mikro text-text-3">BOBOT MOMENTUM</div>
							<div class="mt-1 text-15 font-bold text-text">{angka(agenCfg.weights?.mom, 3)}</div>
						</div>
						<div class="rounded border border-line bg-surface-2 p-2.5">
							<div class="label-mikro text-text-3">BOBOT ORDERBOOK</div>
							<div class="mt-1 text-15 font-bold text-text">{angka(agenCfg.weights?.book, 3)}</div>
						</div>
						<div class="rounded border border-line bg-surface-2 p-2.5">
							<div class="label-mikro text-text-3">BOBOT PRICE BAND</div>
							<div class="mt-1 text-15 font-bold text-text">{angka(agenCfg.weights?.band, 3)}</div>
						</div>
						<div class="rounded border border-line bg-surface-2 p-2.5">
							<div class="label-mikro text-text-3">RENTANG ODDS</div>
							<div class="mt-1 text-14 font-bold text-text">{agenCfg.entryLo ?? '—'} – {agenCfg.entryHi ?? '—'}</div>
						</div>
						<div class="rounded border border-line bg-surface-2 p-2.5">
							<div class="label-mikro text-text-3">UKURAN & LOSS CAP</div>
							<div class="mt-1 text-14 font-bold text-text">${agenCfg.sizeUsd ?? 5} / cap ${agenCfg.dailyLossCap ?? 10}</div>
						</div>
					</div>
				{:else}
					<p class="mt-2 text-12 text-text-3">Konfigurasi poly-agent belum terbaca dari fakta.</p>
				{/if}
			</section>

			<!-- Evaluasi Kandidat & Alasan Penolakan Terakhir -->
			{#if eventsList.length > 0}
				<section class="rounded-card border border-line bg-surface p-4">
					<div class="flex flex-wrap items-center justify-between gap-2">
						<div>
							<h2 class="text-13 font-bold text-text">Aliran Evaluasi Kandidat Terbaru (agent-events.jsonl)</h2>
							<p class="mt-0.5 text-11 text-text-3">
								Keputusan per window 5 menit beserta alasan filter ketika sinyal ditahan.
							</p>
						</div>
						<span class="font-mono text-10 text-text-3">{eventsList.length} event terakhir</span>
					</div>
					<div class="mt-2 overflow-x-auto">
						<table class="w-full text-left font-mono text-11">
							<thead class="border-b border-line text-10 text-text-3">
								<tr>
									<th class="px-2 py-1.5">Waktu</th>
									<th class="px-2 py-1.5">Koin</th>
									<th class="px-2 py-1.5">Window Key</th>
									<th class="px-2 py-1.5">Detik Berjalan</th>
									<th class="px-2 py-1.5">Keputusan / Alasan Filter</th>
								</tr>
							</thead>
							<tbody class="divide-y divide-line-soft">
								{#each eventsList.slice(0, 10) as ev, i (`${ev.key}-${i}`)}
									<tr>
										<td class="px-2 py-1.5 text-text-3">{waktuTs(ev.ts)}</td>
										<td class="px-2 py-1.5 font-bold uppercase text-text">{ev.coin ?? '—'}</td>
										<td class="px-2 py-1.5 text-text-2">{ev.key ?? '—'}</td>
										<td class="px-2 py-1.5 text-text-3">{ev.elapsed != null ? `${ev.elapsed}s` : '—'}</td>
										<td class="px-2 py-1.5">
											<span class="rounded border border-line bg-surface-2 px-1.5 py-0.5 text-10 text-text-2">
												{ev.reason ?? ev.kind ?? '—'}
											</span>
										</td>
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				</section>
			{/if}

			<!-- Pembelajaran Otomatis (Lessons Applied & Rejected) -->
			<section class="rounded-card border border-line bg-surface p-4">
				<div class="flex flex-wrap items-center justify-between gap-2">
					<div>
						<h2 class="text-13 font-bold text-text">Jurnal Self-Tuning & Guardrail Bounds (agent-lessons.jsonl)</h2>
						<p class="mt-0.5 text-11 text-text-3">
							Setiap usulan perubahan bobot yang melanggar batas aman (<code class="font-mono">bounds</code>) ditolak otomatis oleh harness.
						</p>
					</div>
					<span class="font-mono text-10 text-text-3">
						total lessons: {agen?.lessons?.n ?? 0} · upgrades: {agen?.upgrades?.n ?? 0}
					</span>
				</div>
				<div class="mt-3 grid gap-4 sm:grid-cols-2">
					<div>
						<div class="label-mikro font-mono text-pos">PARAMETER DITERAPKAN TERAKHIR</div>
						{#if diterapkanList.length === 0}
							<p class="mt-1 text-11 text-text-3">Belum ada riwayat penerapan parameter.</p>
						{:else}
							<ul class="mt-1.5 divide-y divide-line-soft font-mono text-11">
								{#each diterapkanList.slice(-6).reverse() as item, idx (idx)}
									<li class="flex items-center justify-between py-1">
										<span class="font-bold text-text">{item.kunci}</span>
										<span class="text-10 text-text-3">{waktuTs(item.label ?? item.ts)}</span>
									</li>
								{/each}
							</ul>
						{/if}
					</div>
					<div>
						<div class="label-mikro font-mono text-warn">USULAN DITOLAK GUARDRAIL BOUNDS</div>
						{#if ditolakList.length === 0}
							<p class="mt-1 text-11 text-text-3">Tidak ada penolakan parameter.</p>
						{:else}
							<ul class="mt-1.5 divide-y divide-line-soft font-mono text-11">
								{#each ditolakList.slice(-6).reverse() as item, idx (idx)}
									<li class="flex items-center justify-between py-1">
										<span class="text-text">{item.kunci} = <b class="text-warn">{item.nilai}</b></span>
										<span class="text-10 text-text-3">{item.alasan}</span>
									</li>
								{/each}
							</ul>
						{/if}
					</div>
				</div>
			</section>

			<!-- Alternatif Strategi: PolyBTC 5m Momentum -->
			<section class="rounded-card border border-line bg-surface p-4">
				<h2 class="mb-2 text-13 font-bold text-text">Strategi Alternatif · PolyBTC 5m Momentum</h2>
				<PolyAltBtc5m nilai={polyAlt} fakta={polyAltFakta} />
			</section>
		</div>

	{:else if sub === 'uji'}
		<div class="space-y-4">
			<!-- Gate Evaluasi Statistik Wilson 95% + deff -->
			{#if payload}
				<section class="rounded-card border border-line bg-surface p-4">
					<h2 class="mb-2 text-13 font-bold text-text">Evaluasi Gate Statistik (Wilson 95% + Koreksi Klaster deff)</h2>
					<GateBlok data={payload} />
				</section>
			{/if}

			<!-- Parity Drift: Mirror vs Pilot Executor -->
			<section class="rounded-card border border-line bg-surface p-4">
				<div class="flex flex-wrap items-center justify-between gap-2">
					<div>
						<h2 class="text-13 font-bold text-text">Parity Drift · Mirror vs Pilot Executor</h2>
						<p class="mt-0.5 text-11 text-text-3">
							Memastikan keputusan masuk/tolak di mesin mirror konsisten dengan eksekutor pilot sebelum gate live dibuka.
						</p>
					</div>
					<span class="rounded border border-line bg-surface-2 px-2 py-0.5 font-mono text-10 text-text-2">
						status: {drift?.status ?? '—'}
					</span>
				</div>
				{#if drift}
					<div class="mt-3 grid gap-3 sm:grid-cols-3 font-mono text-12">
						<div class="rounded border border-line bg-surface-2 p-3">
							<div class="label-mikro text-text-3">KEPUTUSAN MIRROR (EKOR 400)</div>
							<div class="mt-1 text-15 font-bold text-text">{drift.mirror_n ?? 0}</div>
						</div>
						<div class="rounded border border-line bg-surface-2 p-3">
							<div class="label-mikro text-text-3">KEPUTUSAN EKSEKUTOR PILOT</div>
							<div class="mt-1 text-15 font-bold text-text">{drift.executor_n ?? 0}</div>
						</div>
						<div class="rounded border border-line bg-surface-2 p-3">
							<div class="label-mikro text-text-3">SELISIH KEPUTUSAN (DRIFT)</div>
							<div class="mt-1 text-15 font-bold {(drift.drift ?? 0) > 0 ? 'text-warn' : 'text-pos'}">
								{drift.status === 'ok' ? drift.drift : '—'}
							</div>
						</div>
					</div>
					{#if drift.detail}
						<p class="mt-2 font-mono text-11 text-text-3">{drift.detail}</p>
					{/if}
				{/if}
			</section>

			<!-- Katalog Dataset Recorder -->
			<section class="rounded-card border border-line bg-surface p-4">
				<h2 class="mb-2 text-13 font-bold text-text">Katalog Dataset Riset & Cakupan Baca</h2>
				<DatasetExplorer recorder={recorderFakta} cakupan={cakupanFakta} />
			</section>
		</div>

	{:else if sub === 'eksekusi'}
		<div class="space-y-4">
			<!-- Status 3-Way Live Arming & Rekonsiliasi Klaim -->
			<section class="grid gap-3 sm:grid-cols-2">
				<div class="rounded-card border border-line bg-surface p-4">
					<div class="flex items-center justify-between">
						<h2 class="text-13 font-bold text-text">Gerbang Eksekusi Live (3-Way Arming)</h2>
						<span class="rounded border px-2 py-0.5 font-mono text-10 font-bold {arming?.armed ? 'border-pos/40 bg-pos/10 text-pos' : 'border-line bg-surface-2 text-text-3'}">
							{arming?.armed ? 'LIVE ARMED' : 'PAPER ONLY (DISARMED)'}
						</span>
					</div>
					<p class="mt-1 text-11 text-text-3">
						{arming?.detail ?? 'Eksekusi live CLOB ditangguhkan sementara sampai keempat syarat arming terpenuhi.'}
					</p>
					{#if arming?.checks?.length}
						<ul class="mt-2.5 space-y-1 font-mono text-11">
							{#each arming.checks as c, i (i)}
								<li class="flex items-center justify-between border-t border-line-soft pt-1">
									<span class="text-text-2">{c.name ?? c.check ?? `syarat-${i + 1}`}</span>
									<span class={c.ok ? 'text-pos font-bold' : 'text-text-3'}>
										{c.ok ? 'SIAP' : (c.reason ?? 'TERKUNCI')}
									</span>
								</li>
							{/each}
						</ul>
					{/if}
				</div>

				<div class="rounded-card border border-line bg-surface p-4">
					<div class="flex items-center justify-between">
						<h2 class="text-13 font-bold text-text">Rekonsiliasi Klaim Pilot & On-Chain</h2>
						<span class="rounded border border-line bg-surface-2 px-2 py-0.5 font-mono text-10 text-text-2">
							mode: {klaim?.mode ?? 'manual'}
						</span>
					</div>
					<div class="mt-2 grid grid-cols-2 gap-2 font-mono text-12">
						<div>
							<div class="label-mikro text-text-3">CATATAN KLAIM PILOT</div>
							<div class="mt-0.5 text-14 font-bold text-text">{usd(klaim?.klaim)}</div>
						</div>
						<div>
							<div class="label-mikro text-text-3">VERIFIKASI ON-CHAIN</div>
							<div class="mt-0.5 text-12 font-bold {klaim?.terverifikasi ? 'text-pos' : 'text-warn'}">
								{klaim?.terverifikasi ? 'TERVERIFIKASI' : 'BELUM DIVERIFIKASI'}
							</div>
						</div>
					</div>
					<p class="mt-2 text-11 text-text-3">
						{klaim?.keterangan ?? 'Penarikan dilakukan manual lewat dashboard Polymarket.'}
					</p>
				</div>
			</section>

			<!-- Riwayat Settlement Paper Poly-Agent (25 terbaru) -->
			<section class="rounded-card border border-line bg-surface p-4">
				<div class="flex flex-wrap items-center justify-between gap-2">
					<div>
						<h2 class="text-13 font-bold text-text">Ledger Settlement Paper · Poly-Agent ({agenState?.settled ?? settledList.length} total)</h2>
						<p class="mt-0.5 text-11 text-text-3">
							Catatan penyelesaian window 5m dari <code class="font-mono">/var/lib/poly-agent/agent-settled.jsonl</code> (resolusi Gamma outcomePrices).
						</p>
					</div>
					<span class="font-mono text-10 text-text-3">menampilkan {settledList.length} terbaru</span>
				</div>

				{#if settledList.length === 0}
					<p class="mt-3 text-12 text-text-3">Belum ada baris settlement paper yang terbaca.</p>
				{:else}
					<div class="mt-3 overflow-x-auto">
						<table class="w-full text-left font-mono text-11">
							<thead class="border-b border-line text-10 text-text-3">
								<tr>
									<th class="px-2 py-1.5">Waktu</th>
									<th class="px-2 py-1.5">Kontrak</th>
									<th class="px-2 py-1.5">Sisi</th>
									<th class="px-2 py-1.5 text-right">Entry</th>
									<th class="px-2 py-1.5 text-right">Cost</th>
									<th class="px-2 py-1.5 text-right">Payout</th>
									<th class="px-2 py-1.5 text-right">PnL</th>
									<th class="px-2 py-1.5 text-right">Skor (Mom/Book)</th>
									<th class="px-2 py-1.5 text-right">Saldo</th>
								</tr>
							</thead>
							<tbody class="divide-y divide-line-soft">
								{#each settledList as s, idx (`${s.key}-${idx}`)}
									<tr class="hover:bg-surface-2/60">
										<td class="px-2 py-1.5 text-text-3">{waktuTs(s.ts)}</td>
										<td class="px-2 py-1.5 font-bold uppercase text-text">{s.coin ?? '—'} <span class="font-normal text-10 text-text-3">{s.key ?? ''}</span></td>
										<td class="px-2 py-1.5 {s.side === 'Up' ? 'text-pos' : 'text-warn'}">{s.side ?? '—'}</td>
										<td class="px-2 py-1.5 text-right text-text">{angka(s.price, 2)}</td>
										<td class="px-2 py-1.5 text-right text-text-2">{usd(s.cost)}</td>
										<td class="px-2 py-1.5 text-right text-text-2">{usd(s.payout)}</td>
										<td class="px-2 py-1.5 text-right font-bold {s.won ? 'text-pos' : 'text-neg'}">
											{usdSigned(s.pnl)}
										</td>
										<td class="px-2 py-1.5 text-right text-text-3">
											{angka(s.score, 3)}
											{#if s.signals}
												<span class="text-10">({angka(s.signals.mom, 2)}/{angka(s.signals.book, 2)})</span>
											{/if}
										</td>
										<td class="px-2 py-1.5 text-right text-text">{usd(s.balanceAfter)}</td>
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				{/if}
			</section>

			<!-- Riwayat Paper Ledger Alternatif PolyBTC 5m -->
			{#if polyAltLedger.length > 0}
				<section class="rounded-card border border-line bg-surface p-4">
					<div class="flex flex-wrap items-center justify-between gap-2">
						<div>
							<h2 class="text-13 font-bold text-text">Paper Ledger · Alternatif PolyBTC 5m Momentum</h2>
							<p class="mt-0.5 text-11 text-text-3">
								Keputusan dry-run dari <code class="font-mono">polymarket-btc-5m/runtime/paper_ledger.jsonl</code> ({polyAlt?.ledger?.menang ?? 0}W / {polyAlt?.ledger?.kalah ?? 0}L · total PnL {usdSigned(polyAlt?.ledger?.pnl_usd)}).
							</p>
						</div>
					</div>
					<div class="mt-3 overflow-x-auto">
						<table class="w-full text-left font-mono text-11">
							<thead class="border-b border-line text-10 text-text-3">
								<tr>
									<th class="px-2 py-1.5">Waktu</th>
									<th class="px-2 py-1.5">Market Slug</th>
									<th class="px-2 py-1.5">Arah</th>
									<th class="px-2 py-1.5 text-right">Entry</th>
									<th class="px-2 py-1.5 text-right">Stake</th>
									<th class="px-2 py-1.5 text-right">Hasil Paper</th>
									<th class="px-2 py-1.5 text-right">PnL</th>
								</tr>
							</thead>
							<tbody class="divide-y divide-line-soft">
								{#each polyAltLedger as r, idx (`${r.slug}-${idx}`)}
									<tr class="hover:bg-surface-2/60">
										<td class="px-2 py-1.5 text-text-3">{waktuTs(r.ts)}</td>
										<td class="px-2 py-1.5 text-text">{r.slug ?? '—'}</td>
										<td class="px-2 py-1.5 font-bold {r.side === 'UP' ? 'text-pos' : 'text-warn'}">{r.side ?? '—'}</td>
										<td class="px-2 py-1.5 text-right text-text">{angka(r.entry_price, 2)}</td>
										<td class="px-2 py-1.5 text-right text-text-2">{usd(r.stake_usd)}</td>
										<td class="px-2 py-1.5 text-right font-bold {r.hasil_paper === 'MENANG' ? 'text-pos' : r.hasil_paper === 'KALAH' ? 'text-neg' : 'text-text-3'}">
											{r.hasil_paper ?? '—'}
										</td>
										<td class="px-2 py-1.5 text-right font-bold {(r.pnl_usd ?? 0) > 0 ? 'text-pos' : (r.pnl_usd ?? 0) < 0 ? 'text-neg' : 'text-text-3'}">
											{usdSigned(r.pnl_usd)}
										</td>
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				</section>
			{/if}
		</div>
	{/if}
</MarketShell>
