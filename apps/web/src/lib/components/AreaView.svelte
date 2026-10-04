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
	let sub = $state(page.url.searchParams.get('sub') ?? area?.anak[0]?.slug ?? '');
	const anak = $derived(area?.anak.find((a) => a.slug === sub) ?? area?.anak[0] ?? null);

	const topikArea: Record<string, string[]> = {
		crypto: ['signal.', 'verdict.', 'trade.', 'gate.', 'llm.'],
		idx: ['signal.', 'alert.'],
		forex: ['signal.', 'alert.'],
		polymarket: ['verdict.', 'gate.', 'trade.', 'alert.'],
		gmgn: ['signal.', 'trade.', 'alert.']
	};

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

	const rp = (n?: number | null) =>
		n == null ? '—' : `Rp ${n.toLocaleString('id-ID', { maximumFractionDigits: 0 })}`;
	const jt = (n?: number | null) =>
		n == null ? '—' : `${n > 0 ? '+' : ''}${n.toLocaleString('id-ID', { maximumFractionDigits: 1 })} Jt`;

	function getWIBHour(): number {
		const now = new Date();
		return (now.getUTCHours() + 7) % 24;
	}

	function statusSesi(jamMulai: number, jamSelesai: number, sekarangJam: number): boolean {
		if (jamMulai <= jamSelesai) {
			return sekarangJam >= jamMulai && sekarangJam < jamSelesai;
		}
		return sekarangJam >= jamMulai || sekarangJam < jamSelesai;
	}

	const wibHour = $derived(getWIBHour());
</script>

