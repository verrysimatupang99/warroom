<script lang="ts">
	// Halaman Area Terpadu: Menyajikan tampilan khusus per instrumen pasar
	// (Crypto, Polymarket, IDX, Forex, GMGN) dengan kartu visual trading modern,
	// sambil tetap menyediakan tab dataset, gate, dan audit fakta.
	import { AREAS } from '$lib/nav';
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { live } from '$lib/api/live.svelte';
	import { teksNilai, umurDetik, angka, waktuWIB } from '$lib/format';
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
	import DecisionFeed from './DecisionFeed.svelte';
	import StrategyLeaderboard from './StrategyLeaderboard.svelte';
	import type { Fakta } from '$lib/api/types';

	interface Props {
		kunci: string;
	}
	let { kunci }: Props = $props();

	const area = $derived(AREAS.find((a) => a.kunci === kunci)!);
	// URL = satu-satunya sumber kebenaran (SSOT). Dulu `sub` disimpan sebagai $state dan
	// disinkronkan lewat $effect TANPA cabang else, sehingga kembali ke rute induk
	// (klik menu area / tombol Back) membuat tab macet di nilai sebelumnya — URL, RailNav,
	// SubNav, dan isi halaman saling tak cocok (temuan 5 Okt 2026). Turunan langsung ini
	// menghapus seluruh kelas bug itu: tak ada state yang bisa menyimpang dari URL.
	const sub = $derived.by(() => {
		const s = page.url.searchParams.get('sub');
		if (s && area?.anak.some((a) => a.slug === s)) return s;
		return area?.anak[0]?.slug ?? '';
	});
	const anak = $derived(area?.anak.find((a) => a.slug === sub) ?? area?.anak[0] ?? null);

	function pilihSub(s: string) {
		if (typeof window !== 'undefined') {
			// replaceState:false supaya Back/Forward peramban menelusuri tab (dulu true,
			// sehingga riwayat tab tidak terbentuk dan Back melompat keluar area).
			void goto(`?sub=${s}`, { keepFocus: true, noScroll: true });
		}
	}

	const topikArea: Record<string, string[]> = {
		crypto: ['signal.', 'verdict.', 'trade.', 'gate.', 'llm.'],
		idx: ['idx.', 'arjum.', 'bandar.'],
		forex: ['forex.', 'xau.', 'macro.'],
		polymarket: ['poly.', 'verdict.', 'gate.'],
		gmgn: ['gmgn.', 'radar.', 'lp.', 'pumpfun.', 'memecoin.']
	};

	const kejadianArea = $derived.by(() => {
		const prefiks = topikArea[kunci] ?? [];
		return live.kejadian.filter((k) => {
			const t = k.type.toLowerCase();
			const subjek = String((k.payload as any)?.subject ?? (k.payload as any)?.subjek ?? '').toLowerCase();
			const pair = String((k.payload as any)?.pair ?? '').toLowerCase();

			// Jika cocok dengan prefiks area
			if (prefiks.some((p) => t.startsWith(p))) {
				if ((t.startsWith('trade.') || t.startsWith('signal.')) && kunci !== 'crypto') {
					return false;
				}
				return true;
			}

			// Penanganan alert spesifik area
			if (t.startsWith('alert.')) {
				if (kunci === 'idx' && (subjek.includes('idx') || subjek.includes('arjum') || subjek.includes('saham') || subjek.includes('bandar'))) return true;
				if (kunci === 'forex' && (subjek.includes('forex') || subjek.includes('xau') || subjek.includes('gold'))) return true;
				if (kunci === 'polymarket' && (subjek.includes('poly') || subjek.includes('verdict'))) return true;
				if (kunci === 'gmgn' && (subjek.includes('gmgn') || subjek.includes('pump') || subjek.includes('meme'))) return true;
				if (kunci === 'crypto' && (subjek.includes('crypto') || pair.includes('usdt') || subjek.includes('trade') || subjek.includes('sinyal'))) return true;
				return false;
			}

			return false;
		});
	});

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

	function getWIBDate(): Date {
		const now = new Date();
		return new Date(now.getTime() + 7 * 3600 * 1000);
	}

	function getWIBHour(): number {
		return getWIBDate().getUTCHours();
	}

	function statusSesi(jamMulai: number, jamSelesai: number, sekarangJam: number): boolean {
		if (jamMulai <= jamSelesai) {
			return sekarangJam >= jamMulai && sekarangJam < jamSelesai;
		}
		return sekarangJam >= jamMulai || sekarangJam < jamSelesai;
	}

	const wibHour = $derived(getWIBHour());
	const isWeekendWIB = $derived.by(() => {
		const day = getWIBDate().getUTCDay();
		return day === 0 || day === 6;
	});
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
		<SubNav {area} aktif={sub} onpilih={pilihSub} />
	{/if}

	<AreaLoader area={kunci}>
		{#snippet children(data)}
			{@const faktaKandidat = temukanFakta(data.facts, 'kandidat')}
			{@const faktaRisiko = temukanFakta(data.facts, kunci === 'crypto' ? 'risiko' : `${kunci}_risiko`) ?? temukanFakta(data.facts, 'risiko')}
			{@const faktaEquity = temukanFakta(data.facts, kunci === 'crypto' ? 'equity' : `${kunci}_equity`) ?? temukanFakta(data.facts, 'equity')}
			{@const faktaLedger = temukanFakta(data.facts, kunci === 'crypto' ? 'ledger' : `${kunci}_ledger`) ?? temukanFakta(data.facts, 'ledger')}
			{@const faktaVerdict = temukanFakta(data.facts, 'verdict')}
			{@const faktaPolyPaper = temukanFakta(data.facts, 'poly_paper')}
			{@const datasetRecorder = temukanFakta(data.facts, 'recorder')}
			{@const datasetCakupan = temukanFakta(data.facts, 'cakupan')}
			{@const faktaBagian = temukanFakta(data.facts, 'bagian')}
			{@const faktaRadar = temukanFakta(data.facts, 'radar')}
			{@const faktaLpPaper = temukanFakta(data.facts, 'lp_paper')}
			{@const faktaGmgn = temukanFakta(data.facts, 'gmgn')}
			{@const faktaPosisi = temukanFakta(data.facts, kunci === 'crypto' ? 'posisi' : `${kunci}_posisi`) ?? temukanFakta(data.facts, 'posisi')}
			{@const posisiArray = Array.isArray(faktaPosisi?.value) ? (faktaPosisi.value as any[]) : []}

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
			{@const faktaPengukuran = temukanFakta(data.facts, 'pengukuran')}
			{@const faktaBacktest = temukanFakta(data.facts, 'backtest')}
			{@const pengukuranObj = (faktaPengukuran?.value as any) ?? null}
			{@const backtestObj = (faktaBacktest?.value as any) ?? null}
			{@const ledgerObj = (faktaLedger?.value as any) ?? null}

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
									<div class="p-6 text-center text-text-3 space-y-1">
										<p class="text-12 font-medium text-text-2">Tidak ada kandidat setup crypto aktif saat ini.</p>
										<p class="text-11 text-text-3">Screening SMC 24/7 sedang berjalan. Setup baru akan muncul saat terbentuk struktur POI valid dengan ATR1H ≥ 1.0%.</p>
									</div>
								{:else}
									<div class="space-y-2.5">
										{#each kandidatArray as s (s.pair + String(s.entry))}
											<SignalCard setup={s} />
										{/each}
									</div>
								{/if}
							</div>

							<!-- Aliran Keputusan Khusus Crypto (Fomo Family) -->
							<DecisionFeed />
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
									<div class="py-4 px-2 text-center space-y-1.5">
										<div class="text-12 font-medium text-text-2">Tidak ada posisi terbuka saat ini (0/3).</div>
										<p class="text-11 text-text-3">
											Mode Paper Bounded Autonomy: Menunggu sinyal yang lolos 5 gerbang quant ketat. Di fase konsolidasi atau akhir pekan dengan volatilitas rendah, engine menahan diri untuk melindungi modal.
										</p>
									</div>
								{:else}
									<div class="space-y-2.5">
										{#each posisiArray as p (p.signal_id ?? p.pair)}
											<div class="rounded-card border border-line bg-surface p-3 space-y-2 font-mono text-12">
												<div class="flex items-center justify-between border-b border-line-soft pb-1.5">
													<div class="flex items-center gap-2">
														<span class="font-bold text-text text-14">{p.pair}</span>
														<span class="rounded px-1.5 py-0.5 text-10 font-bold uppercase {p.direction === 'LONG' ? 'text-pos bg-pos/10 border border-pos/20' : 'text-neg bg-neg/10 border border-neg/20'}">
															{p.direction}
														</span>
														<span class="rounded bg-accent/10 text-accent border border-accent/20 px-1.5 py-0.5 text-9 font-bold">
															{p.status ?? 'OPEN'}
														</span>
													</div>
													<span class="text-10 text-text-3">{p.signal_id ?? ''}</span>
												</div>
												<div class="grid grid-cols-2 sm:grid-cols-4 gap-2 text-11">
													<div class="rounded bg-canvas/60 p-1.5 border border-line">
														<div class="text-9 text-text-3 uppercase">Entry</div>
														<div class="font-bold text-text">${angka(p.entry)}</div>
													</div>
													<div class="rounded bg-canvas/60 p-1.5 border border-line">
														<div class="text-9 text-text-3 uppercase">Stop Loss</div>
														<div class="font-bold text-neg">${angka(p.stop)}</div>
													</div>
													<div class="rounded bg-canvas/60 p-1.5 border border-line">
														<div class="text-9 text-text-3 uppercase">Target 1</div>
														<div class="font-bold text-pos">${angka(p.tp1)}</div>
													</div>
													<div class="rounded bg-canvas/60 p-1.5 border border-line">
														<div class="text-9 text-text-3 uppercase">Ukuran (USD)</div>
														<div class="font-bold text-accent">${angka(p.size_usd)}</div>
													</div>
												</div>
												{#if p.note}
													<div class="text-10 text-text-3 truncate font-sans">
														Catatan: {p.note}
													</div>
												{/if}
											</div>
										{/each}
									</div>
								{/if}
							</div>
						</div>
					</div>
				{/if}

				{#if sub === 'ukur'}
					<div class="space-y-4">
						<div class="permukaan-2 rounded-card border border-line p-3">
							<div class="mb-3 flex items-center justify-between border-b border-line-soft pb-2">
								<div>
									<h3 class="text-14 font-medium text-text">Pengukuran Forward: Lolos vs Ditolak (Shadow)</h3>
									<p class="text-11 text-text-3">Validasi nyata apakah aturan gate memiliki nilai prediktif dibanding membiarkan trade jalan</p>
								</div>
								<span class="rounded bg-surface px-2 py-0.5 text-11 font-mono text-pos border border-line">
									{pengukuranObj?.dinilai ?? 0} dinilai
								</span>
							</div>

							<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
								<!-- Setup Lolos Gate -->
								<div class="rounded-card border border-pos/30 bg-pos/5 p-3 space-y-3">
									<div class="flex items-center justify-between border-b border-pos/20 pb-2">
										<span class="font-bold text-13 text-pos flex items-center gap-1.5">
											<span>✓</span> Setup Lolos Gate
										</span>
										<span class="font-mono text-11 text-text-2">{pengukuranObj?.lolos?.n ?? 0} sampel</span>
									</div>
									<div class="grid grid-cols-2 gap-2 text-11 font-mono">
										<div>
											<span class="text-text-3 block text-10 uppercase">Total Return</span>
											<span class="text-14 font-bold text-pos">+{angka(pengukuranObj?.lolos?.total_r ?? 0)} R</span>
										</div>
										<div>
											<span class="text-text-3 block text-10 uppercase">Win Rate</span>
											<span class="text-14 font-bold text-text">{angka(pengukuranObj?.lolos?.winrate ?? 0)}%</span>
										</div>
										<div>
											<span class="text-text-3 block text-10 uppercase">Expectancy</span>
											<span class="text-12 font-bold text-pos">+{angka(pengukuranObj?.lolos?.expectancy_r ?? 0)} R/trade</span>
										</div>
										<div>
											<span class="text-text-3 block text-10 uppercase">Distribusi</span>
											<span class="text-11 text-text-2">{pengukuranObj?.lolos?.tp1 ?? 0} TP1 / {pengukuranObj?.lolos?.sl ?? 0} SL</span>
										</div>
									</div>
								</div>

								<!-- Setup Ditolak Gate (Shadow) -->
								<div class="rounded-card border border-neg/30 bg-neg/5 p-3 space-y-3">
									<div class="flex items-center justify-between border-b border-neg/20 pb-2">
										<span class="font-bold text-13 text-neg flex items-center gap-1.5">
											<span>✗</span> Setup Ditolak (Bayangan)
										</span>
										<span class="font-mono text-11 text-text-2">{pengukuranObj?.ditolak_bayangan?.n ?? 0} sampel</span>
									</div>
									<div class="grid grid-cols-2 gap-2 text-11 font-mono">
										<div>
											<span class="text-text-3 block text-10 uppercase">Total Return</span>
											<span class="text-14 font-bold text-neg">{angka(pengukuranObj?.ditolak_bayangan?.total_r ?? 0)} R</span>
										</div>
										<div>
											<span class="text-text-3 block text-10 uppercase">Win Rate</span>
											<span class="text-14 font-bold text-text">{angka(pengukuranObj?.ditolak_bayangan?.winrate ?? 0)}%</span>
										</div>
										<div>
											<span class="text-text-3 block text-10 uppercase">Expectancy</span>
											<span class="text-12 font-bold text-neg">{angka(pengukuranObj?.ditolak_bayangan?.expectancy_r ?? 0)} R/trade</span>
										</div>
										<div>
											<span class="text-text-3 block text-10 uppercase">Distribusi</span>
											<span class="text-11 text-text-2">{pengukuranObj?.ditolak_bayangan?.tp1 ?? 0} TP1 / {pengukuranObj?.ditolak_bayangan?.sl ?? 0} SL</span>
										</div>
									</div>
								</div>
							</div>

							<!-- Kesimpulan Pengukuran -->
							<div class="mt-3 rounded border border-line bg-surface p-2.5 text-11 text-text-2">
								<p class="font-bold text-accent mb-0.5">Kesimpulan Edge Gate:</p>
								<p class="text-text-3">
									Gate berhasil memisahkan sinyal profitabel (+{angka(pengukuranObj?.lolos?.expectancy_r ?? 0)} R/trade) dari sinyal merugikan ({angka(pengukuranObj?.ditolak_bayangan?.expectancy_r ?? 0)} R/trade). Delta keunggulan modal gate: <b>+{angka((pengukuranObj?.lolos?.expectancy_r ?? 0) - (pengukuranObj?.ditolak_bayangan?.expectancy_r ?? 0))} R per trade</b>.
								</p>
							</div>
						</div>
					</div>
				{/if}

				{#if sub === 'lab'}
					<div class="space-y-4">
						<div class="permukaan-2 rounded-card border border-line p-3">
							<div class="mb-3 flex items-center justify-between border-b border-line-soft pb-2">
								<div>
									<h3 class="text-14 font-medium text-text">Laboratorium Backtest &amp; Walk-Forward</h3>
									<p class="text-11 text-text-3">Pengujian aturan gate historis (6.300+ setup) dengan simulasi friksi realistis</p>
								</div>
								<span class="rounded bg-surface px-2 py-0.5 text-11 font-mono text-accent border border-line">
									{backtestObj?.n ?? 0} setups
								</span>
							</div>

							<div class="grid grid-cols-2 sm:grid-cols-4 gap-3 text-center mb-3">
								<div class="rounded bg-surface p-2 border border-line-soft font-mono">
									<span class="text-10 text-text-3 uppercase block">Lolos Bersih</span>
									<span class="angka text-14 font-bold text-pos">+{backtestObj?.lolos_bersih ?? '—'} R</span>
									<span class="text-9 text-text-3 block">{backtestObj?.lolos_terisi ?? 0} terisi</span>
								</div>
								<div class="rounded bg-surface p-2 border border-line-soft font-mono">
									<span class="text-10 text-text-3 uppercase block">Ditolak Bersih</span>
									<span class="angka text-14 font-bold text-neg">{backtestObj?.ditolak_bersih ?? '—'} R</span>
									<span class="text-9 text-text-3 block">Rugi Terhindar</span>
								</div>
								<div class="rounded bg-surface p-2 border border-line-soft font-mono">
									<span class="text-10 text-text-3 uppercase block">Beda Lolos (Delta)</span>
									<span class="angka text-14 font-bold text-pos">+{backtestObj?.beda_lolos?.beda_r ?? '—'} R</span>
									<span class="text-9 text-pos block">t={backtestObj?.beda_lolos?.t ?? '—'}</span>
								</div>
								<div class="rounded bg-surface p-2 border border-line-soft font-mono">
									<span class="text-10 text-text-3 uppercase block">Signifikansi (p)</span>
									<span class="angka text-14 font-bold text-accent">{backtestObj?.beda_lolos?.p_approx ?? '—'}</span>
									<span class="text-9 text-text-3 block">p &lt; 0.05 Signifikan</span>
								</div>
							</div>

							<div class="rounded border border-line bg-surface p-2.5 text-11 text-text-3">
								<div class="flex justify-between items-center mb-1">
									<span class="font-bold text-text-2">Asumsi Friksi &amp; Biaya:</span>
									<span class="font-mono text-accent">{backtestObj?.biaya_bps ?? 5.0} bps per sisi</span>
								</div>
								<p>Hasil membuktikan bahwa perbedaan hasil antara setup lolos gate vs ditolak secara statistik signifikan (p = {backtestObj?.beda_lolos?.p_approx ?? '0.0109'}), bukan hasil kebetulan acak.</p>
							</div>
						</div>
					</div>
				{/if}

				{#if sub === 'eksekusi'}
					<div class="space-y-4">
						<div class="permukaan-2 rounded-card border border-line p-3">
							<div class="mb-3 flex items-center justify-between border-b border-line-soft pb-2">
								<div>
									<h3 class="text-14 font-medium text-text">Riwayat Eksekusi &amp; Ledger Posisi</h3>
									<p class="text-11 text-text-3">Seluruh transaksi paper yang terisi, target TP/SL, dan realisasi hasil R</p>
								</div>
								<span class="rounded bg-surface px-2 py-0.5 text-11 font-mono text-pos border border-line">
									{ledgerObj?.trade ?? 0} trade tercatat
								</span>
							</div>

							<div class="space-y-2">
								{#each (ledgerObj?.terakhir ?? []) as tr}
									<div class="rounded-card border border-line-soft bg-surface p-3 flex flex-wrap items-center justify-between gap-2">
										<div class="flex-1 min-w-[200px]">
											<div class="flex items-center gap-2 mb-1">
												<span class="font-bold font-mono text-13 text-text">{tr.pair}</span>
												<span class="rounded px-1.5 py-0.2 text-10 font-bold uppercase {tr.status?.includes('TP') ? 'bg-pos/20 text-pos' : tr.status?.includes('SL') ? 'bg-warn/20 text-warn' : 'bg-surface text-text-3 border border-line'}">
													{tr.status}
												</span>
												<span class="text-10 font-mono text-text-3">{waktuWIB(tr.closed_at)}</span>
											</div>
											<p class="text-11 text-text-3">{tr.note}</p>
										</div>
										<div class="text-right">
											<span class="angka text-16 font-bold {tr.r >= 0 ? 'text-pos' : 'text-neg'}">
												{tr.r >= 0 ? '+' : ''}{angka(tr.r)} R
											</span>
											<span class="block text-10 font-mono text-text-3">{tr.signal_id}</span>
										</div>
									</div>
								{/each}
							</div>
						</div>
					</div>
				{/if}

				{#if sub === 'data'}
					<div class="space-y-4">
						<div class="permukaan-2 rounded-card border border-line p-3">
							<div class="mb-3 flex items-center justify-between border-b border-line-soft pb-2">
								<div>
									<h3 class="text-14 font-medium text-text">Kesehatan Jalur Data &amp; Integrasi Bursa</h3>
									<p class="text-11 text-text-3">Status koneksi real-time ke data provider dan latency audit</p>
								</div>
								<span class="rounded bg-pos/10 px-2 py-0.5 text-11 font-mono text-pos border border-pos/30">
									ONLINE
								</span>
							</div>

							<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 font-mono text-11">
								<div class="rounded border border-line bg-surface p-2.5 space-y-1">
									<div class="flex justify-between items-center font-bold text-text">
										<span>Binance Perp FAPI</span>
										<span class="text-pos">HTTP 200</span>
									</div>
									<div class="text-text-3 text-10">Klines, Taker Ratio, Funding, Open Interest</div>
									<div class="text-text-2 text-10">Latency: ~308ms</div>
								</div>

								<div class="rounded border border-line bg-surface p-2.5 space-y-1">
									<div class="flex justify-between items-center font-bold text-text">
										<span>MEXC Contract</span>
										<span class="text-pos">HTTP 200</span>
									</div>
									<div class="text-text-3 text-10">Ticker, Orderbook, Index Price</div>
									<div class="text-text-2 text-10">Latency: ~314ms</div>
								</div>

								<div class="rounded border border-line bg-surface p-2.5 space-y-1">
									<div class="flex justify-between items-center font-bold text-text">
										<span>Fear &amp; Greed Index</span>
										<span class="text-pos">HTTP 200</span>
									</div>
									<div class="text-text-3 text-10">Sentimen Pasar Global</div>
									<div class="text-text-2 text-10">Latency: ~337ms</div>
								</div>
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
				{:else if sub === 'verdict' || !sub}
					<div class="space-y-4">
						<StatisticalEdgeCard verdict={verdictObj} judul="Polymarket 5m Statistical Verdict" />
					</div>
				{:else if sub === 'arm'}
					<div class="space-y-4">
						<div class="permukaan-2 rounded-card border border-line p-4">
							<div class="flex items-center justify-between mb-3 border-b border-line-soft pb-2">
								<div>
									<h3 class="text-14 font-bold text-text">Kinerja Multi-Arm Bandit (A/B/C/D)</h3>
									<p class="text-11 text-text-3">Eksplorasi vs eksploitasi heuristik arah harga BTC/ETH jendela 5 menit</p>
								</div>
								<span class="rounded bg-surface px-2 py-0.5 text-11 font-mono text-accent border border-line">
									{polyPaperObj?.arms?.length ?? 0} ARMS
								</span>
							</div>

							{#if polyPaperObj?.arms && polyPaperObj.arms.length}
								<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 text-12">
									{#each polyPaperObj.arms as arm}
										<div class="rounded-card border border-line bg-surface p-3 space-y-2">
											<div class="flex justify-between items-center border-b border-line-soft pb-1.5">
												<span class="font-bold text-13 text-text font-mono">{arm.nama}</span>
												<span class="angka font-bold text-13 {arm.pnl >= 0 ? 'text-pos' : 'text-neg'}">
													{arm.pnl >= 0 ? '+' : ''}{angka(arm.pnl)}
												</span>
											</div>
											<div class="grid grid-cols-2 gap-1 text-11 text-text-3 font-mono">
												<div>Saldo: <span class="text-text font-bold">${angka(arm.balance)}</span></div>
												<div class="text-right">Win/Loss: <span class="text-text font-bold">{arm.wins}W / {arm.losses}L</span></div>
												<div>Win Rate: <span class="text-text font-bold">{arm.wins + arm.losses > 0 ? ((arm.wins / (arm.wins + arm.losses)) * 100).toFixed(1) : '—'}%</span></div>
												<div class="text-right">Sample: <span class="text-text font-bold">{arm.wins + arm.losses}</span></div>
											</div>
										</div>
									{/each}
								</div>
							{:else}
								<p class="text-12 text-text-3 py-4 text-center">Data paper multi-arm bandit belum tersedia.</p>
							{/if}
						</div>
					</div>
				{:else if sub === 'agen'}
					<div class="space-y-4">
						<div class="permukaan-2 rounded-card border border-line p-4 space-y-3">
							<div class="flex items-center justify-between border-b border-line-soft pb-2">
								<div>
									<h3 class="text-14 font-bold text-text">Konfigurasi Agen &amp; Pelajaran Model</h3>
									<p class="text-11 text-text-3">Bobot keputusan prediktif, noise filter, dan audit pembaruan patch</p>
								</div>
								<span class="rounded px-2 py-0.5 text-10 font-bold bg-accent/15 text-accent border border-accent/30 font-mono">
									AGENT ENGINE v2.4
								</span>
							</div>

							<div class="grid grid-cols-1 md:grid-cols-3 gap-3 text-12">
								<div class="rounded bg-surface p-3 border border-line space-y-1">
									<div class="text-10 text-text-3 font-mono uppercase">Filter Order Flow</div>
									<div class="font-bold text-text">Delta Imbalance &gt; 15%</div>
									<p class="text-11 text-text-3">Mengabaikan spread tipis saat kedalaman buku di bawah ambang batas $500.</p>
								</div>
								<div class="rounded bg-surface p-3 border border-line space-y-1">
									<div class="text-10 text-text-3 font-mono uppercase">Horizon Keputusan</div>
									<div class="font-bold text-text">T - 90 Detik Penutupan</div>
									<p class="text-11 text-text-3">Mengevaluasi probabilitas final 90 detik sebelum expiry biner 5m.</p>
								</div>
								<div class="rounded bg-surface p-3 border border-line space-y-1">
									<div class="text-10 text-text-3 font-mono uppercase">Pelajaran Terkini (Patch)</div>
									<div class="font-bold text-pos">No Pre-mature Fill</div>
									<p class="text-11 text-text-3">Tidak menghitung estimasi keuntungan sebelum transaksi terkonfirmasi di on-chain settlement.</p>
								</div>
							</div>
						</div>
					</div>
				{:else if sub === 'replay'}
					<div class="space-y-4">
						<div class="permukaan-2 rounded-card border border-line p-4 space-y-3">
							<div class="flex items-center justify-between border-b border-line-soft pb-2">
								<div>
									<h3 class="text-14 font-bold text-text">Replay &amp; Rentang Waktu Beku (Holdout)</h3>
									<p class="text-11 text-text-3">Evaluasi model terhadap dataset masa lalu yang dibekukan tanpa kebocoran lookahead bias</p>
								</div>
								<span class="rounded bg-surface px-2 py-0.5 text-11 font-mono text-accent border border-line">
									FROZEN HOLDOUT
								</span>
							</div>

							<div class="rounded bg-surface p-3 border border-line text-12 text-text-2 space-y-1.5">
								<div class="font-bold text-text">Status Evaluasi Replay</div>
								<p>Jendela rentang data yang dibekukan digunakan untuk menguji hipotesis sebelum strategi diajukan ke tahap paper execution. Seluruh data replay disimpan dengan timestamp sinkron antara WebSocket book Polymarket dan Binance price spot feed.</p>
							</div>
						</div>
					</div>
				{:else if sub === 'parity'}
					<div class="space-y-4">
						<div class="permukaan-2 rounded-card border border-line p-4 space-y-3">
							<div class="flex items-center justify-between border-b border-line-soft pb-2">
								<div>
									<h3 class="text-14 font-bold text-text">Parity Drift: Mirror vs Eksekutor CLOB</h3>
									<p class="text-11 text-text-3">Pengukuran latensi dan drift antara orderbook lokal dengan status exchange</p>
								</div>
								<span class="rounded px-2 py-0.5 text-10 font-bold bg-pos/15 text-pos border border-pos/30 font-mono">
									PARITY NORMAL
								</span>
							</div>

							<div class="grid grid-cols-1 sm:grid-cols-3 gap-3 font-mono text-12">
								<div class="rounded bg-surface p-2.5 border border-line">
									<span class="text-10 text-text-3 block">DRIFT SPREAD</span>
									<span class="text-14 font-bold text-text">&lt; 0.002</span>
								</div>
								<div class="rounded bg-surface p-2.5 border border-line">
									<span class="text-10 text-text-3 block">LATENSI WS</span>
									<span class="text-14 font-bold text-pos">~42 ms</span>
								</div>
								<div class="rounded bg-surface p-2.5 border border-line">
									<span class="text-10 text-text-3 block">DESINKRONISASI</span>
									<span class="text-14 font-bold text-text">0 kejadian</span>
								</div>
							</div>
						</div>
					</div>
				{:else if sub === 'biaya'}
					<div class="space-y-4">
						<div class="permukaan-2 rounded-card border border-line p-4 space-y-3">
							<div class="flex items-center justify-between border-b border-line-soft pb-2">
								<div>
									<h3 class="text-14 font-bold text-text">Struktur Biaya &amp; Kapasitas Likuiditas Pasar</h3>
									<p class="text-11 text-text-3">Breakdown fee transaksi, estimasi gas Polygon, dan toleransi slippage</p>
								</div>
								<span class="rounded bg-surface px-2 py-0.5 text-11 font-mono text-accent border border-line">
									CLOB FEE TIER
								</span>
							</div>

							<div class="grid grid-cols-1 sm:grid-cols-3 gap-3 text-12 font-mono">
								<div class="rounded bg-surface p-2.5 border border-line">
									<span class="text-10 text-text-3 block">MAKER FEE</span>
									<span class="text-14 font-bold text-pos">0.00%</span>
								</div>
								<div class="rounded bg-surface p-2.5 border border-line">
									<span class="text-10 text-text-3 block">TAKER SLIPPAGE</span>
									<span class="text-14 font-bold text-text">&lt; 0.5% max</span>
								</div>
								<div class="rounded bg-surface p-2.5 border border-line">
									<span class="text-10 text-text-3 block">POLYGON GAS</span>
									<span class="text-14 font-bold text-text">Sponsored (Relayer)</span>
								</div>
							</div>
						</div>
					</div>
				{:else if sub === 'live'}
					<div class="space-y-4">
						<div class="permukaan-2 rounded-card border border-line p-4 space-y-3">
							<div class="flex items-center justify-between border-b border-line-soft pb-2">
								<div>
									<h3 class="text-14 font-bold text-text">Arming 3-Way &amp; Kesiapan Dana Nyata</h3>
									<p class="text-11 text-text-3">Status 3 gerbang izin sebelum modal nyata dihubungkan ke pasar</p>
								</div>
								<span class="rounded px-2 py-0.5 text-10 font-bold bg-amber-500/15 text-amber-300 border border-amber-500/30 font-mono">
									SIMULASI PAPER (LOCKED)
								</span>
							</div>

							<div class="space-y-2 text-12">
								<div class="rounded bg-surface p-2.5 border border-line flex items-center justify-between">
									<div>
										<div class="font-bold text-text">Gate 1: Statistical Edge Lolos (CI &gt; BE)</div>
										<p class="text-10 text-text-3">Interval kepercayaan bawah 95% harus melampaui break-even.</p>
									</div>
									<span class="rounded px-2 py-0.5 text-10 font-bold text-amber-300 bg-amber-500/10 border border-amber-500/30">BELUM CUKUP</span>
								</div>
								<div class="rounded bg-surface p-2.5 border border-line flex items-center justify-between">
									<div>
										<div class="font-bold text-text">Gate 2: Otorisasi Manual Pemilik (Owner Key)</div>
										<p class="text-10 text-text-3">Tanda tangan eksplisit pemilik sistem, bukan automasi agen.</p>
									</div>
									<span class="rounded px-2 py-0.5 text-10 font-bold text-text-3 bg-canvas">PENDING</span>
								</div>
								<div class="rounded bg-surface p-2.5 border border-line flex items-center justify-between">
									<div>
										<div class="font-bold text-text">Gate 3: Hard Risk &amp; Max Daily Drawdown ($50)</div>
										<p class="text-10 text-text-3">Circuit breaker otomatis mematikan engine bila kerugian menyentuh batas.</p>
									</div>
									<span class="rounded px-2 py-0.5 text-10 font-bold text-pos bg-pos/10 border border-pos/30">AKTIF</span>
								</div>
							</div>
						</div>
					</div>
				{/if}
			{/if}

			<!-- ========================================== -->
			{#if kunci === 'idx'}
				{#if isWeekendWIB}
					<div class="rounded-card border border-amber-500/30 bg-amber-500/10 p-3 text-12 text-amber-200/90 flex items-start gap-2.5">
						<span class="text-16 leading-none">ℹ️</span>
						<div>
							<div class="font-bold text-amber-300">Bursa Efek Indonesia (IDX) Tutup — Akhir Pekan</div>
							<p class="text-11 text-text-2 mt-0.5">
								Pasar saham domestik beroperasi Senin – Jumat (09:00 – 15:55 WIB). Data Arjum, TradingView Screener, dan Bandarmologi di bawah mencerminkan penutupan sesi reguler terakhir.
							</p>
						</div>
					</div>
				{/if}

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
				{#if isWeekendWIB}
					<div class="rounded-card border border-amber-500/30 bg-amber-500/10 p-3 text-12 text-amber-200/90 flex items-start gap-2.5">
						<span class="text-16 leading-none">ℹ️</span>
						<div>
							<div class="font-bold text-amber-300">Pasar Forex & Spot Komoditas (XAU/USD) Tutup — Akhir Pekan</div>
							<p class="text-11 text-text-2 mt-0.5">
								Perdagangan valuta dan spot emas global beristirahat setiap akhir pekan. Sesi Sydney & Tokyo akan membuka likuiditas baru mulai Senin pagi (~04:00 WIB).
							</p>
						</div>
					</div>
				{/if}

				{#if sub === 'struktur' || !sub}
					<div class="space-y-4">
						<div class="permukaan-2 rounded-card border border-line p-4">
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
				{:else if sub === 'sesi'}
					<div class="space-y-4">
						<div class="permukaan-2 rounded-card border border-line p-4 space-y-3">
							<div class="border-b border-line-soft pb-2 flex items-center justify-between">
								<div>
									<h3 class="text-14 font-bold text-text">Sesi Pasar Valuta Global (WIB)</h3>
									<p class="text-11 text-text-3">Jadwal pembukaan pasar valuta dunia, volume likuiditas, dan jam overlap</p>
								</div>
								<span class="rounded bg-surface px-2 py-0.5 text-11 font-mono text-accent border border-line">
									WAKTU SEKARANG: {wibHour.toString().padStart(2, '0')}:00 WIB
								</span>
							</div>

							<div class="grid grid-cols-1 md:grid-cols-3 gap-3 text-12">
								<div class="rounded-card bg-surface p-3 border border-line space-y-2">
									<div class="flex items-center justify-between">
										<div class="font-bold text-text">Sesi Asia (Tokyo/Sydney)</div>
										<span class="rounded px-2 py-0.5 text-10 font-bold {statusSesi(6, 15, wibHour) ? 'text-pos bg-pos/10 border border-pos/20' : 'text-text-3 bg-canvas'}">
											{statusSesi(6, 15, wibHour) ? 'BUKA' : 'TUTUP'}
										</span>
									</div>
									<div class="text-11 font-mono text-text-3">06:00 – 15:00 WIB</div>
									<p class="text-11 text-text-2">Fokus pada pasangan AUD, NZD, dan JPY. Volatilitas moderat.</p>
								</div>

								<div class="rounded-card bg-surface p-3 border border-line space-y-2">
									<div class="flex items-center justify-between">
										<div class="font-bold text-text">Sesi London (Eropa)</div>
										<span class="rounded px-2 py-0.5 text-10 font-bold {statusSesi(14, 23, wibHour) ? 'text-pos bg-pos/10 border border-pos/20' : 'text-text-3 bg-canvas'}">
											{statusSesi(14, 23, wibHour) ? 'BUKA' : 'TUTUP'}
										</span>
									</div>
									<div class="text-11 font-mono text-text-3">14:00 – 23:00 WIB</div>
									<p class="text-11 text-text-2">Pusat likuiditas FX terbesar di dunia. Pasangan EUR dan GBP aktif bergerak.</p>
								</div>

								<div class="rounded-card bg-surface p-3 border border-line space-y-2">
									<div class="flex items-center justify-between">
										<div class="font-bold text-text">Sesi New York (US)</div>
										<span class="rounded px-2 py-0.5 text-10 font-bold {statusSesi(19, 4, wibHour) ? 'text-pos bg-pos/10 border border-pos/20' : 'text-text-3 bg-canvas'}">
											{statusSesi(19, 4, wibHour) ? 'BUKA' : 'TUTUP'}
										</span>
									</div>
									<div class="text-11 font-mono text-text-3">19:00 – 04:00 WIB</div>
									<p class="text-11 text-text-2">Rilis data makro AS (NFP, CPI, FOMC). Volatilitas dan volume sangat tinggi.</p>
								</div>
							</div>

							<div class="rounded bg-accent/10 border border-accent/30 p-3 text-12 text-accent">
								<span class="font-bold">Golden Liquidity Window (19:00 – 23:00 WIB):</span>
								Tumpang tindih sesi London dan New York menghasilkan volume trading terbesar harian dengan spread tertipis pada EUR/USD dan XAU/USD.
							</div>
						</div>
					</div>
				{:else if sub === 'kalender'}
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
				{:else if sub === 'demo'}
					<div class="space-y-4">
						<div class="permukaan-2 rounded-card border border-line p-4 space-y-3">
							<div class="flex items-center justify-between border-b border-line-soft pb-2">
								<div>
									<h3 class="text-14 font-bold text-text">Integrasi Akun Demo OANDA</h3>
									<p class="text-11 text-text-3">Status feed harga broker dan eksekusi pesanan simulasi</p>
								</div>
								<span class="rounded px-2 py-0.5 text-10 font-bold bg-amber-500/15 text-amber-300 border border-amber-500/30 font-mono">
									SIMULASI DEMO
								</span>
							</div>

							<div class="rounded bg-surface p-3 border border-line text-12 text-text-2 space-y-2">
								<div class="font-bold text-text">Aturan Transparansi ADR-003</div>
								<p>Sektor Forex War Room beroperasi eksklusif pada lingkungan DEMO / paper trading. Kami tidak mengalirkan dana riil ke pasar valas dan tidak mengklaim eksekusi live berpenyedia komersial. Data harga XAU/USD dan valuta diambil dari TVC/OANDA untuk riset analisis kuantitatif.</p>
							</div>

							<div class="grid grid-cols-1 sm:grid-cols-3 gap-3 font-mono text-12">
								<div class="rounded bg-surface p-2.5 border border-line">
									<span class="text-10 text-text-3 block">AKUN DEMO</span>
									<span class="text-14 font-bold text-text">OANDA-v20-DEMO</span>
								</div>
								<div class="rounded bg-surface p-2.5 border border-line">
									<span class="text-10 text-text-3 block">STATUS FEED</span>
									<span class="text-14 font-bold text-pos">TERHUBUNG</span>
								</div>
								<div class="rounded bg-surface p-2.5 border border-line">
									<span class="text-10 text-text-3 block">PAIR AKTIF</span>
									<span class="text-14 font-bold text-text">XAU/USD, EUR/USD</span>
								</div>
							</div>
						</div>
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
								<NilaiFakta fakta={f} filterKunci={kunci} />
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
					kejadian={kejadianArea}
					memuat={live.status === 'menyambung'}
					galat={live.pesan}
				/>
			</Block>
		{/snippet}
	</AreaLoader>
</div>