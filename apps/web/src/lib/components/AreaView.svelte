<script lang="ts">
	// Halaman Area Terpadu: Menyajikan tampilan khusus per instrumen pasar
	// (Crypto, Polymarket, IDX, Forex, GMGN) dengan kartu visual trading modern,
	// sambil tetap menyediakan tab dataset, gate, dan audit fakta.
	import { AREAS } from '$lib/nav';
	import { page } from '$app/state';
	import { live } from '$lib/api/live.svelte';
	import { teksNilai, umurDetik, angka } from '$lib/format';
	import AreaLoader from './AreaLoader.svelte';
	import Block from './Block.svelte';
	import SubNav from './SubNav.svelte';
	import NilaiFakta from './NilaiFakta.svelte';
	import DataTable from './DataTable.svelte';
	import EventFeed from './EventFeed.svelte';
	import GateBlok from './GateBlok.svelte';
	import DatasetExplorer from './DatasetExplorer.svelte';
	import SignalCard from './SignalCard.svelte';
	import RiskMeter from './RiskMeter.svelte';
	import EquityCurve from './EquityCurve.svelte';
	import StatisticalEdgeCard from './StatisticalEdgeCard.svelte';
	import type { Fakta } from '$lib/api/types';

	interface Props {
		kunci: string;
	}
	let { kunci }: Props = $props();

	const area = $derived(AREAS.find((a) => a.kunci === kunci)!);
	let sub = $state(page.url.searchParams.get('sub') ?? area.anak[0]?.slug ?? '');
	const anak = $derived(area.anak.find((a) => a.slug === sub) ?? area.anak[0] ?? null);

	const topikArea: Record<string, string[]> = {
		crypto: ['signal.', 'verdict.', 'trade.', 'gate.', 'llm.'],
		idx: ['signal.', 'alert.'],
		forex: ['signal.', 'alert.'],
		polymarket: ['verdict.', 'gate.', 'trade.', 'alert.'],
		gmgn: ['signal.', 'trade.', 'alert.']
	};

	const tampilGate = $derived(['polymarket', 'crypto', 'idx'].includes(kunci));

	const kolomFakta = [
		{ kunci: 'kunci', label: 'kunci' },
		{ kunci: 'nilai', label: 'nilai' },
		{ kunci: 'sumber', label: 'sumber' },
		{ kunci: 'umur', label: 'umur' },
		{ kunci: 'status', label: 'status' }
	];

	let tampilRaw = $state(false);

	function temukanFakta(facts: Fakta[], key: string): Fakta | null {
		return facts.find((f) => f.key === key) ?? null;
	}
</script>