<div class="space-y-4">
	<!-- Header Area -->
	<div class="flex flex-wrap items-center justify-between gap-3 border-b border-line pb-3">
		<div>
			<div class="flex items-center gap-2">
				<h1 class="text-26 font-bold tracking-tight text-text font-display">{area?.label ?? kunci}</h1>
				<span class="rounded bg-surface px-2 py-0.5 text-11 font-mono uppercase text-accent border border-line">
					{area?.kunci ?? kunci}
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
	{#if area?.anak?.length}
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
			{@const faktaBagian = temukanFakta(data.facts, 'bagian')}
			{@const faktaRadar = temukanFakta(data.facts, 'radar')}
			{@const faktaLpPaper = temukanFakta(data.facts, 'lp_paper')}
			{@const faktaGmgn = temukanFakta(data.facts, 'gmgn')}

			{@const bagianObj = (faktaBagian?.value as Record<string, any>) ?? {}}
			{@const idxArjum = (bagianObj?.idx?.rows as any[]) ?? []}
			{@const idxTv = (bagianObj?.idx_tv?.rows as any[]) ?? []}
			{@const idxBandar = (bagianObj?.bandarmologi as any) ?? null}
			{@const idx616 = (bagianObj?.idx616?.terbuka as any[]) ?? []}
			{@const forexObj = (bagianObj?.forex as any) ?? null}
			{@const macroObj = (bagianObj?.macro as any) ?? null}
			{@const memecoinObj = (bagianObj?.memecoin as any) ?? null}
			{@const radarObj = (faktaRadar?.value as any) ?? null}
			{@const lpPaperObj = (faktaLpPaper?.value as any) ?? null}
			{@const gmgnObj = (faktaGmgn?.value as any) ?? null}

			{@const kandidatArray = Array.isArray(faktaKandidat?.value) ? faktaKandidat.value : []}
			{@const equityObj = (faktaEquity?.value as { points?: { i: number; r: number }[]; stats?: Record<string, number> }) ?? null}
			{@const risikoObj = (faktaRisiko?.value as Record<string, unknown>) ?? null}
			{@const verdictObj = (faktaVerdict?.value as Record<string, unknown>) ?? null}
			{@const polyPaperObj = (faktaPolyPaper?.value as { arms?: { nama: string; balance: number; pnl: number; wins: number; losses: number }[] }) ?? null}
			{@const tampilGate = Boolean(faktaVerdict || temukanFakta(data.facts, 'gate'))}

			<!-- ========================================== -->
			<!-- VIEW KHUSUS: CRYPTO                      -->
			<!-- ========================================== -->
			{#if kunci === 'crypto'}
				{#if sub === 'cockpit' || sub === 'setup' || !sub}
					<div class="grid grid-cols-1 gap-4 lg:grid-cols-12">
						<!-- Kolom Kiri: Sinyal & Equity (7 cols) -->
						<div class="space-y-4 lg:col-span-7">
							{#if sub === 'cockpit' || !sub}
								<EquityCurve points={equityObj?.points} stats={equityObj?.stats} />
							{/if}

							<div class="permukaan-2 rounded-card border border-line p-3">
								<div class="mb-3 flex items-center justify-between border-b border-line-soft pb-2">
									<div>
										<h3 class="text-14 font-medium text-text">Kandidat Setup SMC Crypto</h3>
										<p class="text-11 text-text-3">Kandidat trade hasil screening multi-timeframe SMC</p>
									</div>
									<span class="rounded bg-surface px-2 py-0.5 text-11 font-mono text-accent border border-line">
										{kandidatArray.length} setup
									</span>
								</div>

								{#if kandidatArray.length === 0}
									<div class="p-6 text-center text-text-3">
										<p class="text-12">Tidak ada kandidat setup crypto yang aktif saat ini.</p>
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

			<!-- ========================================== -->
			<!-- VIEW KHUSUS: IDX (Pasar Saham Indonesia) -->
			<!-- ========================================== -->
			{#if kunci === 'idx'}
				{#if sub === 'screener' || !sub}
					<div class="space-y-4">
						<!-- Arjum Screener -->
						<div class="permukaan-2 rounded-card border border-line p-3">
							<div class="mb-3 flex items-center justify-between border-b border-line-soft pb-2">
								<div>
									<h3 class="text-14 font-medium text-text">Arjum Multi-Factor Stock Screener</h3>
									<p class="text-11 text-text-3">Filter kombinasi broker flow, teknikal, dan probabilitas event</p>
								</div>
								<span class="rounded bg-surface px-2 py-0.5 text-11 font-mono text-accent border border-line">
									{idxArjum.length} saham lolos
								</span>
							</div>

							{#if idxArjum.length === 0}
								<div class="py-6 text-center text-text-3 text-12">
									Tidak ada emiten yang lolos kriteria Arjum screener saat ini.
								</div>
							{:else}
								<div class="overflow-x-auto">
									<table class="w-full text-left text-12">
										<thead class="border-b border-line text-text-3 font-normal text-11 font-mono">
											<tr>
												<th class="py-2 px-2.5">KODE</th>
												<th class="py-2 px-2.5">KATEGORI / BUCKET</th>
												<th class="py-2 px-2.5">SUMMARY SIGNAL</th>
												<th class="py-2 px-2.5 text-right">WR EVENT</th>
												<th class="py-2 px-2.5 text-right">POTENSI</th>
												<th class="py-2 px-2.5 text-right">MAX DD</th>
												<th class="py-2 px-2.5">CATATAN</th>
											</tr>
										</thead>
										<tbody class="divide-y divide-line-soft">
											{#each idxArjum as r (r.stock_code)}
												<tr class="hover:bg-surface/50 transition-colors">
													<td class="py-2 px-2.5">
														<div class="font-bold text-text font-mono">{r.stock_code}</div>
														<div class="text-10 text-text-3 truncate max-w-[120px]">{r.stock_name ?? ''}</div>
													</td>
													<td class="py-2 px-2.5 whitespace-nowrap">
														<span class="rounded px-2 py-0.5 text-11 font-medium border border-line {
															r.bucket?.includes('PANTULAN') ? 'text-amber-400 bg-amber-400/10' :
															r.bucket?.includes('DISTRIBUSI') ? 'text-rose-400 bg-rose-400/10' :
															r.bucket?.includes('SENYAP') ? 'text-cyan-400 bg-cyan-400/10' :
															'text-text-2 bg-surface'
														}">
															{r.bucket ?? '—'}
														</span>
													</td>
													<td class="py-2 px-2.5 text-11 text-text-2 max-w-[280px]">
														{r.summary ?? '—'}
													</td>
													<td class="py-2 px-2.5 text-right font-mono font-medium {r.wr_event != null && r.wr_event >= 60 ? 'text-pos' : 'text-text-2'}">
														{r.wr_event != null ? `${r.wr_event.toFixed(1)}%` : '—'}
													</td>
													<td class="py-2 px-2.5 text-right font-mono text-pos">
														{r.potential != null ? `+${r.potential}%` : '—'}
													</td>
													<td class="py-2 px-2.5 text-right font-mono text-neg">
														{r.drawdown != null ? `${r.drawdown}%` : '—'}
													</td>
													<td class="py-2 px-2.5 text-11 text-text-3">
														{r.note ?? '—'}
													</td>
												</tr>
											{/each}
										</tbody>
									</table>
								</div>
							{/if}
						</div>

						<!-- TradingView Momentum Screener -->
						<div class="permukaan-2 rounded-card border border-line p-3">
							<div class="mb-3 flex items-center justify-between border-b border-line-soft pb-2">
								<div>
									<h3 class="text-14 font-medium text-text">TradingView Momentum & Volume Screener</h3>
									<p class="text-11 text-text-3">Top volume, RSI14, dan status moving average EMA8 vs EMA21</p>
								</div>
								<span class="rounded bg-surface px-2 py-0.5 text-11 font-mono text-accent border border-line">
									{idxTv.length} emiten aktif
								</span>
							</div>

							{#if idxTv.length === 0}
								<div class="py-6 text-center text-text-3 text-12">
									Data TradingView screener belum tersedia.
								</div>
							{:else}
								<div class="overflow-x-auto">
									<table class="w-full text-left text-12">
										<thead class="border-b border-line text-text-3 font-normal text-11 font-mono">
											<tr>
												<th class="py-2 px-2.5">TICKER</th>
												<th class="py-2 px-2.5 text-right">HARGA (RP)</th>
												<th class="py-2 px-2.5 text-right">24H CHG</th>
												<th class="py-2 px-2.5 text-right">VOLUME</th>
												<th class="py-2 px-2.5 text-right">RSI (14)</th>
												<th class="py-2 px-2.5 text-center">EMA STATE</th>
												<th class="py-2 px-2.5 text-right">ATR</th>
											</tr>
										</thead>
										<tbody class="divide-y divide-line-soft font-mono">
											{#each idxTv as t (t.ticker)}
												<tr class="hover:bg-surface/50 transition-colors">
													<td class="py-2 px-2.5 font-bold text-text">{t.ticker}</td>
													<td class="py-2 px-2.5 text-right">{t.close?.toLocaleString('id-ID') ?? '—'}</td>
													<td class="py-2 px-2.5 text-right font-medium {(t.change_pct ?? 0) >= 0 ? 'text-pos' : 'text-neg'}">
														{(t.change_pct ?? 0) >= 0 ? '+' : ''}{(t.change_pct ?? 0).toFixed(2)}%
													</td>
													<td class="py-2 px-2.5 text-right text-text-2">
														{t.volume != null ? `${(t.volume / 1e6).toFixed(1)}M` : '—'}
													</td>
													<td class="py-2 px-2.5 text-right {(t.rsi14 ?? 50) >= 70 ? 'text-warn font-bold' : (t.rsi14 ?? 50) <= 30 ? 'text-pos font-bold' : 'text-text-2'}">
														{t.rsi14?.toFixed(1) ?? '—'}
													</td>
													<td class="py-2 px-2.5 text-center">
														<span class="rounded px-2 py-0.5 text-10 font-sans border border-line {t.ema_state === 'naik' ? 'text-pos bg-pos/10' : 'text-neg bg-neg/10'}">
															{t.ema_state === 'naik' ? '▲ NAIK' : '▼ TURUN'}
														</span>
													</td>
													<td class="py-2 px-2.5 text-right text-text-3">{t.atr?.toFixed(1) ?? '—'}</td>
												</tr>
											{/each}
										</tbody>
									</table>
								</div>
							{/if}
						</div>
					</div>
				{/if}

				<!-- Tab Bandarmologi -->
				{#if sub === 'bandarmologi'}
					<div class="space-y-4">
						<div class="permukaan-2 rounded-card border border-line p-3">
							<div class="mb-3 flex items-center justify-between border-b border-line-soft pb-2">
								<div>
									<h3 class="text-14 font-medium text-text">Bandarmologi & Broker Summary</h3>
									<p class="text-11 text-text-3">Analisis akumulator/distributor, Average Transaction Size (ATS), dan status No-Sell</p>
								</div>
								{#if idxBandar?.hari}
									<span class="rounded bg-surface px-2 py-0.5 text-11 font-mono text-text-3 border border-line">
										Data: {idxBandar.hari}
									</span>
								{/if}
							</div>

							{#if !idxBandar || (idxBandar.hasil ?? []).length === 0}
								<div class="py-6 text-center text-text-3 text-12">
									Belum ada data broker flow yang dihitung untuk siklus ini.
								</div>
							{:else}
								<div class="grid grid-cols-1 md:grid-cols-2 gap-3">
									{#each idxBandar.hasil ?? [] as b (b.kode)}
										<div class="rounded-card border border-line bg-surface p-3 space-y-2">
											<div class="flex items-center justify-between border-b border-line-soft pb-2">
												<div class="flex items-center gap-2">
													<span class="text-16 font-bold text-text font-mono">{b.kode}</span>
													{#if b.no_sell}
														<span class="rounded bg-pos/10 text-pos border border-pos/20 px-2 py-0.5 text-10 font-bold">
															NO SELL
														</span>
													{/if}
												</div>
												<span class="font-mono text-13 font-bold {(b.net_juta ?? 0) >= 0 ? 'text-pos' : 'text-neg'}">
													{(b.net_juta ?? 0) >= 0 ? '+' : ''}{jt(b.net_juta)}
												</span>
											</div>

											<!-- ATS Metrics -->
											<div class="grid grid-cols-2 gap-2 text-11 font-mono">
												<div class="rounded bg-canvas/60 p-2 border border-line">
													<div class="text-10 text-text-3">ATS BELI</div>
													<div class="text-12 font-medium text-pos">{rp(b.ats_beli)}</div>
													<div class="text-10 text-text-3 mt-0.5">{b.frq_beli?.toLocaleString('id-ID') ?? '—'} transaksi</div>
												</div>
												<div class="rounded bg-canvas/60 p-2 border border-line">
													<div class="text-10 text-text-3">ATS JUAL</div>
													<div class="text-12 font-medium text-neg">{rp(b.ats_jual)}</div>
													<div class="text-10 text-text-3 mt-0.5">{b.frq_jual?.toLocaleString('id-ID') ?? '—'} transaksi</div>
												</div>
											</div>

											<!-- Top Broker Breakdown -->
											<div class="space-y-1 pt-1 text-11">
												{#if b.pembeli_teratas}
													<div class="flex items-center justify-between text-text-2">
														<span class="text-text-3">Akumulator Utama:</span>
														<span class="font-mono font-medium text-pos">
															{b.pembeli_teratas.broker} ({b.pembeli_teratas.nama ?? ''})
														</span>
													</div>
												{/if}
												{#if b.penjual_teratas}
													<div class="flex items-center justify-between text-text-2">
														<span class="text-text-3">Distributor Utama:</span>
														<span class="font-mono font-medium text-neg">
															{b.penjual_teratas.broker} ({b.penjual_teratas.nama ?? ''})
														</span>
													</div>
												{/if}
											</div>
										</div>
									{/each}
								</div>
							{/if}
						</div>
					</div>
				{/if}

				<!-- Tab Aliran (Asing vs Lokal) -->
				{#if sub === 'aliran'}
					<div class="space-y-4">
						<div class="permukaan-2 rounded-card border border-line p-3">
							<div class="mb-3 border-b border-line-soft pb-2">
								<h3 class="text-14 font-medium text-text">Dinamika Aliran Institusi & Asing</h3>
								<p class="text-11 text-text-3">Pergerakan modal besar pada emiten radar</p>
							</div>
							<div class="grid grid-cols-1 md:grid-cols-3 gap-3">
								<div class="rounded bg-surface p-3 border border-line">
									<div class="text-11 text-text-3">Total Saham Radar</div>
									<div class="text-20 font-bold text-text font-mono mt-1">{idxArjum.length}</div>
									<div class="text-11 text-text-3 mt-1">Screening Arjum harian</div>
								</div>
								<div class="rounded bg-surface p-3 border border-line">
									<div class="text-11 text-text-3">Emiten Akumulasi Senyap</div>
									<div class="text-20 font-bold text-cyan-400 font-mono mt-1">
										{idxArjum.filter((r) => r.bucket?.includes('SENYAP')).length}
									</div>
									<div class="text-11 text-text-3 mt-1">Tanpa lonjakan volume retail</div>
								</div>
								<div class="rounded bg-surface p-3 border border-line">
									<div class="text-11 text-text-3">Konflik Distribusi</div>
									<div class="text-20 font-bold text-amber-400 font-mono mt-1">
										{idxArjum.filter((r) => r.bucket?.includes('KONFLIK')).length}
									</div>
									<div class="text-11 text-text-3 mt-1">Broker akumulasi vs asing jual</div>
								</div>
							</div>
						</div>
					</div>
				{/if}

				<!-- Tab Watchlist: ARA Hunter Setups -->
				{#if sub === 'watchlist'}
					<div class="space-y-4">
						<div class="permukaan-2 rounded-card border border-line p-3">
							<div class="mb-3 flex items-center justify-between border-b border-line-soft pb-2">
								<div>
									<h3 class="text-14 font-medium text-text">Watchlist Sinyal ARA Hunter (IDX616)</h3>
									<p class="text-11 text-text-3">Setup breakout auto-rejection atas terdaftar dari ledger</p>
								</div>
								<span class="rounded bg-surface px-2 py-0.5 text-11 font-mono text-accent border border-line">
									{idx616.length} setup
								</span>
							</div>

							{#if idx616.length === 0}
								<div class="py-6 text-center text-text-3 text-12">
									Tidak ada setup ARA Hunter yang aktif saat ini.
								</div>
							{:else}
								<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
									{#each idx616 as s, idx (s.ticker + String(idx))}
										<div class="rounded-card border border-line bg-surface p-3 space-y-2">
											<div class="flex items-center justify-between border-b border-line-soft pb-2">
												<div class="flex items-center gap-2">
													<span class="font-bold text-14 text-text font-mono">{s.ticker}</span>
													<span class="rounded bg-pos/10 text-pos px-1.5 py-0.5 text-10 font-bold font-mono">
														{s.direction ?? 'LONG'}
													</span>
												</div>
												<span class="rounded bg-canvas px-2 py-0.5 text-10 font-mono text-text-3 border border-line">
													{s.status ?? 'CREATED'}
												</span>
											</div>
											<div class="grid grid-cols-2 gap-2 text-11 font-mono">
												<div>
													<span class="text-text-3 text-10">ENTRY</span>
													<div class="font-bold text-text">{rp(s.entry_low)}</div>
												</div>
												<div>
													<span class="text-text-3 text-10">STOP LOSS</span>
													<div class="font-bold text-neg">{rp(s.sl)}</div>
												</div>
												<div>
													<span class="text-text-3 text-10">TARGET 1</span>
													<div class="font-bold text-pos">{rp(s.tp1)}</div>
												</div>
												<div>
													<span class="text-text-3 text-10">TARGET 2</span>
													<div class="font-bold text-pos">{rp(s.tp2)}</div>
												</div>
											</div>
										</div>
									{/each}
								</div>
							{/if}
						</div>
					</div>
				{/if}
			{/if}

			<!-- ========================================== -->
			<!-- VIEW KHUSUS: FOREX & KOMODITAS             -->
			<!-- ========================================== -->
			{#if kunci === 'forex'}
				{#if sub === 'struktur' || !sub}
					<div class="grid grid-cols-1 gap-4 lg:grid-cols-12">
						<!-- Cockpit Emas (7 cols) -->
						<div class="space-y-4 lg:col-span-7">
							<div class="permukaan-2 rounded-card border border-line p-3">
								<div class="mb-3 flex items-center justify-between border-b border-line-soft pb-2">
									<div>
										<h3 class="text-14 font-medium text-text">Cockpit Komoditas: Spot Gold (XAU/USD)</h3>
										<p class="text-11 text-text-3">Struktur harga multi-bar, moving average & trend bias</p>
									</div>
									<span class="rounded px-2 py-0.5 text-11 font-bold font-mono uppercase {forexObj?.bias === 'bullish' ? 'text-pos bg-pos/10 border border-pos/20' : 'text-neg bg-neg/10 border border-neg/20'}">
										{forexObj?.bias ?? 'BEARISH'}
									</span>
								</div>

								<div class="grid grid-cols-2 sm:grid-cols-4 gap-2 font-mono mb-3">
									<div class="rounded bg-surface p-2.5 border border-line">
										<div class="text-10 text-text-3">CLOSE</div>
										<div class="text-16 font-bold text-text">${angka(forexObj?.close)}</div>
									</div>
									<div class="rounded bg-surface p-2.5 border border-line">
										<div class="text-10 text-text-3">EMA 20</div>
										<div class="text-14 font-medium text-text-2">${angka(forexObj?.ema20)}</div>
									</div>
									<div class="rounded bg-surface p-2.5 border border-line">
										<div class="text-10 text-text-3">EMA 50</div>
										<div class="text-14 font-medium text-text-2">${angka(forexObj?.ema50)}</div>
									</div>
									<div class="rounded bg-surface p-2.5 border border-line">
										<div class="text-10 text-text-3">ATR (14)</div>
										<div class="text-14 font-medium text-accent">${angka(forexObj?.atr14)} ({forexObj?.atr_pct ?? '—'}%)</div>
									</div>
								</div>

								<div class="rounded bg-surface p-2.5 border border-line text-11 text-text-3">
									Resolusi: {forexObj?.resolution ?? 60}m · Bar dianalisis: {forexObj?.bars ?? 120} bar · Sumber: TVC:GOLD
								</div>
							</div>
						</div>

						<!-- Market Sessions (5 cols) -->
						<div class="space-y-4 lg:col-span-5">
							<div class="permukaan-2 rounded-card border border-line p-3">
								<div class="mb-3 border-b border-line-soft pb-2">
									<h3 class="text-14 font-medium text-text">Sesi Pasar Global (WIB)</h3>
									<p class="text-11 text-text-3">Jadwal pembukaan pasar valuta & likuiditas</p>
								</div>
								<div class="space-y-2 text-11">
									<div class="rounded bg-surface p-2 border border-line flex items-center justify-between">
										<div>
											<div class="font-bold text-text">Sesi Asia (Tokyo & Sydney)</div>
											<div class="text-10 text-text-3">06:00 – 15:00 WIB</div>
										</div>
										<span class="rounded px-2 py-0.5 text-10 font-bold {statusSesi(6, 15, wibHour) ? 'text-pos bg-pos/10 border border-pos/20' : 'text-text-3 bg-canvas'}">
											{statusSesi(6, 15, wibHour) ? 'BUKA' : 'TUTUP'}
										</span>
									</div>
									<div class="rounded bg-surface p-2 border border-line flex items-center justify-between">
										<div>
											<div class="font-bold text-text">Sesi London (Eropa)</div>
											<div class="text-10 text-text-3">14:00 – 23:00 WIB</div>
										</div>
										<span class="rounded px-2 py-0.5 text-10 font-bold {statusSesi(14, 23, wibHour) ? 'text-pos bg-pos/10 border border-pos/20' : 'text-text-3 bg-canvas'}">
											{statusSesi(14, 23, wibHour) ? 'BUKA' : 'TUTUP'}
										</span>
									</div>
									<div class="rounded bg-surface p-2 border border-line flex items-center justify-between">
										<div>
											<div class="font-bold text-text">Sesi New York (Wall Street)</div>
											<div class="text-10 text-text-3">19:00 – 04:00 WIB</div>
										</div>
										<span class="rounded px-2 py-0.5 text-10 font-bold {statusSesi(19, 4, wibHour) ? 'text-pos bg-pos/10 border border-pos/20' : 'text-text-3 bg-canvas'}">
											{statusSesi(19, 4, wibHour) ? 'BUKA' : 'TUTUP'}
										</span>
									</div>
								</div>
							</div>
						</div>
					</div>
				{/if}

				<!-- Tab Kalender Ekonomi -->
				{#if sub === 'kalender'}
					<div class="permukaan-2 rounded-card border border-line p-3">
						<div class="mb-3 flex items-center justify-between border-b border-line-soft pb-2">
							<div>
								<h3 class="text-14 font-medium text-text">Kalender Makroekonomi Global</h3>
								<p class="text-11 text-text-3">Jadwal rilis data ekonomi berdampak tinggi & libur bank</p>
							</div>
							<span class="rounded bg-surface px-2 py-0.5 text-11 font-mono text-accent border border-line">
								{macroObj?.berikutnya?.length ?? 0} agenda
							</span>
						</div>

						{#if !macroObj || (macroObj.berikutnya ?? []).length === 0}
							<div class="py-6 text-center text-text-3 text-12">
								Tidak ada agenda kalender makro yang tercatat.
							</div>
						{:else}
							<div class="overflow-x-auto">
								<table class="w-full text-left text-12">
									<thead class="border-b border-line text-text-3 font-normal text-11 font-mono">
										<tr>
											<th class="py-2 px-2.5">MATA UANG</th>
											<th class="py-2 px-2.5">DAMPAK</th>
											<th class="py-2 px-2.5">AGENDA</th>
											<th class="py-2 px-2.5 text-right">FORECAST</th>
											<th class="py-2 px-2.5 text-right">SEBELUMNYA</th>
										</tr>
									</thead>
									<tbody class="divide-y divide-line-soft">
										{#each (macroObj.berikutnya ?? []).slice(0, 20) as m (m.ts + m.title + m.mata_uang)}
											<tr class="hover:bg-surface/50 transition-colors">
												<td class="py-2 px-2.5 font-bold font-mono text-text">
													<span class="rounded bg-surface px-1.5 py-0.5 border border-line">
														{m.mata_uang ?? '—'}
													</span>
												</td>
												<td class="py-2 px-2.5">
													<span class="rounded px-2 py-0.5 text-10 font-bold border border-line {
														m.impact === 'High' ? 'text-neg bg-neg/10' :
														m.impact === 'Medium' ? 'text-warn bg-warn/10' :
														m.impact === 'Holiday' ? 'text-accent bg-accent/10' :
														'text-text-3 bg-surface'
													}">
														{m.impact ?? '—'}
													</span>
												</td>
												<td class="py-2 px-2.5 font-medium text-text">{m.title ?? '—'}</td>
												<td class="py-2 px-2.5 text-right font-mono text-text-2">{m.forecast || '—'}</td>
												<td class="py-2 px-2.5 text-right font-mono text-text-3">{m.previous || '—'}</td>
											</tr>
										{/each}
									</tbody>
								</table>
							</div>
						{/if}
					</div>
				{/if}
			{/if}

			<!-- ========================================== -->
			<!-- VIEW KHUSUS: GMGN (DEX & MEMECOIN)        -->
			<!-- ========================================== -->
			{#if kunci === 'gmgn'}
				{#if sub === 'radar' || !sub}
					<div class="space-y-4">
						<div class="permukaan-2 rounded-card border border-line p-3">
							<div class="mb-3 flex items-center justify-between border-b border-line-soft pb-2">
								<div>
									<h3 class="text-14 font-medium text-text">Multi-Chain Token Radar</h3>
									<p class="text-11 text-text-3">Status jendela likuiditas, HP, dan volume/liquidity ratio per rantai</p>
								</div>
								<span class="rounded bg-surface px-2 py-0.5 text-11 font-mono text-accent border border-line">
									{radarObj?.chains?.length ?? 0} chain
								</span>
							</div>

							{#if !radarObj || (radarObj.chains ?? []).length === 0}
								<div class="py-6 text-center text-text-3 text-12">
									Data radar rantai belum tersedia.
								</div>
							{:else}
								<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 font-mono">
									{#each radarObj.chains as c (c.chain)}
										<div class="rounded-card border border-line bg-surface p-3 space-y-2">
											<div class="flex items-center justify-between border-b border-line-soft pb-2">
												<span class="font-bold text-13 text-text uppercase">{c.chain}</span>
												<span class="rounded px-2 py-0.5 text-10 font-bold border border-line {c.window === 'OPEN' ? 'text-pos bg-pos/10' : 'text-text-3 bg-canvas'}">
													{c.window}
												</span>
											</div>
											<div class="space-y-1 text-11">
												<div class="flex justify-between text-text-2">
													<span class="text-text-3">Avg V/L:</span>
													<span class="font-bold">{c.avg_vl?.toFixed(3) ?? '—'}</span>
												</div>
												<div class="flex justify-between text-text-2">
													<span class="text-text-3">HP:</span>
													<span>{c.hp ?? '—'}</span>
												</div>
												<div class="flex justify-between text-text-2">
													<span class="text-text-3">Age:</span>
													<span>{c.age ?? '—'}</span>
												</div>
											</div>
										</div>
									{/each}
								</div>
							{/if}
						</div>
					</div>
				{/if}

				{#if sub === 'lp'}
					<div class="space-y-4">
						<div class="permukaan-2 rounded-card border border-line p-3">
							<div class="mb-3 flex items-center justify-between border-b border-line-soft pb-2">
								<div>
									<h3 class="text-14 font-medium text-text">Paper LP Positions & Impermanent Loss</h3>
									<p class="text-11 text-text-3">Monitoring posisi LP uang nyata dan perbandingan vs hold</p>
								</div>
								{#if lpPaperObj?.capital}
									<span class="rounded bg-surface px-2 py-0.5 text-11 font-mono text-accent border border-line">
										Kapital: ${lpPaperObj.capital}
									</span>
								{/if}
							</div>

							{#if !lpPaperObj || (lpPaperObj.posisi ?? []).length === 0}
								<div class="py-6 text-center text-text-3 text-12">
									Tidak ada posisi LP aktif saat ini.
								</div>
							{:else}
								<div class="space-y-2">
									{#each lpPaperObj.posisi as p (p.symbol)}
										<div class="rounded-card border border-line bg-surface p-3 flex flex-wrap items-center justify-between gap-3">
											<div class="space-y-1">
												<div class="flex items-center gap-2">
													<span class="text-14 font-bold text-text font-mono">{p.symbol}</span>
													<span class="rounded bg-neg/10 text-neg border border-neg/20 px-2 py-0.5 text-10 font-bold">
														{p.verdict}
													</span>
												</div>
												<p class="text-11 text-text-3">{p.alasan}</p>
											</div>
											<div class="flex items-center gap-4 text-11 font-mono">
												<div>
													<span class="text-text-3 text-10 block">NOTIONAL</span>
													<span class="font-bold text-text">${p.notional}</span>
												</div>
												<div>
													<span class="text-text-3 text-10 block">FEE / HARI</span>
													<span class="font-bold text-pos">${p.fee_hari}</span>
												</div>
												<div>
													<span class="text-text-3 text-10 block">V/L AWAL / KINI</span>
													<span class="font-bold text-text-2">{p.vl} → {p.vl_now}</span>
												</div>
											</div>
										</div>
									{/each}
								</div>
							{/if}
						</div>
					</div>
				{/if}

				{#if sub === 'token'}
					<div class="space-y-4">
						<div class="permukaan-2 rounded-card border border-line p-3">
							<div class="mb-3 flex items-center justify-between border-b border-line-soft pb-2">
								<div>
									<h3 class="text-14 font-medium text-text">GMGN Smart Money & Whale Signals</h3>
									<p class="text-11 text-text-3">Deteksi akumulasi dompet pintar & whale multi-rantai (ETH, SOL, BSC)</p>
								</div>
								<span class="rounded bg-surface px-2 py-0.5 text-11 font-mono text-accent border border-line">
									{gmgnObj?.signals?.length ?? 0} sinyal
								</span>
							</div>

							{#if !gmgnObj || (gmgnObj.signals ?? []).length === 0}
								<div class="py-6 text-center text-text-3 text-12">
									Belum ada sinyal Smart Money yang terdeteksi.
								</div>
							{:else}
								<div class="overflow-x-auto">
									<table class="w-full text-left text-12 font-mono">
										<thead class="border-b border-line text-text-3 font-normal text-11">
											<tr>
												<th class="py-2 px-2.5">SIMBOL</th>
												<th class="py-2 px-2.5">SUMBER</th>
												<th class="py-2 px-2.5 text-right">BELI USD</th>
												<th class="py-2 px-2.5 text-right">HARGA (USD)</th>
												<th class="py-2 px-2.5 text-right">5M CHG</th>
												<th class="py-2 px-2.5 text-right">1H CHG</th>
												<th class="py-2 px-2.5 text-right">SHADOW %</th>
											</tr>
										</thead>
										<tbody class="divide-y divide-line-soft">
											{#each (gmgnObj.signals ?? []).slice(-15).reverse() as s (s.key + String(s.ts))}
												<tr class="hover:bg-surface/50 transition-colors">
													<td class="py-2 px-2.5 font-bold text-text">
														{s.symbol}
														{#if s.whale}
															<span class="ml-1 text-10 text-accent font-sans border border-accent/20 bg-accent/10 px-1 py-0.2 rounded">
																WHALE
															</span>
														{/if}
													</td>
													<td class="py-2 px-2.5 text-text-3 font-sans text-10 uppercase">
														{s.source} ({s.cluster_wallets}w)
													</td>
													<td class="py-2 px-2.5 text-right text-text-2">
														${s.cluster_buy_usd?.toLocaleString('id-ID', { maximumFractionDigits: 0 }) ?? '—'}
													</td>
													<td class="py-2 px-2.5 text-right text-text">
														${s.last_price_usd < 0.01 ? s.last_price_usd?.toFixed(6) : s.last_price_usd?.toFixed(2)}
													</td>
													<td class="py-2 px-2.5 text-right font-medium {(s.ret_5m_pct ?? 0) >= 0 ? 'text-pos' : 'text-neg'}">
														{(s.ret_5m_pct ?? 0) >= 0 ? '+' : ''}{s.ret_5m_pct?.toFixed(1) ?? '—'}%
													</td>
													<td class="py-2 px-2.5 text-right font-medium {(s.ret_1h_pct ?? 0) >= 0 ? 'text-pos' : 'text-neg'}">
														{(s.ret_1h_pct ?? 0) >= 0 ? '+' : ''}{s.ret_1h_pct?.toFixed(1) ?? '—'}%
													</td>
													<td class="py-2 px-2.5 text-right {(s.shadow_pct ?? 0) >= 0 ? 'text-pos' : 'text-neg'}">
														{(s.shadow_pct ?? 0) >= 0 ? '+' : ''}{s.shadow_pct?.toFixed(1) ?? '—'}%
													</td>
												</tr>
											{/each}
										</tbody>
									</table>
								</div>
							{/if}
						</div>
					</div>
				{/if}

				{#if sub === 'bot' || sub === 'memecoin'}
					<div class="space-y-4">
						<div class="permukaan-2 rounded-card border border-line p-3">
							<div class="mb-3 flex items-center justify-between border-b border-line-soft pb-2">
								<div>
									<h3 class="text-14 font-medium text-text">Solana Pumpfun Listings</h3>
									<p class="text-11 text-text-3">Token meme Solana aktif hasil streaming DexScreener</p>
								</div>
								<span class="rounded bg-surface px-2 py-0.5 text-11 font-mono text-accent border border-line">
									{memecoinObj?.venue?.pumpfun?.length ?? 0} token
								</span>
							</div>

							{#if !memecoinObj || (memecoinObj.venue?.pumpfun ?? []).length === 0}
								<div class="py-6 text-center text-text-3 text-12">
									Belum ada token Pumpfun yang terdeteksi.
								</div>
							{:else}
								<div class="grid grid-cols-1 md:grid-cols-2 gap-3">
									{#each memecoinObj.venue.pumpfun as m (m.alamat ?? m.pasangan)}
										<div class="rounded-card border border-line bg-surface p-3 flex items-center justify-between">
											<div>
												<div class="font-bold text-14 text-text font-mono">{m.pasangan}</div>
												<div class="text-11 text-text-3 font-mono">Volume 24h: ${m.vol_24h?.toLocaleString('id-ID') ?? '—'}</div>
												<div class="text-10 text-text-3 font-mono truncate max-w-[200px] mt-0.5">{m.alamat}</div>
											</div>
											{#if m.url}
												<a
													href={m.url}
													target="_blank"
													rel="noopener noreferrer"
													class="rounded-control border border-line bg-canvas px-3 py-1.5 text-11 text-accent hover:border-accent transition-colors"
												>
													DexScreener ↗
												</a>
											{/if}
										</div>
									{/each}
								</div>
							{/if}
						</div>
					</div>
				{/if}
			{/if}

			<!-- Gate Blok Evaluasi (Hanya bila ada verdict / gate statistik) -->
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

			<!-- Mode Inspeksi Mentah atau Fallback Area Non-Spesifik -->
			{#if tampilRaw || !['crypto', 'polymarket', 'idx', 'forex', 'gmgn'].includes(kunci)}
				<div class="space-y-3">
					<div class="border-t border-line-soft pt-3">
						<h3 class="text-13 font-medium text-text mb-2">Blok Data Area (Inspeksi Mentah)</h3>
					</div>

					{#if faktaTerpilih.length === 0}
						<Block judul={`Blok ${anak?.label ?? area?.label ?? kunci}`} kosong
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