<div class="space-y-4">
	<!-- Header Area -->
	<div class="flex flex-wrap items-center justify-between gap-3 border-b border-line pb-3">
		<div>
			<div class="flex items-center gap-2">
				<h1 class="text-26 font-bold tracking-tight text-text font-display">{area.label}</h1>
				<span class="rounded bg-surface px-2 py-0.5 text-11 font-mono uppercase text-accent border border-line">
					{area.kunci}
				</span>
			</div>
			{#if anak}
				<p class="text-12 text-text-3 mt-0.5">{anak.label} — {anak.catatan}</p>
			{/if}
		</div>

		<!-- Tombol Mode Inspeksi Mentah -->
		<button
			type="button"
			class="rounded-control border border-line bg-surface px-3 py-1.5 text-11 text-text-3 hover:text-text hover:border-line-soft transition-colors"
			onclick={() => (tampilRaw = !tampilRaw)}
		>
			{tampilRaw ? 'Tutup Inspeksi Mentah' : '🔍 Inspeksi Fakta Mentah'}
		</button>
	</div>

	<!-- Sub-navigasi Tabs -->
	{#if area.anak.length}
		<SubNav {area} aktif={sub} onpilih={(s) => (sub = s)} />
	{/if}

	<AreaLoader area={kunci}>
		{#snippet children(data)}
			{@const faktaKandidat = temukanFakta(data.facts, 'kandidat')}
			{@const faktaRisiko = temukanFakta(data.facts, 'risiko')}
			{@const faktaEquity = temukanFakta(data.facts, 'equity')}
			{@const faktaLedger = temukanFakta(data.facts, 'ledger')}
			{@const faktaVerdict = temukanFakta(data.facts, 'verdict')}
			{@const faktaPolyPaper = temukanFakta(data.facts, 'poly_paper')}
			{@const datasetRecorder = temukanFakta(data.facts, 'recorder')}
			{@const datasetCakupan = temukanFakta(data.facts, 'cakupan')}

			{@const kandidatArray = Array.isArray(faktaKandidat?.value) ? faktaKandidat.value : []}
			{@const equityObj = (faktaEquity?.value as { points?: { i: number; r: number }[]; stats?: Record<string, number> }) ?? null}
			{@const risikoObj = (faktaRisiko?.value as Record<string, unknown>) ?? null}
			{@const verdictObj = (faktaVerdict?.value as Record<string, unknown>) ?? null}
			{@const polyPaperObj = (faktaPolyPaper?.value as { arms?: { nama: string; balance: number; pnl: number; wins: number; losses: number }[] }) ?? null}

			<!-- ========================================== -->
			<!-- VIEW KHUSUS: CRYPTO                      -->
			<!-- ========================================== -->
			{#if kunci === 'crypto'}
				{#if sub === 'cockpit' || sub === 'setup' || !sub}
					<div class="grid grid-cols-1 gap-4 lg:grid-cols-12">
						<!-- Kolom Kiri: Sinyal & Equity (7 cols) -->
						<div class="space-y-4 lg:col-span-7">
							{#if sub === 'cockpit'}
								<EquityCurve points={equityObj?.points} stats={equityObj?.stats} />
							{/if}

							<div class="permukaan-2 rounded-card border border-line p-3">
								<div class="mb-3 flex items-center justify-between border-b border-line-soft pb-2">
									<div>
										<h3 class="text-14 font-medium text-text">Kandidat Setup SMC</h3>
										<p class="text-11 text-text-3">Kandidat trade hasil screening multi-timeframe</p>
									</div>
									<span class="rounded bg-surface px-2 py-0.5 text-11 font-mono text-accent border border-line">
										{kandidatArray.length} setup
									</span>
								</div>

								{#if kandidatArray.length === 0}
									<div class="p-6 text-center text-text-3">
										<p class="text-12">Tidak ada kandidat setup yang aktif saat ini.</p>
									</div>
								{:else}
									<div class="space-y-2.5">
										{#each kandidatArray as s (s.pair + String(s.entry))}
											<SignalCard setup={s} />
										{/each}
									</div>
								{/if}
							</div>
						</div>

						<!-- Kolom Kanan: Risiko & Posisi (5 cols) -->
						<div class="space-y-4 lg:col-span-5">
							<RiskMeter risiko={risikoObj} />

							<!-- Status Posisi Terbuka -->
							<div class="permukaan-2 rounded-card border border-line p-3">
								<div class="mb-2 flex items-center justify-between border-b border-line-soft pb-2">
									<h3 class="text-13 font-medium text-text">Posisi Terbuka</h3>
									<span class="text-11 text-text-3 font-mono">
										{Number(risikoObj?.posisi_terbuka ?? 0)} / {Number(risikoObj?.maks_posisi ?? 3)}
									</span>
								</div>
								{#if Number(risikoObj?.posisi_terbuka ?? 0) === 0}
									<div class="py-4 text-center text-text-3 text-12">
										Tidak ada posisi terbuka saat ini.
									</div>
								{/if}
							</div>
						</div>
					</div>
				{/if}
			{/if}

			<!-- ========================================== -->
			<!-- VIEW KHUSUS: POLYMARKET                  -->
			<!-- ========================================== -->
			{#if kunci === 'polymarket'}
				{#if sub === 'dataset'}
					<Block
						judul="Katalog dataset"
						deskripsi="poly.dataset/recorder + poly.akses/cakupan — angka apa adanya dari job poly-sync"
						sumber={datasetRecorder?.source ?? null}
						age_s={datasetRecorder?.age_s ?? null}
						status={datasetRecorder?.status ?? null}
					>
						<DatasetExplorer recorder={datasetRecorder} cakupan={datasetCakupan} />
					</Block>
				{:else if sub === 'verdict' || sub === 'arm' || !sub}
					<div class="grid grid-cols-1 gap-4 lg:grid-cols-12">
						<div class="space-y-4 lg:col-span-6">
							<StatisticalEdgeCard verdict={verdictObj} judul="Polymarket 5m Statistical Verdict" />
						</div>

						<div class="space-y-4 lg:col-span-6">
							{#if polyPaperObj?.arms && polyPaperObj.arms.length}
								<div class="permukaan-2 rounded-card border border-line p-3">
									<h3 class="text-13 font-medium text-text mb-2 border-b border-line-soft pb-2">
										Kinerja Multi-Arm Bandit (A/B/C/D)
									</h3>
									<div class="grid grid-cols-2 gap-2 text-11">
										{#each polyPaperObj.arms as arm}
											<div class="rounded border border-line bg-surface p-2">
												<div class="flex justify-between items-center mb-1">
													<span class="font-bold text-text">{arm.nama}</span>
													<span class="angka font-bold {arm.pnl >= 0 ? 'text-pos' : 'text-neg'}">
														{arm.pnl >= 0 ? '+' : ''}{angka(arm.pnl)}
													</span>
												</div>
												<div class="flex justify-between text-10 text-text-3">
													<span>Sal: {angka(arm.balance)}</span>
													<span>{arm.wins}W / {arm.losses}L</span>
												</div>
											</div>
										{/each}
									</div>
								</div>
							{/if}
						</div>
					</div>
				{/if}
			{/if}

			<!-- Gate Blok Evaluasi -->
			{#if tampilGate && sub !== 'dataset'}
				<Block
					judul="Evaluasi Gate Statistik"
					deskripsi="Keputusan lolos hanya bila batas bawah CI > BE (ADR-003)."
				>
					<GateBlok {data} />
				</Block>
			{/if}

			{@const faktaTerpilih = anak && anak.kunci.length
				? data.facts.filter((f) => anak.kunci.includes(f.key))
				: data.facts}
			{@const barisFakta = data.facts.map((f) => ({
				kunci: f.key,
				nilai: teksNilai(f.value).slice(0, 100),
				sumber: f.source,
				umur: umurDetik(f.age_s),
				status: f.status
			}))}

			{#if tampilRaw || (kunci !== 'crypto' && kunci !== 'polymarket')}
				<div class="space-y-3">
					<div class="border-t border-line-soft pt-3">
						<h3 class="text-13 font-medium text-text mb-2">Blok Data Area</h3>
					</div>

					{#if faktaTerpilih.length === 0}
						<Block judul={`Blok ${anak?.label ?? area.label}`} kosong
							kosongPesan="Belum ada fakta untuk sub ini. Tampilkan —, bukan 0." />
					{:else}
						{#each faktaTerpilih as f (f.key)}
							<Block judul={f.key} deskripsi={`kind ${f.kind}`} sumber={f.source} age_s={f.age_s} status={f.status}>
								<NilaiFakta fakta={f} />
							</Block>
						{/each}
					{/if}

					<!-- Tabel Data Mentah -->
					<Block judul="Daftar Fakta Area" deskripsi={`${data.facts.length} fakta · sumber & umur ditampilkan apa adanya`}>
						<DataTable
							kolom={kolomFakta}
							baris={barisFakta}
							cari="cari kunci/nilai/sumber…"
							ekspor={`${kunci}-fakta.csv`}
						/>
					</Block>
				</div>
			{/if}

			<!-- Aliran Kejadian SSE untuk Area ini -->
			<Block judul="Kejadian Area" deskripsi="Aliran SSE terfilter topik area.">
				<EventFeed
					kejadian={live.berdasarkanTopik(topikArea[kunci] ?? [])}
					memuat={live.status === 'menyambung'}
					galat={live.pesan}
				/>
			</Block>
		{/snippet}
	</AreaLoader>
</div>