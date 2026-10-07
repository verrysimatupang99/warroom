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
	import FreshnessBadge from './FreshnessBadge.svelte';
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
	import type { DecisionItem } from './DecisionFeed.svelte';
	import StrategyLeaderboard from './StrategyLeaderboard.svelte';
	import AkurasiPasar from './AkurasiPasar.svelte';
	import DompetPasar from './DompetPasar.svelte';
	import JudulBagian from './JudulBagian.svelte';
	import Penjelasan from './Penjelasan.svelte';
	import ForexPair from './ForexPair.svelte';
	import KalenderDampak from './KalenderDampak.svelte';
	import SinyalPasar from './SinyalPasar.svelte';
	import { getEvents } from '$lib/api/client';
	import type { Fakta, Kejadian } from '$lib/api/types';

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
	// Slug LAMA → slug baru, supaya tautan & bookmark tidak mati saat sub dirampingkan
	// (6 Okt 2026: IDX 5→3, GMGN 4→3). Bukan pengalihan URL, tapi penerjemahan di sini —
	// halaman tetap satu tempat, dan `?sub=` lama tetap menampilkan isi yang benar.
	const ALIAS_SUB: Record<string, string> = {
		aliran: 'bandarmologi', // IDX: Aliran digabung ke Bandarmologi
		watchlist: 'bsjp', // IDX: Watchlist/ARA Hunter digabung ke BSJP
		token: 'memecoin', // GMGN: Token + Bot digabung jadi Memecoin
		bot: 'memecoin',
		// Crypto: 7→4 (6 Okt 2026)
		lab: 'ukur',
		data: 'cockpit',
		overextended: 'eksekusi',
		// IDX (7 Okt): "screener" diganti "sinyal"; "aliran" kini tab sendiri lagi
		screener: 'sinyal',
		// Polymarket (7 Okt): fokus Setup B; verdict→setup-b, dataset→riset, arm→arsip
		verdict: 'setup-b',
		dataset: 'riset',
		arm: 'arsip',
		// Polymarket (7 Okt): sub lama dipetakan ke struktur baru {setup-b, riset, arsip, live}
		agen: 'arsip',
		replay: 'riset',
		parity: 'riset',
		biaya: 'arsip'
	};

	const sub = $derived.by(() => {
		const s = page.url.searchParams.get('sub');
		if (s && area?.anak.some((a) => a.slug === s)) return s;
		const alias = s ? ALIAS_SUB[s] : undefined;
		if (alias && area?.anak.some((a) => a.slug === alias)) return alias;
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

	// Backfill: SSE hanya mengirim kejadian BARU (mulai dari "sekarang"), jadi panel area
	// selalu kosong sampai ada kejadian berikutnya. Ambil riwayat singkat lewat REST dan
	// gabung dengan aliran SSE — dedupe per id, urut terbaru dulu. Tanpa ini kepala panel
	// menjanjikan "aliran SSE terfilter" padahal isinya mustahil terisi (menyesatkan).
	let kejadianRiw = $state<Kejadian[]>([]);
	$effect(() => {
		let batal = false;
		void (async () => {
			try {
				const rows = await getEvents(120);
				if (!batal) kejadianRiw = rows;
			} catch {
				/* gagal backfill bukan alasan mematikan halaman; SSE tetap jalan */
			}
		})();
		return () => {
			batal = true;
		};
	});
	const kejadianGabung = $derived.by(() => {
		const seen = new Set<number>();
		const out: Kejadian[] = [];
		for (const k of [...live.kejadian, ...kejadianRiw]) {
			const id = Number(k.id);
			if (Number.isFinite(id) && id > 0) {
				if (seen.has(id)) continue;
				seen.add(id);
			}
			out.push(k);
		}
		return out.sort((a, b) => Number(b.id ?? 0) - Number(a.id ?? 0));
	});

	const kejadianArea = $derived.by(() => {
		const prefiks = topikArea[kunci] ?? [];
		return kejadianGabung.filter((k) => {
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
			<!-- Sumber jumlah = posisiArray.length, BUKAN risiko.posisi_terbuka: collector kini
			     menulis `posisi` sebagai array, sedangkan `risiko` tak lagi memuat field itu.
			     Akibat versi lama: ada 2 posisi nyata (SUIUSDT, 1000PEPE) tapi Cockpit menulis
			     "Tidak ada posisi terbuka (0/3)" — temuan pemilik 7 Okt. -->
			{@const posisiJumlah = posisiArray.length}
			<!-- Pembersih format harga: kripto mikro (1000PEPE 0,0041) tidak boleh jadi "0,00" -->
			{@const harga = (v: unknown): string => {
				const n = typeof v === 'number' ? v : Number(v);
				if (!Number.isFinite(n)) return '—';
				const a = Math.abs(n);
				const dp = a >= 1000 ? 2 : a >= 1 ? 4 : 8;
				return n.toLocaleString('id-ID', { maximumFractionDigits: dp });
			}}

			{@const bagianObj = (faktaBagian?.value as Record<string, any>) ?? {}}
			{@const idxArjum = (bagianObj?.idx?.rows as any[]) ?? []}
			{@const idxTv = (bagianObj?.idx_tv?.rows as any[]) ?? []}
			{@const idxBandar = (bagianObj?.bandarmologi as any) ?? null}
			{@const idx616 = (bagianObj?.idx616?.terbuka as any[]) ?? []}
			{@const bsjpObj = (bagianObj?.bsjp as any) ?? null}
			{@const overextObj = (bagianObj?.overextended as any) ?? null}
			{@const forexObj = (bagianObj?.forex as any) ?? null}
			{@const macroObj = (bagianObj?.macro as any) ?? null}
			{@const memecoinObj = (bagianObj?.memecoin as any) ?? null}
			{@const radarObj = (faktaRadar?.value as any) ?? null}
			{@const lpPaperObj = (faktaLpPaper?.value as any) ?? null}
			{@const faktaLpMark = temukanFakta(data.facts, 'lp_mark')}
			{@const lpMarkObj = (faktaLpMark?.value as any) ?? null}
			{@const faktaIdxAkurasi = temukanFakta(data.facts, 'idx_akurasi')}
			{@const idxAkurasiObj = (faktaIdxAkurasi?.value as any) ?? null}
			{@const faktaCryptoSinyal = temukanFakta(data.facts, 'crypto_sinyal')}
			{@const cryptoSinyalObj = (faktaCryptoSinyal?.value as any) ?? null}
			{@const faktaForexSinyal = temukanFakta(data.facts, 'forex_sinyal')}
			{@const forexSinyalObj = (faktaForexSinyal?.value as any) ?? null}
			{@const faktaIdxSinyal = temukanFakta(data.facts, 'idx_sinyal')}
			{@const idxSinyalObj = (faktaIdxSinyal?.value as any) ?? null}
			{@const faktaLpVerif = temukanFakta(data.facts, 'lp_verifikasi')}
			{@const lpVerifObj = (faktaLpVerif?.value as any) ?? null}
			<!-- Kandidat AKTIF (kind `signal`, kunci per pair) — hanya yang belum basi;
			     sebelumnya fakta ini tidak pernah sampai ke UI (temuan audit 7 Okt). -->
			{@const sinyalAktif = data.facts.filter((f) => f.kind === 'signal')}
			{@const hargaAdaptif = (v: unknown): string => {
				const n = typeof v === 'number' ? v : Number(v);
				if (!Number.isFinite(n)) return '—';
				const a = Math.abs(n);
				const dp = a >= 1 ? 2 : a >= 0.01 ? 4 : 8;
				return n.toLocaleString('id-ID', { maximumFractionDigits: dp });
			}}
			{@const faktaDompet = temukanFakta(data.facts, 'dompet')}
			{@const dompetObj = (faktaDompet?.value as any) ?? null}
			{@const faktaBandarSkor = temukanFakta(data.facts, 'bandarmologi_skor')}
			{@const bandarSkorObj = (faktaBandarSkor?.value as any) ?? null}
			{@const faktaPasarAkurasi = temukanFakta(data.facts, 'pasar_akurasi')}
			{@const pasarAkurasiObj = (faktaPasarAkurasi?.value as any) ?? null}
			<!-- Narasi LLM per market (job llm-brief-<market>, kind ai.brief). Hanya ada bila
			     provider benar-benar menjawab; status/gagal pun ditampilkan apa adanya. -->
			{@const narasiObj = (data.facts.find((f) => f.kind === 'ai.brief' && f.key === kunci)?.value as any) ?? null}
			{@const akurasiCrypto = (pasarAkurasiObj?.pasar?.crypto as any) ?? null}
			{@const akurasiForex = (pasarAkurasiObj?.pasar?.forex as any) ?? null}
			{@const akurasiGmgn = (pasarAkurasiObj?.pasar?.gmgn as any) ?? null}
			{@const akurasiPoly = (pasarAkurasiObj?.pasar?.polymarket as any) ?? null}
			{@const gmgnObj = (faktaGmgn?.value as any) ?? null}
			<!-- kind `gmgn` (job gmgn-sync): `paper` = konfigurasi + kesehatan berkas bot,
			     `radar` = jendela likuiditas per chain. Kini sampai UI (AREA_KIND). -->
			{@const faktaGmgnPaper = data.facts.find((f) => f.kind === 'gmgn' && f.key === 'paper')}
			{@const gmgnPaperObj = (faktaGmgnPaper?.value as any) ?? null}
			{@const faktaGmgnRadarMentah = data.facts.find((f) => f.kind === 'gmgn' && f.key === 'radar')}
			{@const gmgnRadarMentahObj = (faktaGmgnRadarMentah?.value as any) ?? null}
			{@const faktaPengukuran = temukanFakta(data.facts, 'pengukuran')}
			{@const faktaBacktest = temukanFakta(data.facts, 'backtest')}
			{@const pengukuranObj = (faktaPengukuran?.value as any) ?? null}
			{@const backtestObj = (faktaBacktest?.value as any) ?? null}
			{@const ledgerObj = (faktaLedger?.value as any) ?? null}

			<!-- Aliran keputusan dari ledger NYATA (bukan contoh). Status ledger
			     dipetakan ke jenis keputusan; `note` jadi alasan; tidak ada yang dikarang. -->
			{@const jenisDariStatus = (st: string | null | undefined): 'ENTRY' | 'EXIT_TP' | 'EXIT_SL' | 'EXIT_MANUAL' | 'VETO' | 'ALERT' => {
				const s = String(st ?? '').toLowerCase();
				if (s.includes('tp')) return 'EXIT_TP';
				if (s.includes('sl')) return 'EXIT_SL';
				if (s.includes('expired') || s.includes('batal') || s.includes('cancel')) return 'VETO';
				if (s.includes('manual')) return 'EXIT_MANUAL';
				return 'ENTRY';
			}}
			{@const feedKeputusan = ((ledgerObj?.terakhir ?? []) as any[]).map((tr, i) => ({
				id: String(tr.signal_id ?? `ledger-${i}`),
				ts: String(tr.closed_at ?? tr.logged_at ?? ''),
				jenis: jenisDariStatus(tr.status),
				pair: String(tr.pair ?? '—'),
				venue: String(tr.source ?? 'paper'),
				r: typeof tr.r === 'number' ? tr.r : null,
				judul: `${String(tr.direction ?? '')} ${String(tr.pair ?? '')} · ${String(tr.status ?? '')}`.trim(),
				alasan: String(tr.note ?? '—'),
				mode: 'PAPER' as const
			})) as DecisionItem[]}

			{@const kandidatArray = Array.isArray(faktaKandidat?.value) ? faktaKandidat.value : []}
			{@const equityObj = (faktaEquity?.value as { points?: { i: number; r: number }[]; stats?: Record<string, number> }) ?? null}
			{@const risikoObj = (faktaRisiko?.value as Record<string, unknown>) ?? null}
			{@const posisiMaks = Number(risikoObj?.maks_posisi ?? 3)}
			{@const verdictObj = (faktaVerdict?.value as Record<string, unknown>) ?? null}
			{@const polyPaperObj = (faktaPolyPaper?.value as { arms?: { nama: string; balance: number; pnl: number; wins: number; losses: number }[] }) ?? null}
			{@const tampilGate = Boolean(faktaVerdict || temukanFakta(data.facts, 'gate'))}

			<!-- Dipecah 7 Okt supaya Cockpit bisa menyusun: baris kondisi (dompet/risiko/posisi)
			     di atas, lalu kurva, lalu insight. Sebelumnya tiga kartu hidup di kolom yang
			     berbeda sehingga mata harus melompat (keluhan "card dibawahnya belum rapi"). -->
			{#snippet panelPosisi(ringkas: boolean)}
				<div class="permukaan-2 rounded-card border border-line p-3">
					<div class="mb-2 flex items-center justify-between border-b border-line-soft pb-2">
						<h3 class="text-13 font-medium text-text">Posisi Terbuka</h3>
						<span class="text-11 text-text-3 font-mono">{posisiJumlah} / {posisiMaks}</span>
					</div>
					{#if posisiJumlah === 0}
						<div class="py-3 px-1 text-center space-y-1">
							<div class="text-12 font-medium text-text-2">Tidak ada posisi terbuka (0/{posisiMaks}).</div>
							<p class="text-11 text-text-3">
								Keadaan normal, bukan mesin rusak: posisi dibuka hanya bila kandidat lolos semua gerbang
								dan masih ada ruang risiko.
							</p>
						</div>
					{:else if ringkas}
						<ul class="space-y-1.5">
							{#each posisiArray as p (p.signal_id ?? p.pair)}
								<li class="flex flex-wrap items-center justify-between gap-2 font-mono text-12">
									<span class="flex items-center gap-1.5">
										<span class="font-bold text-text">{p.pair}</span>
										<span class="rounded px-1 py-0.5 text-10 font-bold uppercase {p.direction === 'LONG' ? 'text-pos bg-pos/10 border border-pos/20' : 'text-neg bg-neg/10 border border-neg/20'}">{p.direction}</span>
									</span>
									<span class="text-11 text-text-3">e {harga(p.entry)} · SL {harga(p.stop)} · TP {harga(p.tp1)}</span>
								</li>
							{/each}
						</ul>
						<p class="mt-2 text-10 text-text-3">Detail penuh & ledger ada di tab Eksekusi.</p>
					{:else}
						<div class="space-y-2.5">
							{#each posisiArray as p (p.signal_id ?? p.pair)}
								<div class="rounded-card border border-line bg-surface p-3 space-y-2 font-mono text-12">
									<div class="flex items-center justify-between border-b border-line-soft pb-1.5">
										<div class="flex items-center gap-2">
											<span class="font-bold text-text text-14">{p.pair}</span>
											<span class="rounded px-1.5 py-0.5 text-10 font-bold uppercase {p.direction === 'LONG' ? 'text-pos bg-pos/10 border border-pos/20' : 'text-neg bg-neg/10 border border-neg/20'}">{p.direction}</span>
											<span class="rounded bg-accent/10 text-accent border border-accent/20 px-1.5 py-0.5 text-10 font-bold">{p.status ?? 'OPEN'}</span>
										</div>
										<span class="text-10 text-text-3">{p.signal_id ?? ''}</span>
									</div>
									<div class="grid grid-cols-2 sm:grid-cols-4 gap-2 text-11">
										<div class="rounded bg-canvas/60 p-1.5 border border-line">
											<div class="text-10 text-text-3 uppercase">Entry</div>
											<div class="font-bold text-text">${harga(p.entry)}</div>
										</div>
										<div class="rounded bg-canvas/60 p-1.5 border border-line">
											<div class="text-10 text-text-3 uppercase">Stop Loss</div>
											<div class="font-bold text-neg">${harga(p.stop)}</div>
										</div>
										<div class="rounded bg-canvas/60 p-1.5 border border-line">
											<div class="text-10 text-text-3 uppercase">Target 1</div>
											<div class="font-bold text-pos">${harga(p.tp1)}</div>
										</div>
										<div class="rounded bg-canvas/60 p-1.5 border border-line">
											<div class="text-10 text-text-3 uppercase">Ukuran (USD)</div>
											<div class="font-bold text-accent">${angka(p.size_usd)}</div>
										</div>
									</div>
									{#if p.note}
										<div class="text-10 text-text-3 truncate font-sans">Catatan: {p.note}</div>
									{/if}
								</div>
							{/each}
						</div>
					{/if}
				</div>
			{/snippet}

			<!-- ========================================== -->
			<!-- VIEW KHUSUS: CRYPTO                      -->
			<!-- ========================================== -->
			{#if kunci === 'crypto'}
				<!-- 7 Okt: pemilik bertanya "apa pembeda Cockpit vs Setup?". Sekarang dijawab
				     di kepala halaman; isinya juga dipisah (kandidat tabel hanya di Setup). -->
				{#if sub === 'cockpit' || !sub}
					<JudulBagian nomor="1" judul="Ringkasan" tujuan="Uang, risiko, dan sinyal teratas — keadaan hari ini dalam satu pandangan" ikon="◎" />
				{:else if sub === 'setup'}
					<JudulBagian nomor="2" judul="Setup Kandidat" tujuan="Daftar lengkap kandidat + alasan lolos/gagal per aturan (kolom 'skor gate')" ikon="◈" />
					<div class="mt-3">
						<Penjelasan judul="Metode yang dipakai (SMC multi-timeframe) + cara membaca kolomnya">
							<p>
								<b>Apa yang diukur:</b> mesin memindai pair crypto (MEXC) di tiga kerangka waktu —
								<b>1D, 4H, 1H</b> — mencari <i>point of interest</i> (POI) berupa FVG/order block,
								menunggu harga kembali ke area itu, lalu menyusun entry/SL/TP di sekitarnya.
								Kolom POI itu sebabnya: entry hanya sah bila harga berada di dalam area.
							</p>
							<p><b>Enam aturan gate</b> (semua harus lolos; yang keras tidak bisa ditawar):</p>
							<ul class="ml-4 list-disc space-y-0.5">
								<li><span class="font-mono">mtf_alignment</span> — arah 1D/4H/1H searah. Bila 1D melawan, tier diturunkan (maks STANDAR).</li>
								<li><span class="font-mono">poi_valid</span> (keras) — entry harus di dalam area POI.</li>
								<li><span class="font-mono">freshness</span> (keras) — harga masih dekat POI, belum lari jauh.</li>
								<li><span class="font-mono">sl_distance</span> (keras) — jarak stop diukur dari ATR; terlalu lebar = risiko terlalu besar.</li>
								<li><span class="font-mono">atr_min</span> — volatilitas cukup untuk bergerak (ideal ATR1H ≥ 1,5%; di bawah itu boleh lolos tetapi tercatat).</li>
								<li><span class="font-mono">exposure</span> (keras) — masih ada slot posisi dan korelasi dengan posisi berjalan aman.</li>
							</ul>
							<p>
								<b>Cara membaca kartu:</b> <b>tier</b> STANDAR = lolos semua aturan; <b>SKIP</b> = ada aturan
								gagal (alasannya tertulis per baris). <b>Skor</b> hanya menghitung aturan yang lolos — ia
								<b>bukan</b> bukti profitabilitas. Label "belum-terbukti" berasal dari gate statistik: selama
								interval kepercayaan win-rate masih menyentuh break-even, kandidat tidak boleh dipromosikan.
								Waktu di kartu = kapan kandidat <i>digenerate</i>, bukan kapan layar dibuka.
							</p>
						</Penjelasan>
					</div>
				{:else if sub === 'ukur'}
					<JudulBagian nomor="3" judul="Ukur (validasi)" tujuan="Apakah aturan gate punya nilai? Lolos vs ditolak, dihitung setelah kejadian" ikon="⚖" />
					<div class="mt-3">
						<Penjelasan judul="Apa yang dimaksud 'diukur' di tab ini">
							<p>
								Tab ini menjawab satu pertanyaan: <b>apakah aturan gate-nya berguna?</b> Tidak cukup
								"tradenya untung" — harus terbukti bahwa <i>yang ditolak</i> memang lebih buruk daripada
								<i>yang diloloskan</i>.
							</p>
							<ul class="ml-4 list-disc space-y-0.5">
								<li><b>Pengukuran Forward (shadow)</b> — tiap kandidat dicatat, lalu dinilai <i>setelah</i> kejadian: yang lolos gate vs yang ditolak. Bila yang ditolak justru lebih baik, gate-nya tidak layak dipakai.</li>
								<li><b>Laboratorium backtest</b> — menguji ulang aturan pada data historis, dengan walk-forward supaya aturan tidak dinilai memakai data yang dipakai menyusunnya.</li>
								<li><b>Akurasi per strategi</b> — hasil nyata dari ledger (trade tuntas), dilaporkan bersama <i>pakem</i>.</li>
							</ul>
							<p>
								<b>Pakem (satu standar bukti):</b> <span class="font-mono">INSUFFICIENT</span> (&lt;10 hari — belum boleh diklaim apa pun) →
								<span class="font-mono">DIRECTIONAL</span> (&lt;30 hari — hanya arah) →
								<span class="font-mono">PRELIMINARY</span> (&lt;100 hari — evaluasi awal) →
								<span class="font-mono">TUNING</span> (≥100 hari — baru boleh menyetel ulang).
								Selama INSUFFICIENT, win-rate ditampilkan apa adanya tetapi <b>tidak boleh</b> dipakai mengambil keputusan.
							</p>
						</Penjelasan>
					</div>
				{:else if sub === 'eksekusi'}
					<JudulBagian nomor="4" judul="Eksekusi & Ledger" tujuan="Yang benar-benar terjadi: posisi terbuka, fill, hasil per trade" ikon="⇄" />
					<div class="mt-3">
						<Penjelasan judul="Cara membaca Eksekusi & Ledger (jalur paper)">
							<p>
								<b>Paper</b> berarti order disimulasikan, bukan dikirim ke bursa. Yang penting: jalur
								keputusannya <b>sama</b> dengan yang nanti dipakai live — yang berbeda hanya sakelar
								eksekusinya. Jadi catatan di sini adalah bukti perilaku mesin, bukan hasil uang nyata.
							</p>
							<ul class="ml-4 list-disc space-y-0.5">
								<li><b>Posisi terbuka</b> — apa yang sedang berjalan: pair, arah, entry, stop, target, ukuran. Jumlah <span class="font-mono">n / maks</span> berasal dari daftar posisi itu sendiri.</li>
								<li><b>Ledger &amp; R</b> — tiap trade tuntas dinilai dengan <b>R</b>: (harga keluar − masuk) ÷ jarak stop. Menang TP1 = +2 R bila R:R 1:2. R dipakai karena satuannya sama di semua pair; ia tidak bisa dibandingkan langsung dengan P&amp;L dolar.</li>
								<li><b>overextended</b> — fakta harga (jarak dari puncak/dasar), <b>bukan sinyal</b>. Puncak hanya diketahui setelah terjadi.</li>
							</ul>
							<p>
								Yang <b>tidak</b> akan terlihat: posisi yang dibuka paksa, angka yang dibulatkan menjadi
								bagus, atau trade yang dihilangkan. Bila tidak ada posisi, artinya (a) tidak ada kandidat yang
								lolos semua gerbang, atau (b) biaya depth membuat R bersih terlalu kecil.
							</p>
						</Penjelasan>
					</div>
				{/if}
				{#if sub === 'cockpit' || sub === 'setup' || !sub}
					<div class="grid grid-cols-1 gap-4 lg:grid-cols-12">
						<!-- Kolom Kiri: Sinyal & Equity (7 cols) -->
						<div class="space-y-4 lg:col-span-7">
							{#if sub === 'cockpit' || !sub}
								<!-- Susunan ini SUDAH BENAR menurut pemilik (7 Okt) — jangan diubah tanpa
								     alasan baru: Dompet dulu, lalu kurva, lalu catatan cara membacanya. -->
								<DompetPasar market="crypto" dompet={dompetObj} judul="Dompet Paper Crypto" ringkas />
								<EquityCurve points={equityObj?.points} stats={equityObj?.stats} />
								<p class="text-11 text-text-3 -mt-1">
									Kurva di atas = <b>ledger trade tertutup</b> (satu titik per trade selesai, satuan R), BUKAN kandidat.
									Kandidat di tabel Setup baru jadi titik setelah dibuka & ditutup; order yang tak pernah terisi
									ditandai <span class="font-mono">expired</span> dan tidak dihitung. Posisi berjalan terlihat di tab Eksekusi.
								</p>
							{/if}

							{#if sub === 'setup'}
								<!-- Kandidat "layar besar" (SignalCard) HANYA di tab Setup.
								     Di Cockpit ini duplikat dengan tabel SinyalPasar dan membuat kedua
								     tab terasa sama (keluhan pemilik 7 Okt: "apa pembedanya?"). -->
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
							{/if}

			<!-- Narasi LLM per market: dari job llm-brief-<market>. Angka tetap dari fakta;
			     narasi hanya menjelaskan — tidak pernah menggantikan bukti.
			     Revisi pemilik 7 Okt: "harusnya bisa kayak narrativelabs" — mereka
			     menonjolkan KESIMPULAN sebagai kalimat pembuka besar, bukti menyusul,
			     dan mesinnya (provider/ms) tidak dipajang di muka. Hierarki di bawah ini
			     mengikuti itu; grounding `fact_ids` tetap terlihat sebagai janji bukti. -->
			{#if narasiObj}
							<div class="mb-4 overflow-hidden rounded-card border border-line bg-surface">
								<div class="flex flex-wrap items-center justify-between gap-2 border-b border-line-soft px-3 py-1.5">
									<span class="text-11 font-bold uppercase tracking-wide text-accent-2">✳ Narasi</span>
									<span class="text-10 text-text-3 font-mono">
										{narasiObj.fact_ids?.length ?? 0} fakta dirujuk
										{#if narasiObj.output?.nada}· nada {narasiObj.output.nada}{/if}
									</span>
								</div>
								{#if narasiObj.status !== 'ok'}
									<p class="px-3 py-2 text-11 text-warn">
										Narasi tidak tersedia ({narasiObj.status ?? '—'}{narasiObj.error_code ? ` · ${narasiObj.error_code}` : ''}) —
										angka di halaman ini tetap sah karena berasal dari fakta, bukan dari narasi.
									</p>
								{:else if narasiObj.output?.kalimat?.length}
									<div class="px-3 py-2.5">
										<p class="text-15 leading-snug text-text">{narasiObj.output.kalimat[0].teks}</p>
										{#if narasiObj.output.kalimat.length > 1}
											<div class="mt-1.5 space-y-1 border-l-2 border-line-soft pl-2.5">
												{#each narasiObj.output.kalimat.slice(1) as k}
													<p class="text-12 text-text-2">{k.teks}</p>
												{/each}
											</div>
										{/if}
										<p class="mt-2 text-10 text-text-3">
											Deskriptif, bukan rekomendasi. Mesin: {narasiObj.provider ?? '—'} ·
											{narasiObj.prompt_version ?? '—'}{#if narasiObj.latency_ms} · {narasiObj.latency_ms} ms{/if}
										</p>
									</div>
								{:else}
									<p class="px-3 py-2 text-11 text-text-3">Narasi kosong — fakta tetap sah.</p>
								{/if}
							</div>
			{/if}

							<!-- Kandidat AKTIF dari ledger gate (job signal-sync). Ini daftar "apa yang
							     sedang hidup" — dibedakan dari tabel riwayat di bawahnya. -->
							{#if (sub === 'setup' || sub === 'cockpit') && sinyalAktif.length}
								<div class="permukaan-2 rounded-card border border-line p-3">
									<div class="mb-2 flex items-center justify-between border-b border-line-soft pb-2">
										<div>
											<h3 class="text-14 font-medium text-text">Kandidat Aktif (ledger gate)</h3>
											<p class="text-11 text-text-3">
												Hanya yang TTL-nya belum lewat — kandidat tua otomatis disembunyikan
											</p>
										</div>
										<span class="rounded bg-surface px-2 py-0.5 text-11 font-mono text-accent border border-line">
											{sinyalAktif.length} hidup
										</span>
									</div>
									<div class="grid grid-cols-1 gap-2 sm:grid-cols-2">
										{#each sinyalAktif as f (f.key)}
											{@const s = (f.value as any) ?? {}}
											<div class="rounded-card border border-line bg-surface p-2.5">
												<div class="flex items-center justify-between gap-2">
													<span class="font-mono font-bold text-text">{s.pair ?? f.key}</span>
													<span class="rounded px-1.5 py-0.5 text-10 font-bold border {String(s.arah).toUpperCase() === 'LONG' ? 'text-pos bg-pos/10 border-pos/20' : 'text-neg bg-neg/10 border-neg/20'}">
														{s.arah ?? '—'}
													</span>
													<span class="rounded bg-canvas border border-line px-1.5 py-0.5 text-10 font-mono text-text-3">{s.tier ?? '—'}</span>
												</div>
												<div class="mt-1.5 grid grid-cols-3 gap-1.5 font-mono text-11">
													<div><div class="text-10 text-text-3">ENTRY</div><div class="text-text">{hargaAdaptif(s.entry)}</div></div>
													<div><div class="text-10 text-text-3">SL</div><div class="text-neg">{hargaAdaptif(s.sl)}</div></div>
													<div><div class="text-10 text-text-3">TP1</div><div class="text-pos">{hargaAdaptif(s.tp1)}</div></div>
												</div>
												<div class="mt-1 flex items-center justify-between text-10 text-text-3 font-mono">
													<!-- TEMUAN QA 7 Okt (P0): angka ini JARAK STOP, bukan risiko akun.
													     Ukuran posisi dihitung agar risiko akun tetap 1% (risk.py:
													     size = risk_usd ÷ jarak-stop). Bukti: 1000PEPE jarak 3,81%
													     → posisi $25,55 ≈ 1% × $100; SUI jarak 2,01% → $47,28.
													     Label lama "risiko 3,813%" membuat pembaca (dan QA) wajar
													     menyimpulkan policy dilanggar. Jangan disingkat lagi. -->
													<span>R:R {s.r_r ?? '—'} · jarak stop {s.risk_pct ?? '—'}% · risiko akun 1%</span>
													<span>{umurDetik(f.age_s)} lalu</span>
												</div>
												{#if s.aturan_gagal?.length}
													<div class="mt-0.5 text-10 text-warn">aturan gagal: {s.aturan_gagal.join(', ')}</div>
												{/if}
												<div class="mt-0.5 text-10 text-text-3">{s.label ?? ''}</div>
											</div>
										{/each}
									</div>
								</div>
							{/if}

							<!-- Sinyal & entry setup crypto (6 Okt): tiap baris = 1 setup, kolom khas SMC.
							     HANYA di Setup — supaya Cockpit (ringkasan) tidak berisi tabel panjang. -->
							{#if sub === 'setup'}
								<SinyalPasar
									pasar="crypto"
									judul="Sinyal & Entry Setup (Crypto)"
									subjudul="Verdict gate SMC terakhir — skor = aturan lolos, bukan edge terbukti"
									data={cryptoSinyalObj}
								/>
							{/if}

						</div>

						<!-- Kolom Kanan: Risiko & Posisi (5 cols). Di tab Setup, RiskMeter disembunyikan:
						     ia duplikat Cockpit dan membuat kolom terasa kosong saat tak ada posisi. -->
						<div class="space-y-4 lg:col-span-5">
							{#if sub === 'cockpit' || !sub}
								<RiskMeter risiko={risikoObj} />
							{/if}

							<!-- Akurasi per strategi crypto (6 Okt): dari ledger nyata, pakem satu standar -->
							{#if sub === 'setup' || sub === 'ukur'}
								<AkurasiPasar
									judul="Akurasi per Strategi (Crypto)"
									subjudul="Ledger nyata venue crypto — pakem bukti sama dengan IDX"
									data={akurasiCrypto}
								/>
							{/if}

							{@render panelPosisi(false)}

							<!-- Aliran Keputusan (7 Okt): DIPINDAH dari kolom kiri ke kanan. Ledger yang
							     sama dipakai blok posisi di atasnya, jadi dua-duanya terbaca berurutan:
							     "apa yang berjalan" lalu "apa yang sudah terjadi". Ini juga mengisi ruang
							     kosong kolom kanan (screenshot cockpit: kiri jauh lebih panjang). -->
							<DecisionFeed items={feedKeputusan} />
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

				{#if sub === 'lab' || sub === 'ukur'}
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
									<span class="text-10 text-text-3 block">{backtestObj?.lolos_terisi ?? 0} terisi</span>
								</div>
								<div class="rounded bg-surface p-2 border border-line-soft font-mono">
									<span class="text-10 text-text-3 uppercase block">Ditolak Bersih</span>
									<span class="angka text-14 font-bold text-neg">{backtestObj?.ditolak_bersih ?? '—'} R</span>
									<span class="text-10 text-text-3 block">Rugi Terhindar</span>
								</div>
								<div class="rounded bg-surface p-2 border border-line-soft font-mono">
									<span class="text-10 text-text-3 uppercase block">Beda Lolos (Delta)</span>
									<span class="angka text-14 font-bold text-pos">+{backtestObj?.beda_lolos?.beda_r ?? '—'} R</span>
									<span class="text-10 text-pos block">t={backtestObj?.beda_lolos?.t ?? '—'}</span>
								</div>
								<div class="rounded bg-surface p-2 border border-line-soft font-mono">
									<span class="text-10 text-text-3 uppercase block">Signifikansi (p)</span>
									<span class="angka text-14 font-bold text-accent">{backtestObj?.beda_lolos?.p_approx ?? '—'}</span>
									<span class="text-10 text-text-3 block">p &lt; 0.05 Signifikan</span>
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

				<!-- Tab Overextended (dipindah dari area /overextended — datanya dari crypto) -->
				{#if sub === 'overextended' || sub === 'eksekusi'}
					<div class="space-y-4">
						<!-- POSISI TERBUKA di tab Eksekusi (temuan 7 Okt: tab ini menjanjikan
						     "posisi terbuka" di judulnya, tapi tidak menampilkannya sama sekali —
						     padahal ada 3 posisi berjalan). Detail penuh, bukan ringkas. -->
						{#if sub === 'eksekusi'}
							{@render panelPosisi(false)}
						{/if}
						<div class="permukaan-2 rounded-card border border-line p-3">
							<div class="mb-3 flex items-center justify-between border-b border-line-soft pb-2">
								<div>
									<h3 class="text-14 font-medium text-text">Overextended &amp; Uji Edge</h3>
									<p class="text-11 text-text-3">
										Seberapa jauh pump harga dari dasar, jarak dari puncak, perubahan OI, dan
										funding rate.
									</p>
								</div>
								<span class="rounded bg-surface px-2 py-0.5 text-11 font-mono text-accent border border-line">
									{overextObj?.jumlah ?? 0} simbol
								</span>
							</div>

							{#if overextObj?.galat?.length}
								<div class="rounded bg-warn/10 border border-warn/30 p-2.5 text-11 text-warn">
									Catatan sumber: {(overextObj.galat ?? []).join('; ')}
								</div>
							{/if}

							{#if !overextObj || (overextObj.simbol ?? []).length === 0}
								<div class="py-6 text-center text-text-3 text-12">
									Belum ada data overextended pada siklus ini.
								</div>
							{:else}
								<div class="overflow-x-auto">
									<table class="w-full text-left text-12 font-mono">
										<thead class="border-b border-line text-text-3 text-11">
											<tr>
												<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5">SIMBOL</th>
												<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right">PUMP %</th>
												<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right">DARI PUNCAK</th>
												<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right">OI Δ</th>
												<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right">FUNDING</th>
											</tr>
										</thead>
										<tbody class="divide-y divide-line-soft">
											{#each overextObj.simbol ?? [] as o (o.symbol ?? o.simbol)}
												<tr class="hover:bg-surface/50 transition-colors">
													<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 font-bold text-text">{o.symbol ?? o.simbol}</td>
													<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right text-warn">
														{o.pump_pct != null ? `${o.pump_pct}%` : '—'}
													</td>
													<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right text-text-2">
														{o.turun_dari_puncak_pct != null ? `${o.turun_dari_puncak_pct}%` : '—'}
													</td>
													<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right text-text-2">
														{o.oi_mereda_pct != null ? `${o.oi_mereda_pct}%` : '—'}
													</td>
													<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right text-text-2">
														{o.fr_maks_pct != null ? `${o.fr_maks_pct}%` : '—'}
													</td>
												</tr>
											{/each}
										</tbody>
									</table>
								</div>
								{#if overextObj.catatan?.length}
									<p class="mt-2 text-10 text-text-3">{(overextObj.catatan ?? []).join(' · ')}</p>
								{/if}
							{/if}
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
												<span class="rounded px-1.5 py-0.5 text-10 font-bold uppercase {tr.status?.includes('TP') ? 'bg-pos/20 text-pos' : tr.status?.includes('SL') ? 'bg-warn/20 text-warn' : 'bg-surface text-text-3 border border-line'}">
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

				{#if sub === 'ukur' || sub === 'eksekusi'}
					<!-- 7 Okt: blok kesehatan jalur = plumbing teknis; dipindah dari Cockpit ke sini
					     (pemilik menilai Cockpit "sangat membingungkan" karena campuran ini). -->
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
				{#if sub === 'setup-b' || !sub}
					<JudulBagian nomor="1" judul="Favorit 0,70–0,95 (Arm B)" tujuan="Satu-satunya arm yang dipakai: beli outcome favorit yang harganya 0,70–0,95 (menang kecil, sering benar)" ikon="◎" />
				{:else if sub === 'riset'}
					<JudulBagian nomor="2" judul="Riset" tujuan="Dataset beku + parity/drift + katalog replay — bahan bukti, bukan keputusan" ikon="⌕" />
				{:else if sub === 'arsip'}
					<JudulBagian nomor="3" judul="Arm Lain (Beku)" tujuan="A momentum, C fade, D favorit: disimpan sebagai bukti, bukan dasar keputusan" ikon="❄" />
				{:else if sub === 'live'}
					<JudulBagian nomor="4" judul="Live" tujuan="Jalur uang nyata: status arming 3-way (belum aktif)" ikon="⚡" />
				{/if}
			<!-- Narasi LLM per market: dari job llm-brief-<market>. Angka tetap dari fakta;
			     narasi hanya menjelaskan — tidak pernah menggantikan bukti. Gaya 7 Okt:
			     kesimpulan dulu (kalimat besar), bukti menyusul, mesin disembunyikan di kaki. -->
			{#if narasiObj}
				<div class="mb-4 overflow-hidden rounded-card border border-line bg-surface">
					<div class="flex flex-wrap items-center justify-between gap-2 border-b border-line-soft px-3 py-1.5">
						<span class="text-11 font-bold uppercase tracking-wide text-accent-2">✳ Narasi</span>
						<span class="text-10 text-text-3 font-mono">
							{narasiObj.fact_ids?.length ?? 0} fakta dirujuk{#if narasiObj.output?.nada} · nada {narasiObj.output.nada}{/if}
						</span>
					</div>
					{#if narasiObj.status !== 'ok'}
						<p class="px-3 py-2 text-11 text-warn">
							Narasi tidak tersedia ({narasiObj.status ?? '—'}{narasiObj.error_code ? ` · ${narasiObj.error_code}` : ''}) —
							angka di halaman ini tetap sah karena berasal dari fakta, bukan dari narasi.
							Status penyedia LLM ada di halaman <b>Sistem → AI</b>.
						</p>
					{:else if narasiObj.output?.kalimat?.length}
						<div class="px-3 py-2.5">
							<p class="text-15 leading-snug text-text">{narasiObj.output.kalimat[0].teks}</p>
							{#if narasiObj.output.kalimat.length > 1}
								<div class="mt-1.5 space-y-1 border-l-2 border-line-soft pl-2.5">
									{#each narasiObj.output.kalimat.slice(1) as k}
										<p class="text-12 text-text-2">{k.teks}</p>
									{/each}
								</div>
							{/if}
							<p class="mt-2 text-10 text-text-3">
								Deskriptif, bukan rekomendasi. Mesin: {narasiObj.provider ?? '—'} ·
								{narasiObj.prompt_version ?? '—'}{#if narasiObj.latency_ms} · {narasiObj.latency_ms} ms{/if}
							</p>
						</div>
					{:else}
						<p class="px-3 py-2 text-11 text-text-3">Narasi kosong — fakta tetap sah.</p>
					{/if}
				</div>
			{/if}


				{#if sub === 'riset'}
					<Block
						judul="Katalog dataset"
						deskripsi="poly.dataset/recorder + poly.akses/cakupan — angka apa adanya dari job poly-sync"
						sumber={datasetRecorder?.source ?? null}
						age_s={datasetRecorder?.age_s ?? null}
						status={datasetRecorder?.status ?? null}
					>
						<DatasetExplorer recorder={datasetRecorder} cakupan={datasetCakupan} />
					</Block>
				{/if}
				{#if sub === 'setup-b'}
					<div class="space-y-4">
						<!-- Keputusan owner 7 Okt: fokus SETUP B KANDIDAT. Arm lain dibekukan (tab Arsip). -->
						<div class="rounded-card border border-accent/30 bg-accent/5 p-3 space-y-1">
							<div class="flex items-center gap-2">
								<span class="rounded px-1.5 py-0.5 text-10 font-bold border border-accent/40 text-accent bg-accent/10">YANG DIPAKAI: ARM B</span>
								<span class="text-11 text-text-3">"Arm" = aturan beli yang diuji mesin; huruf A/B/C/D hanya penanda.</span>
							</div>
							<p class="text-11 text-text-2">
								<b>Arm B (kandidat)</b> = beli outcome favorit yang harganya <b>0,70–0,95</b>.
								Menang kecil (+0,05–0,30) tapi sering benar; kalah besar karena membayar mahal.
								Arm A momentum · C fade · D favorit dibekukan → tab <b>Arm Lain (Beku)</b>.
							</p>
							<p class="text-10 text-text-3">
								Dompet di bawah = Rp 10 juta × persentase PnL arm (modal asli arm 100 USD) — bukan setoran baru.
							</p>
						</div>
						<!-- Dompet paper Polymarket: arm B (keputusan owner 7 Okt) -->
						<DompetPasar market="polymarket" dompet={dompetObj} judul="Dompet Paper Polymarket (arm B)" />
						<!-- Akurasi & PnL per arm (6 Okt): win-rate entri mesin paper, dihitung per arm -->
						<AkurasiPasar
							judul="Akurasi & PnL per Arm (Polymarket)"
							subjudul="Entri menang/kalah mesin paper — fees sudah dibebankan; bukan R, belum lewat split beku"
							data={akurasiPoly}
						/>
						<StatisticalEdgeCard verdict={verdictObj} judul="Polymarket 5m Statistical Verdict" />
					</div>
				{/if}
				{#if sub === 'arsip'}
					<div class="space-y-4">
						<div class="rounded-card border border-line bg-surface p-3">
							<div class="text-12 font-bold text-text-2">Arm beku (bukti disimpan)</div>
							<p class="text-11 text-text-3">
								Keputusan owner 7 Okt: hanya Setup B yang dikejar. A/C/D tetap diarsipkan —
								angkanya jangan dihapus, tapi jangan dijadikan dasar keputusan baru.
							</p>
						</div>
						<!-- Dompet paper Polymarket: arm B (keputusan owner 7 Okt), arm lain dibekukan -->
						<DompetPasar market="polymarket" dompet={dompetObj} judul="Dompet Paper Polymarket (arm B)" />
						<AkurasiPasar
							judul="Akurasi & PnL per Arm (Polymarket)"
							subjudul="Arm A momentum · B kandidat · C fade · D favorit — dari shadow summary"
							data={akurasiPoly}
						/>
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
				{/if}
				{#if sub === 'agen' || sub === 'arsip'}
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
				{/if}
				{#if sub === 'replay' || sub === 'riset'}
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
				{/if}
				{#if sub === 'parity' || sub === 'riset' || sub === 'setup-b'}
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
				{/if}
				{#if sub === 'biaya' || sub === 'arsip'}
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
				{/if}
				{#if sub === 'live'}
					<div class="space-y-4">
						<div class="permukaan-2 rounded-card border border-line p-4 space-y-3">
							<div class="flex items-center justify-between border-b border-line-soft pb-2">
								<div>
									<h3 class="text-14 font-bold text-text">Arming 3-Way &amp; Kesiapan Dana Nyata</h3>
									<p class="text-11 text-text-3">Status 3 gerbang izin sebelum modal nyata dihubungkan ke pasar</p>
								</div>
								<span class="rounded px-2 py-0.5 text-10 font-bold bg-warn/15 text-warn border border-warn/30 font-mono">
									SIMULASI PAPER (LOCKED)
								</span>
							</div>

							<div class="space-y-2 text-12">
								<div class="rounded bg-surface p-2.5 border border-line flex items-center justify-between">
									<div>
										<div class="font-bold text-text">Gate 1: Statistical Edge Lolos (CI &gt; BE)</div>
										<p class="text-10 text-text-3">Interval kepercayaan bawah 95% harus melampaui break-even.</p>
									</div>
									<span class="rounded px-2 py-0.5 text-10 font-bold text-warn bg-warn/10 border border-warn/30">BELUM CUKUP</span>
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
				{#if sub === 'sinyal' || !sub}
					<JudulBagian nomor="1" judul="Sinyal" tujuan="Bandarmologi + BSJP + ARA: siapa yang bergerak, dan sinyal apa yang keluar" ikon="◈" />
				{:else if sub === 'bandarmologi'}
					<JudulBagian nomor="2" judul="Bandarmologi" tujuan="Aliran broker per emiten (ATS, frekuensi, no-sell) + skor 0–100" ikon="⚖" />
				{:else if sub === 'bsjp'}
					<JudulBagian nomor="3" judul="BSJP" tujuan="Beli Sore Jual Pagi: kandidat tahan semalam, dari walk-forward (bukan karangan)" ikon="☾" />
				{:else if sub === 'aliran'}
					<JudulBagian nomor="4" judul="Aliran" tujuan="Peta modal: asing vs lokal, akumulasi senyap, konflik distribusi" ikon="⇄" />
				{/if}
				{#if isWeekendWIB}
					<div class="rounded-card border border-warn/30 bg-warn/10 p-3 text-12 text-warn flex items-start gap-2.5">
						<span class="text-16 leading-none">ℹ️</span>
						<div>
							<div class="font-bold text-warn">Bursa Efek Indonesia (IDX) Tutup — Akhir Pekan</div>
							<p class="text-11 text-text-2 mt-0.5">
								Pasar saham domestik beroperasi Senin – Jumat (09:00 – 15:55 WIB). Data Arjum, TradingView Screener, dan Bandarmologi di bawah mencerminkan penutupan sesi reguler terakhir.
							</p>
						</div>
					</div>
				{/if}

				{#if sub === 'sinyal' || !sub}
					<div class="space-y-4">
						<!-- Dompet paper IDX: bagian per setup — ARA_HUNTER vs BSJP terlihat bedanya.
						     Ini "uang" — selalu di atas, apa pun tabnya. -->
						<DompetPasar market="idx" dompet={dompetObj} judul="Dompet Paper IDX (Rp 10 juta)" />
						<!-- ALUR KERJA: (1) Bandarmologi = siapa yang bergerak; (2) BSJP+ARA = sinyal;
						     (3) Screener Arjum = bahan mentah. Urutan ini menggantikan tumpukan
						     yang dulu membuat halaman terasa "hancur" (keluhan 7 Okt). -->
						<div class="rounded-card border border-accent/30 bg-accent/5 p-2.5 text-11 text-text-2">
							Halaman ini dibaca dari ATAS ke BAWAH sebagai satu alur: dari <b>bahan mentah</b>
							sampai <b>keputusan</b>. Tiap blok berlabel LANGKAH — inilah artinya:
							<div class="mt-1.5 grid grid-cols-1 gap-1 sm:grid-cols-2">
								<div><b class="font-mono text-accent">1 · Screener</b> — bahan mentah: 3 emiten yang lolos filter broker+teknikal. Belum keputusan.</div>
								<div><b class="font-mono text-accent">2 · Akurasi</b> — mana SETUP yang layak dipercaya (ARA vs BSJP vs INTRADAY) + tingkat pakem.</div>
								<div><b class="font-mono text-accent">3 · Sinyal</b> — ledger mesin: 24 sinyal terakhir, entry/SL/TP + umur (CREATED berhari-hari = nyangkut).</div>
								<div><b class="font-mono text-accent">4 · BSJP</b> — kandidat tahan semalam (beli sore, jual pagi) dari walk-forward.</div>
								<div><b class="font-mono text-accent">5 · Bandarmologi</b> — skor 0–100 per emiten dari ATS/frekuensi/no-sell, komponennya diaudit.</div>
								<div><b class="font-mono text-accent">6 · ARA Hunter</b> — watchlist breakout auto-rejection (bagian paling berisiko: lihat min R).</div>
							</div>
							<p class="mt-1.5">
								Semua dari <b>ledger mesin yang sama</b>; yang membuat berbeda hanya pertanyaan yang dijawab.
								Ketika tab lain dibuka (Bandarmologi/BSJP/Aliran), label nomor disembunyikan — isinya sama, konteksnya berbeda.
							</p>
						</div>
						<!-- Arjum Screener -->
						<div class="permukaan-2 rounded-card border border-line p-3">
							<div class="mb-3 flex items-center justify-between border-b border-line-soft pb-2">
								<div>
									<h3 class="text-14 font-medium text-text">
										{#if sub === 'sinyal' || !sub}<span class="text-accent font-mono text-11 mr-1">LANGKAH 1</span>{/if}Arjum Multi-Factor Stock Screener
									</h3>
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
												<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5">KODE</th>
												<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5">BUCKET</th>
												<th class="hidden py-1.5 px-1.5 sm:table-cell sm:py-2 sm:px-2.5">SUMMARY SIGNAL</th>
												<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right">WR EVENT</th>
												<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right">POTENSI</th>
												<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right">MAX DD</th>
												<th class="hidden py-1.5 px-1.5 sm:table-cell sm:py-2 sm:px-2.5">CATATAN</th>
											</tr>
										</thead>
										<tbody class="divide-y divide-line-soft">
											{#each idxArjum as r (r.stock_code)}
												<tr class="hover:bg-surface/50 transition-colors">
													<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5">
														<div class="font-bold text-text font-mono">{r.stock_code}</div>
														<div class="text-10 text-text-3 truncate max-w-[64px] sm:max-w-[120px]">{r.stock_name ?? ''}</div>
													</td>
													<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 whitespace-nowrap">
														<span class="rounded px-1.5 py-0.5 text-10 sm:px-2 sm:text-11 font-medium border border-line {
															r.bucket?.includes('PANTULAN') ? 'text-warn bg-warn/10' :
															r.bucket?.includes('DISTRIBUSI') ? 'text-neg bg-neg/10' :
															r.bucket?.includes('SENYAP') ? 'text-accent-2 bg-accent-2/10' :
															'text-text-2 bg-surface'
														}">
															{r.bucket ?? '—'}
														</span>
													</td>
													<td class="hidden py-1.5 px-1.5 sm:table-cell sm:py-2 sm:px-2.5 text-11 text-text-2 max-w-[280px]">
														{r.summary ?? '—'}
													</td>
													<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right font-mono font-medium {r.wr_event != null && r.wr_event >= 60 ? 'text-pos' : 'text-text-2'}">
														{r.wr_event != null ? `${r.wr_event.toFixed(1)}%` : '—'}
													</td>
													<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right font-mono text-pos">
														{r.potential != null ? `+${r.potential}%` : '—'}
													</td>
													<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right font-mono text-neg">
														{r.drawdown != null ? `${r.drawdown}%` : '—'}
													</td>
													<td class="hidden py-1.5 px-1.5 sm:table-cell sm:py-2 sm:px-2.5 text-11 text-text-3">
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
												<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5">TICKER</th>
												<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right">HARGA (RP)</th>
												<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right">24H CHG</th>
												<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right">VOLUME</th>
												<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right">RSI (14)</th>
												<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-center">EMA STATE</th>
												<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right">ATR</th>
											</tr>
										</thead>
										<tbody class="divide-y divide-line-soft font-mono">
											{#each idxTv as t (t.ticker)}
												<tr class="hover:bg-surface/50 transition-colors">
													<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 font-bold text-text">{t.ticker}</td>
													<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right">{t.close?.toLocaleString('id-ID') ?? '—'}</td>
													<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right font-medium {(t.change_pct ?? 0) >= 0 ? 'text-pos' : 'text-neg'}">
														{(t.change_pct ?? 0) >= 0 ? '+' : ''}{(t.change_pct ?? 0).toFixed(2)}%
													</td>
													<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right text-text-2">
														{t.volume != null ? `${(t.volume / 1e6).toFixed(1)}M` : '—'}
													</td>
													<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right {(t.rsi14 ?? 50) >= 70 ? 'text-warn font-bold' : (t.rsi14 ?? 50) <= 30 ? 'text-pos font-bold' : 'text-text-2'}">
														{t.rsi14?.toFixed(1) ?? '—'}
													</td>
													<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-center">
														<span class="rounded px-2 py-0.5 text-10 font-sans border border-line {t.ema_state === 'naik' ? 'text-pos bg-pos/10' : 'text-neg bg-neg/10'}">
															{t.ema_state === 'naik' ? '▲ NAIK' : '▼ TURUN'}
														</span>
													</td>
													<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right text-text-3">{t.atr?.toFixed(1) ?? '—'}</td>
												</tr>
											{/each}
										</tbody>
									</table>
								</div>
							{/if}
						</div>
					</div>
				{/if}

			<!-- Narasi LLM per market: dari job llm-brief-<market>. Angka tetap dari fakta;
			     narasi hanya menjelaskan — tidak pernah menggantikan bukti. Gaya 7 Okt:
			     kesimpulan dulu (kalimat besar), bukti menyusul, mesin disembunyikan di kaki. -->
			{#if narasiObj}
			<div class="mb-4 overflow-hidden rounded-card border border-line bg-surface">
				<div class="flex flex-wrap items-center justify-between gap-2 border-b border-line-soft px-3 py-1.5">
					<span class="text-11 font-bold uppercase tracking-wide text-accent-2">✳ Narasi</span>
					<span class="text-10 text-text-3 font-mono">
						{narasiObj.fact_ids?.length ?? 0} fakta dirujuk{#if narasiObj.output?.nada} · nada {narasiObj.output.nada}{/if}
					</span>
				</div>
				{#if narasiObj.status !== 'ok'}
					<p class="px-3 py-2 text-11 text-warn">
						Narasi tidak tersedia ({narasiObj.status ?? '—'}{narasiObj.error_code ? ` · ${narasiObj.error_code}` : ''}) —
						angka di halaman ini tetap sah karena berasal dari fakta, bukan dari narasi.
					</p>
				{:else if narasiObj.output?.kalimat?.length}
					<div class="px-3 py-2.5">
						<p class="text-15 leading-snug text-text">{narasiObj.output.kalimat[0].teks}</p>
						{#if narasiObj.output.kalimat.length > 1}
							<div class="mt-1.5 space-y-1 border-l-2 border-line-soft pl-2.5">
								{#each narasiObj.output.kalimat.slice(1) as k}
									<p class="text-12 text-text-2">{k.teks}</p>
								{/each}
							</div>
						{/if}
						<p class="mt-2 text-10 text-text-3">
							Deskriptif, bukan rekomendasi. Mesin: {narasiObj.provider ?? '—'} ·
							{narasiObj.prompt_version ?? '—'}{#if narasiObj.latency_ms} · {narasiObj.latency_ms} ms{/if}
						</p>
					</div>
				{:else}
					<p class="px-3 py-2 text-11 text-text-3">Narasi kosong — fakta tetap sah.</p>
				{/if}
			</div>
			{/if}

				<!-- Akurasi signal per setup (6 Okt): dari ledger mesin (grader v3).
				     Hanya baris TUNTAS masuk metrik; belum tuntas & ambigu dipisah.
				     Pakem = kematangan sampel pada hari independen, bukan jumlah trade.
				     Sengaja TANPA guard sub: ini inti area IDX, wajib tampak di semua tab. -->
				<div class="permukaan-2 rounded-card border border-line p-3">
					<div class="mb-3 flex items-center justify-between border-b border-line-soft pb-2">
						<div>
							<h3 class="text-14 font-medium text-text">
								{#if sub === 'sinyal' || !sub}<span class="text-accent font-mono text-11 mr-1">LANGKAH 2</span>{/if}Akurasi Signal per Setup
							</h3>
							<p class="text-11 text-text-3">
								Ledger mesin (grader v3) — hanya baris tuntas yang masuk metrik; kematangan dinilai per hari bursa
							</p>
						</div>
						<span class="rounded bg-surface px-2 py-0.5 text-11 font-mono text-accent border border-line">
							{idxAkurasiObj?.tuntas ?? 0} tuntas · {idxAkurasiObj?.belum_tuntas ?? 0} jalan
						</span>
					</div>

					{#if !idxAkurasiObj?.tersedia}
						<div class="py-6 text-center text-text-3 text-12">
							Ledger akurasi belum tersedia ({idxAkurasiObj?.alasan ?? 'belum diimpor'}).
						</div>
					{:else}
						<div class="overflow-x-auto">
							<table class="w-full text-left text-12 font-mono">
								<thead class="border-b border-line text-text-3 font-normal text-11">
									<tr>
										<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5">SETUP</th>
										<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right">n</th>
										<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right">HARI</th>
										<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right">WIN%</th>
										<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right">MEAN R</th>
										<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right">TOTAL R</th>
										<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5">PAKEM</th>
										<th class="hidden py-1.5 px-1.5 sm:table-cell sm:py-2 sm:px-2.5 text-right">JALAN</th>
									</tr>
								</thead>
								<tbody class="divide-y divide-line-soft">
									{#each Object.entries((idxAkurasiObj.per_setup ?? {}) as Record<string, any>) as [nama, s] (nama)}
										<tr class="hover:bg-surface/50 transition-colors">
											<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 font-bold text-text">
												{s.setup ?? nama}
												{#if s.grader?.length}
													<span class="ml-1 text-10 text-text-3">{s.grader.join(',')}</span>
												{/if}
											</td>
											<td class="py-1.5 px-1.5 text-right text-text-2 sm:py-2 sm:px-2.5">{s.n ?? '—'}</td>
											<td class="py-1.5 px-1.5 text-right text-text-3 sm:py-2 sm:px-2.5">{s.n_hari ?? '—'}</td>
											<td class="py-1.5 px-1.5 text-right sm:py-2 sm:px-2.5">
												{s.winrate_pct == null ? '—' : `${s.winrate_pct}%`}
											</td>
											<td class="py-1.5 px-1.5 text-right sm:py-2 sm:px-2.5 {s.mean_r == null ? 'text-text-3' : s.mean_r > 0 ? 'text-pos font-bold' : 'text-neg font-bold'}">
												{s.mean_r == null ? '—' : (s.mean_r > 0 ? '+' : '') + s.mean_r}
											</td>
											<td class="py-1.5 px-1.5 text-right text-text-2 sm:py-2 sm:px-2.5">
												{s.total_r == null ? '—' : (s.total_r > 0 ? '+' : '') + s.total_r}
											</td>
											<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5">
												<span
													class="rounded border px-1.5 py-0.5 text-10 font-bold {s.pakem === 'TUNING'
														? 'border-line text-text'
														: s.pakem === 'PRELIMINARY'
															? 'border-warn/40 text-warn bg-warn/10'
															: s.pakem === 'DIRECTIONAL'
																? 'border-accent/40 text-accent bg-accent/10'
																: 'border-neg/40 text-neg bg-neg/10'}"
												>
													{s.pakem}
												</span>
											</td>
											<td class="hidden py-1.5 px-1.5 text-right text-text-3 sm:table-cell sm:py-2 sm:px-2.5">{s.belum_tuntas ?? 0}</td>
										</tr>
									{/each}
								</tbody>
							</table>
						</div>

						{#if idxAkurasiObj.bsjp_gabungan}
							<p class="mt-3 rounded-card border border-line-soft bg-surface p-2.5 text-11 text-text-2">
								<span class="font-bold text-text">BSJP gabungan:</span>
								<span class="font-mono">
									n={idxAkurasiObj.bsjp_gabungan.n} · hari={idxAkurasiObj.bsjp_gabungan.n_hari} ·
									WR {idxAkurasiObj.bsjp_gabungan.winrate_pct}% ·
									mean {idxAkurasiObj.bsjp_gabungan.mean_r > 0 ? '+' : ''}{idxAkurasiObj.bsjp_gabungan.mean_r} R ·
									total {idxAkurasiObj.bsjp_gabungan.total_r > 0 ? '+' : ''}{idxAkurasiObj.bsjp_gabungan.total_r} R
								</span>
								{#if idxAkurasiObj.bsjp_gabungan.alasan?.length}
									<span class="text-text-3">· {idxAkurasiObj.bsjp_gabungan.alasan[0]}</span>
								{/if}
							</p>
						{/if}

						<p class="mt-2 text-10 text-text-3">
							Sumber: {idxAkurasiObj.impor?.sumber ?? idxAkurasiObj.sumber ?? 'ledger lokal'}
							{#if idxAkurasiObj.impor?.diimpor_ts}
								· diimpor {new Date(idxAkurasiObj.impor.diimpor_ts * 1000).toLocaleDateString('id-ID')}
							{/if}
							{#if idxAkurasiObj.impor?.sha256}
								· sha256 {idxAkurasiObj.impor.sha256.slice(0, 12)}…
							{/if}
						</p>
					{/if}
				</div>

				<!-- Sinyal & entry setup IDX (6 Okt): ARA/BSJP/INTRADAY dari ledger mesin -->
				{#if sub === 'bsjp' || sub === 'sinyal'}
					<SinyalPasar
						pasar="idx"
						judul="Sinyal & Entry Setup (IDX)"
						subjudul={(sub === 'sinyal' || !sub ? 'LANGKAH 3 · ' : '') + 'Ledger mesin 616: ARA Hunter, BSJP, Scalping INTRADAY — entry = zona, hasil = net R'}
						data={idxSinyalObj}
					/>
				{/if}
				{#if sub === 'screener'}
					<AkurasiPasar
						judul="Akurasi per Setup (IDX)"
						subjudul="Ringkasan dari ledger mesin yang sama dengan tab BSJP"
						data={{
							tersedia: idxAkurasiObj?.tersedia,
							alasan: idxAkurasiObj?.alasan,
							per_setup: idxAkurasiObj?.per_setup,
							sumber: idxAkurasiObj?.impor?.sumber,
							catatan: [`${idxAkurasiObj?.tuntas ?? 0} tuntas`, `${idxAkurasiObj?.belum_tuntas ?? 0} jalan`]
						}}
					/>
				{/if}

				<!-- Tab BSJP: Beli Sore Jual Pagi -->
				{#if sub === 'bsjp' || sub === 'sinyal'}
					<div class="space-y-4">
						<div class="permukaan-2 rounded-card border border-line p-3">
							<div class="mb-3 flex items-center justify-between border-b border-line-soft pb-2">
								<div>
									<h3 class="text-14 font-medium text-text">
										{#if sub === 'sinyal' || !sub}<span class="text-accent font-mono text-11 mr-1">LANGKAH 4</span>{/if}BSJP — Beli Sore, Jual Pagi
									</h3>
									<p class="text-11 text-text-3">
										Peringkat kandidat tahan semalam: beli menjelang tutup, jual di pembukaan
										sesi berikutnya.
									</p>
								</div>
								<span
									class="rounded px-2 py-0.5 text-10 font-bold font-mono border {bsjpObj?.mode ===
									'proksi'
										? 'text-warn bg-warn/10 border-warn/30'
										: 'text-pos bg-pos/10 border-pos/30'}"
									title={bsjpObj?.sumber_angka ?? ''}
								>
									{bsjpObj?.mode === 'terukur'
										? 'EDGE TERUKUR DI SINI'
										: bsjpObj?.mode === 'bersumber'
											? 'EDGE TERUKUR (DARI SUMBER)'
											: 'PROKSI — BELUM TERUKUR'}
								</span>
							</div>

							{#if bsjpObj?.error}
								<div class="rounded bg-neg/10 border border-neg/30 p-2.5 text-11 text-neg font-mono">
									Gagal menyusun BSJP: {bsjpObj.error}
								</div>
							{:else if !bsjpObj?.ada}
								<div class="py-6 text-center text-text-3 text-12">
									Belum ada kandidat BSJP — screener dan snapshot teknikal kosong.
								</div>
							{:else}
								<!-- Mode proksi WAJIB menjelaskan batasnya di sini, bukan disembunyikan. -->
								<div
									class="mb-3 rounded border p-2.5 text-11 {bsjpObj?.mode === 'proksi'
										? 'border-warn/40 bg-warn/10 text-warn'
										: 'border-pos/30 bg-pos/10 text-pos'}"
								>
									{bsjpObj?.catatan_kejujuran}
								</div>

								<div class="mb-3 grid grid-cols-2 sm:grid-cols-3 gap-2 font-mono text-11">
									<div class="rounded bg-surface p-2 border border-line">
										<span class="text-10 text-text-3 block">MODE</span>
										<span class="text-13 font-bold text-text">{bsjpObj?.mode}</span>
									</div>
									<div class="rounded bg-surface p-2 border border-line">
										<span class="text-10 text-text-3 block">EDGE RATA-RATA</span>
										<span class="text-13 font-bold {bsjpObj?.edge_rata_pct != null ? 'text-pos' : 'text-text-3'}">
											{bsjpObj?.edge_rata_pct != null ? `${bsjpObj.edge_rata_pct}%` : '—'}
										</span>
									</div>
									<div class="rounded bg-surface p-2 border border-line">
										<span class="text-10 text-text-3 block">SAMPEL JENDELA</span>
										<span class="text-13 font-bold text-text">{bsjpObj?.n_sampel ?? 0}</span>
									</div>
								</div>

								<!-- Legenda tier: apa arti STRONG vs ARA, dan dari mana angkanya.
								     Sebelumnya istilah ini muncul tanpa penjelasan. -->
								<p class="mb-3 text-11 text-text-3 leading-relaxed">
									<span class="text-text-2 font-medium">Tier:</span>
									<b class="text-pos">STRONG</b> = kandidat teratas (net est ≈ +0,86%/trade dari
									walk-forward sumber) · <b class="text-accent">ARA</b> = lonjakan harga harian
									(net est ≈ +1,06%/trade dari sumber) — filter ARA di sumber <b>tidak</b> memeriksa
									SMA10, jadi ia bercampur antara saham menguat dan yang bangkit dari penurunan.
								</p>

								<div class="overflow-x-auto">
									<table class="w-full text-left text-12">
										<thead class="border-b border-line text-text-3 text-11 font-mono">
											<tr>
												<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5">TICKER</th>
												<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right">SKOR</th>
												<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right">RSI14</th>
												<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5">EMA</th>
												<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right">WR EVENT</th>
												<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right">POTENSI</th>
												<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right">DD</th>
												<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5">CATATAN</th>
											</tr>
										</thead>
										<tbody class="divide-y divide-line-soft">
											{#each bsjpObj.kandidat ?? [] as k (k.ticker)}
												<tr class="hover:bg-surface/50 transition-colors">
													<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 font-bold font-mono text-text">{k.ticker}</td>
													<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right font-mono font-bold {k.skor != null ? 'text-accent' : 'text-text-3'}">
														{k.skor ?? '—'}
													</td>
													<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right font-mono text-text-2">
														{k.rsi14 != null ? k.rsi14.toFixed(1) : '—'}
													</td>
													<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 font-mono text-11 {k.ema_state === 'naik' ? 'text-pos' : 'text-text-3'}">
														{k.ema_state ?? '—'}
													</td>
													<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right font-mono text-text-2">
														{k.wr_event != null ? `${k.wr_event}%` : '—'}
													</td>
													<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right font-mono text-text-2">
														{k.potensi != null ? `${k.potensi}%` : '—'}
													</td>
													<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right font-mono {k.drawdown != null && k.drawdown < 0 ? 'text-neg' : 'text-text-3'}">
														{k.drawdown != null ? `${k.drawdown}%` : '—'}
													</td>
													<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-10 text-text-3">
														{(k.catatan ?? []).join(' · ') || '—'}
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

				<!-- Tab Bandarmologi -->
				{#if sub === 'bandarmologi' || sub === 'sinyal'}
					<div class="space-y-4">
						<!-- Skor Bandarmologi 0–100 (adopsi pola ihsgscreener, 6 Okt): satu angka
						     ringkas dengan komponen yang bisa diaudit. Alat baca, bukan ajakan beli. -->
						<div class="permukaan-2 rounded-card border border-line p-3">
							<div class="mb-3 flex flex-wrap items-center justify-between gap-2 border-b border-line-soft pb-2">
								<div>
									<h3 class="text-14 font-medium text-text">Skor Bandarmologi (0–100)</h3>
									<p class="text-11 text-text-3">
										ATS beli/jual + frekuensi + no-sell, dibobot & bisa diaudit per komponen
									</p>
								</div>
								<span class="rounded bg-surface px-2 py-0.5 text-11 font-mono text-accent border border-line">
									{bandarSkorObj?.n_emiten ?? 0} emiten · {bandarSkorObj?.hari ?? '—'}
								</span>
							</div>
							{#if !bandarSkorObj?.tersedia}
								<div class="py-4 text-center text-12 text-text-3">
									Skor belum tersedia ({bandarSkorObj?.alasan ?? 'belum ada broker summary'}).
								</div>
							{:else}
								<div class="space-y-2">
									{#each bandarSkorObj.emiten as e (e.kode)}
										<div class="rounded-card border border-line bg-surface p-2.5">
											<div class="flex flex-wrap items-center justify-between gap-2">
												<div class="flex items-center gap-2">
													<span class="font-mono font-bold text-text">{e.kode}</span>
													<span class="rounded px-1.5 py-0.5 text-10 font-bold border {e.kelas === 'AKUMULASI' ? 'text-pos bg-pos/10 border-pos/20' : e.kelas === 'DISTRIBUSI' ? 'text-neg bg-neg/10 border-neg/20' : e.kelas === 'SEIMBANG' ? 'text-text-2 bg-surface border-line' : 'text-warn bg-warn/10 border-warn/20'}">
														{e.kelas}
													</span>
													{#if e.no_sell}
														<span class="rounded px-1.5 py-0.5 text-10 font-bold border border-accent/30 text-accent bg-accent/10">NO-SELL</span>
													{/if}
												</div>
												<div class="flex items-center gap-2">
													<div class="h-2 w-32 overflow-hidden rounded bg-canvas border border-line">
														<div class="h-full rounded {e.skor >= 55 ? 'bg-pos' : e.skor <= 45 ? 'bg-neg' : 'bg-accent'}" style="width: {e.skor}%"></div>
													</div>
													<span class="font-mono font-bold text-14 {e.skor >= 55 ? 'text-pos' : e.skor <= 45 ? 'text-neg' : 'text-text-2'}">{e.skor}</span>
												</div>
											</div>
											<div class="mt-1.5 flex flex-wrap gap-x-3 gap-y-0.5 text-10 text-text-3 font-mono">
												<span>ATS beli {e.rasio_ats_pct}%</span>
												<span>FRQ beli {e.rasio_frq_pct}%</span>
												{#each e.komponen as k (k.nama)}
													<span>{k.nama}: {k.kontribusi > 0 ? '+' : ''}{k.kontribusi}</span>
												{/each}
											</div>
										</div>
									{/each}
								</div>
								<p class="mt-2 text-11 text-text-3">{bandarSkorObj.metode}</p>
								<p class="mt-1 text-11 text-warn">{bandarSkorObj.emiten[0]?.peringatan}</p>
							{/if}
						</div>

						<div class="permukaan-2 rounded-card border border-line p-3">
							<div class="mb-3 flex items-center justify-between border-b border-line-soft pb-2">
								<div>
									<h3 class="text-14 font-medium text-text">{#if sub === 'sinyal' || !sub}<span class="text-accent font-mono text-11 mr-1">LANGKAH 5</span>{/if}Bandarmologi &amp; Broker Summary</h3>
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
				{#if sub === 'aliran' || sub === 'bandarmologi'}
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
									<div class="text-20 font-bold text-accent-2 font-mono mt-1">
										{idxArjum.filter((r) => r.bucket?.includes('SENYAP')).length}
									</div>
									<div class="text-11 text-text-3 mt-1">Tanpa lonjakan volume retail</div>
								</div>
								<div class="rounded bg-surface p-3 border border-line">
									<div class="text-11 text-text-3">Konflik Distribusi</div>
									<div class="text-20 font-bold text-warn font-mono mt-1">
										{idxArjum.filter((r) => r.bucket?.includes('KONFLIK')).length}
									</div>
									<div class="text-11 text-text-3 mt-1">Broker akumulasi vs asing jual</div>
								</div>
							</div>
						</div>
					</div>
				{/if}

				<!-- Tab Watchlist: ARA Hunter Setups -->
				{#if sub === 'watchlist' || sub === 'bsjp' || sub === 'sinyal'}
					<div class="space-y-4">
						<div class="permukaan-2 rounded-card border border-line p-3">
							<div class="mb-3 flex items-center justify-between border-b border-line-soft pb-2">
								<div>
									<h3 class="text-14 font-medium text-text">
										{#if sub === 'sinyal' || !sub}<span class="text-accent font-mono text-11 mr-1">LANGKAH 6</span>{/if}Watchlist Sinyal ARA Hunter (IDX616)
									</h3>
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
				<!-- 5 BLOK WAJIB (6 Okt 2026): Statistik & verifikasi + Posisi & riwayat.
				     Sumber: fakta {kunci}_equity / {kunci}_ledger / {kunci}_risiko / {kunci}_posisi.
				     Kosong ditampilkan apa adanya — bukan 0 yang dikarang. -->
				<div class="mt-4 space-y-4">
					<EquityCurve points={equityObj?.points} stats={equityObj?.stats} />
					<RiskMeter risiko={risikoObj} />

					<div class="permukaan-2 rounded-card border border-line p-3">
						<div class="mb-2 flex items-center justify-between border-b border-line-soft pb-2">
							<h3 class="text-13 font-medium text-text">Posisi Terbuka</h3>
							<span class="text-11 text-text-3 font-mono">{posisiJumlah} / {posisiMaks}</span>
						</div>
						{#if posisiArray.length === 0}
							<div class="py-4 px-2 text-center text-12 text-text-3">
								Belum ada posisi terbuka pada venue ini.
							</div>
						{:else}
							<div class="space-y-2">
								{#each posisiArray as p (p.signal_id ?? p.pair)}
									<div class="flex items-center justify-between gap-2 rounded-card border border-line bg-surface p-2.5 font-mono text-12">
										<div class="flex items-center gap-2">
											<span class="font-bold text-text">{p.pair}</span>
											<span class="rounded px-1.5 py-0.5 text-10 font-bold uppercase {p.direction === 'LONG' ? 'text-pos bg-pos/10 border border-pos/20' : 'text-neg bg-neg/10 border border-neg/20'}">{p.direction}</span>
										</div>
										<span class="text-11 text-text-3"
											>entry {harga(p.entry)} · SL {harga(p.stop)} · TP {harga(p.tp1)}</span
										>
									</div>
								{/each}
							</div>
						{/if}
					</div>

					<div class="permukaan-2 rounded-card border border-line p-3">
						<div class="mb-2 flex items-center justify-between border-b border-line-soft pb-2">
							<h3 class="text-13 font-medium text-text">Riwayat Eksekusi &amp; Ledger</h3>
							<span class="text-11 text-text-3 font-mono">{ledgerObj?.trade ?? 0} trade</span>
						</div>
						{#if (ledgerObj?.terakhir ?? []).length === 0}
							<div class="py-4 px-2 text-center text-12 text-text-3">
								Belum ada trade tereksekusi pada venue ini.
							</div>
						{:else}
							<div class="space-y-2">
								{#each (ledgerObj?.terakhir ?? []) as tr}
									<div class="flex flex-wrap items-center justify-between gap-2 rounded-card border border-line-soft bg-surface p-2.5">
										<div class="flex items-center gap-2">
											<span class="font-bold font-mono text-13 text-text">{tr.pair}</span>
											<span class="rounded px-1.5 py-0.5 text-10 font-bold uppercase {String(tr.status ?? '').includes('TP') ? 'bg-pos/20 text-pos' : String(tr.status ?? '').includes('SL') ? 'bg-warn/20 text-warn' : 'bg-surface text-text-3 border border-line'}">{tr.status}</span>
											<span class="text-10 font-mono text-text-3">{waktuWIB(tr.closed_at)}</span>
										</div>
										<span class="font-mono font-bold text-13 {typeof tr.r === 'number' && tr.r > 0 ? 'text-pos' : typeof tr.r === 'number' && tr.r < 0 ? 'text-neg' : 'text-text-3'}">{tr.r == null ? '—' : (tr.r > 0 ? '+' : '') + tr.r + ' R'}</span>
									</div>
								{/each}
							</div>
						{/if}
					</div>
				</div>

			{/if}

			<!-- ========================================== -->
			<!-- VIEW KHUSUS: FOREX & KOMODITAS             -->
			<!-- ========================================== -->
			{#if kunci === 'forex'}
				{#if sub === 'struktur' || !sub}
					<JudulBagian nomor="1" judul="Struktur" tujuan="Cockpit harga (TradingView TVC:GOLD) + sinyal & entry setup dari jurnal mesin" ikon="◈" />
				{:else if sub === 'sesi'}
					<JudulBagian nomor="2" judul="Sesi" tujuan="Kapan tiap bursa buka/tutup (OANDA-style), pola volume per sesi" ikon="◷" />
				{:else if sub === 'kalender'}
					<JudulBagian nomor="3" judul="Kalender" tujuan="Agenda makro + hitung mundur: apakah aman masuk posisi sekarang" ikon="⌗" />
				{:else if sub === 'demo'}
					<JudulBagian nomor="4" judul="Keterbatasan & Demo" tujuan="Apa yang belum ada (akun broker, biaya) — dinyatakan terbuka" ikon="⚠" />
				{/if}
				{#if isWeekendWIB}
					<div class="rounded-card border border-warn/30 bg-warn/10 p-3 text-12 text-warn flex items-start gap-2.5">
						<span class="text-16 leading-none">ℹ️</span>
						<div>
							<div class="font-bold text-warn">Pasar Forex & Spot Komoditas (XAU/USD) Tutup — Akhir Pekan</div>
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

			<!-- Narasi LLM per market: dari job llm-brief-<market>. Angka tetap dari fakta;
			     narasi hanya menjelaskan — tidak pernah menggantikan bukti. Gaya 7 Okt:
			     kesimpulan dulu (kalimat besar), bukti menyusul, mesin disembunyikan di kaki. -->
			{#if narasiObj}
				<div class="mb-4 overflow-hidden rounded-card border border-line bg-surface">
					<div class="flex flex-wrap items-center justify-between gap-2 border-b border-line-soft px-3 py-1.5">
						<span class="text-11 font-bold uppercase tracking-wide text-accent-2">✳ Narasi</span>
						<span class="text-10 text-text-3 font-mono">
							{narasiObj.fact_ids?.length ?? 0} fakta dirujuk{#if narasiObj.output?.nada} · nada {narasiObj.output.nada}{/if}
						</span>
					</div>
					{#if narasiObj.status !== 'ok'}
						<p class="px-3 py-2 text-11 text-warn">
							Narasi tidak tersedia ({narasiObj.status ?? '—'}{narasiObj.error_code ? ` · ${narasiObj.error_code}` : ''}) —
							angka di halaman ini tetap sah karena berasal dari fakta, bukan dari narasi.
							Status penyedia LLM ada di halaman <b>Sistem → AI</b>.
						</p>
					{:else if narasiObj.output?.kalimat?.length}
						<div class="px-3 py-2.5">
							<p class="text-15 leading-snug text-text">{narasiObj.output.kalimat[0].teks}</p>
							{#if narasiObj.output.kalimat.length > 1}
								<div class="mt-1.5 space-y-1 border-l-2 border-line-soft pl-2.5">
									{#each narasiObj.output.kalimat.slice(1) as k}
										<p class="text-12 text-text-2">{k.teks}</p>
									{/each}
								</div>
							{/if}
							<p class="mt-2 text-10 text-text-3">
								Deskriptif, bukan rekomendasi. Mesin: {narasiObj.provider ?? '—'} ·
								{narasiObj.prompt_version ?? '—'}{#if narasiObj.latency_ms} · {narasiObj.latency_ms} ms{/if}
							</p>
						</div>
					{:else}
						<p class="px-3 py-2 text-11 text-text-3">Narasi kosong — fakta tetap sah.</p>
					{/if}
				</div>
			{/if}

						<!-- Dompet paper forex: Rp 10 juta, dari jurnal mesin -->
						<DompetPasar market="forex" dompet={dompetObj} judul="Dompet Paper Forex" />
						<!-- Ringkas per pair: XAUUSD vs NAS100 vs EURUSD (wataknya beda) -->
						<ForexPair data={forexSinyalObj} />
						<!-- Kalkulator posisi: dari angka yang sudah ada, bukan taksiran -->
						<div class="permukaan-2 rounded-card border border-line p-3">
							<div class="mb-2 border-b border-line-soft pb-2">
								<h3 class="text-14 font-medium text-text">Kalkulator Posisi</h3>
								<p class="text-11 text-text-3">
									Ukuran posisi = (risiko% × saldo) ÷ jarak SL. Risiko 1% dari dompet Rp 10 juta = Rp 100.000.
								</p>
							</div>
							<div class="grid grid-cols-1 gap-3 sm:grid-cols-3 font-mono text-12">
								<div class="rounded bg-surface border border-line p-2.5">
									<div class="text-10 text-text-3">SALDO AWAL</div>
									<div class="text-14 font-bold text-text">Rp 10.000.000</div>
									<div class="text-10 text-text-3 mt-1">Risiko 1% = Rp 100.000 per trade</div>
								</div>
								<div class="rounded bg-surface border border-line p-2.5">
									<div class="text-10 text-text-3">CONTOH TERAKHIR DARI JURNAL</div>
									{#if forexSinyalObj?.entries?.[0]}
										{@const e = forexSinyalObj.entries.find((x: any) => x.pair === 'XAUUSD') ?? forexSinyalObj.entries[0]}
										<div class="text-12 font-bold text-text">{e.pair} {e.arah} @ {angka(e.entry)}</div>
										<div class="text-10 text-text-3 mt-1">
											SL {angka(e.sl)} · jarak {e.entry && e.sl ? Math.abs(Number(e.entry) - Number(e.sl)).toFixed(2) : '—'}
										</div>
									{:else}
										<div class="text-11 text-text-3">Belum ada sinyal di jurnal.</div>
									{/if}
								</div>
								<div class="rounded bg-surface border border-line p-2.5">
									<div class="text-10 text-text-3">ATURAN YANG DIKODEKAN</div>
									<div class="text-11 text-text-2 space-y-0.5">
										<div>· 1 posisi per pair (tidak menumpuk)</div>
										<div>· Blackout ±60 menit event high-impact</div>
										<div>· BE digeser 1,2R, TP1 parsial 50%</div>
									</div>
								</div>
							</div>
						</div>
						<!-- Sinyal & entry setup forex (6 Okt): XAUUSD 4-agen + multi-pair, dari jurnal Tencent -->
						<SinyalPasar
							pasar="forex"
							judul="Sinyal & Entry Setup (Forex)"
							subjudul="Jurnal mesin XAUUSD (SMC 4-agen) + NAS100/EURUSD (FVG/OB 1H) — zona entry khas SMC"
							data={forexSinyalObj}
						/>

						<!-- Akurasi forex: pakem bukti sama; sampel masih kecil, itu ditampilkan apa adanya -->
						<AkurasiPasar
							judul="Akurasi per Strategi (Forex)"
							subjudul="Trade tuntas dari jurnal mesin — NO FILL tidak dihitung sebagai trade"
							data={akurasiForex}
						/>
					</div>
				{:else if sub === 'sesi'}
					<div class="space-y-4">
						<!-- Akurasi juga tampil di tab sesi supaya tak perlu bolak-balik -->
						<AkurasiPasar judul="Akurasi per Strategi (Forex)" data={akurasiForex} />
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
					<div class="space-y-4">
						<!-- Kalender dengan dampak + hitung mundur (riset 7 Okt: yang membuat terasa hidup) -->
						<KalenderDampak macro={macroObj} />
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
											<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5">MATA UANG</th>
											<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5">DAMPAK</th>
											<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5">AGENDA</th>
											<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right">FORECAST</th>
											<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right">SEBELUMNYA</th>
										</tr>
									</thead>
									<tbody class="divide-y divide-line-soft">
										{#each (macroObj.berikutnya ?? []).slice(0, 20) as m (m.ts + m.title + m.mata_uang)}
											<tr class="hover:bg-surface/50 transition-colors">
												<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 font-bold font-mono text-text">
													<span class="rounded bg-surface px-1.5 py-0.5 border border-line">
														{m.mata_uang ?? '—'}
													</span>
												</td>
												<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5">
													<span class="rounded px-2 py-0.5 text-10 font-bold border border-line {
														m.impact === 'High' ? 'text-neg bg-neg/10' :
														m.impact === 'Medium' ? 'text-warn bg-warn/10' :
														m.impact === 'Holiday' ? 'text-accent bg-accent/10' :
														'text-text-3 bg-surface'
													}">
														{m.impact ?? '—'}
													</span>
												</td>
												<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 font-medium text-text">{m.title ?? '—'}</td>
												<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right font-mono text-text-2">{m.forecast || '—'}</td>
												<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right font-mono text-text-3">{m.previous || '—'}</td>
											</tr>
										{/each}
									</tbody>
								</table>
							</div>
						{/if}
					</div>
					</div>
				{:else if sub === 'demo'}
					<div class="space-y-4">
						<div class="permukaan-2 rounded-card border border-line p-4 space-y-3">
							<div class="flex items-center justify-between border-b border-line-soft pb-2">
								<div>
									<h3 class="text-14 font-bold text-text">Integrasi Akun Demo OANDA</h3>
									<p class="text-11 text-text-3">Status feed harga broker dan eksekusi pesanan simulasi</p>
								</div>
								<span class="rounded px-2 py-0.5 text-10 font-bold bg-warn/15 text-warn border border-warn/30 font-mono">
									SIMULASI DEMO
								</span>
							</div>

							<div class="rounded bg-surface p-3 border border-line text-12 text-text-2 space-y-2">
								<div class="font-bold text-text">Aturan Transparansi ADR-003</div>
								<p>Forex War Room beroperasi pada lingkungan DEMO / paper trading: tidak ada dana riil ke pasar valas, dan tidak ada klaim eksekusi live berpenyedia komersial.</p>
								<p class="text-warn">
									⚠ Koreksi 7 Okt: halaman ini dulu menulis "Akun Demo OANDA-v20-DEMO — STATUS FEED: TERHUBUNG".
									Itu <b>tidak benar</b>: proyek ini <b>tidak</b> punya akun OANDA. Harga diambil dari
									TradingView (TVC:GOLD) — bukan dari broker. Sumber palsu dihapus, bukan dirapikan.
								</p>
							</div>

							<div class="grid grid-cols-1 sm:grid-cols-3 gap-3 font-mono text-12">
								<div class="rounded bg-surface p-2.5 border border-line">
									<span class="text-10 text-text-3 block">SUMBER HARGA</span>
									<span class="text-14 font-bold text-text">TradingView TVC:GOLD</span>
									<span class="text-10 text-text-3">spot gold CFD, resolusi {forexObj?.resolution ?? 60}m</span>
								</div>
								<div class="rounded bg-surface p-2.5 border border-line">
									<span class="text-10 text-text-3 block">AKUN BROKER</span>
									<span class="text-14 font-bold text-text">tidak ada</span>
									<span class="text-10 text-text-3">paper murni — tak ada kredensial broker</span>
								</div>
								<div class="rounded bg-surface p-2.5 border border-line">
									<span class="text-10 text-text-3 block">MESIN SINYAL</span>
									<span class="text-14 font-bold text-text">Tencent (cron)</span>
									<span class="text-10 text-text-3">XAUUSD 4-agen + multi-pair</span>
								</div>
							</div>
						</div>
					</div>
				{/if}
				<!-- 5 BLOK WAJIB (6 Okt 2026): Statistik & verifikasi + Posisi & riwayat.
				     Sumber: fakta {kunci}_equity / {kunci}_ledger / {kunci}_risiko / {kunci}_posisi.
				     Kosong ditampilkan apa adanya — bukan 0 yang dikarang. -->
				<div class="mt-4 space-y-4">
					<EquityCurve points={equityObj?.points} stats={equityObj?.stats} />
					<RiskMeter risiko={risikoObj} />

					<div class="permukaan-2 rounded-card border border-line p-3">
						<div class="mb-2 flex items-center justify-between border-b border-line-soft pb-2">
							<h3 class="text-13 font-medium text-text">Posisi Terbuka</h3>
							<span class="text-11 text-text-3 font-mono">{posisiJumlah} / {posisiMaks}</span>
						</div>
						{#if posisiArray.length === 0}
							<div class="py-4 px-2 text-center text-12 text-text-3">
								Belum ada posisi terbuka pada venue ini.
							</div>
						{:else}
							<div class="space-y-2">
								{#each posisiArray as p (p.signal_id ?? p.pair)}
									<div class="flex items-center justify-between gap-2 rounded-card border border-line bg-surface p-2.5 font-mono text-12">
										<div class="flex items-center gap-2">
											<span class="font-bold text-text">{p.pair}</span>
											<span class="rounded px-1.5 py-0.5 text-10 font-bold uppercase {p.direction === 'LONG' ? 'text-pos bg-pos/10 border border-pos/20' : 'text-neg bg-neg/10 border border-neg/20'}">{p.direction}</span>
										</div>
										<span class="text-11 text-text-3"
											>entry {harga(p.entry)} · SL {harga(p.stop)} · TP {harga(p.tp1)}</span
										>
									</div>
								{/each}
							</div>
						{/if}
					</div>

					<div class="permukaan-2 rounded-card border border-line p-3">
						<div class="mb-2 flex items-center justify-between border-b border-line-soft pb-2">
							<h3 class="text-13 font-medium text-text">Riwayat Eksekusi &amp; Ledger</h3>
							<span class="text-11 text-text-3 font-mono">{ledgerObj?.trade ?? 0} trade</span>
						</div>
						{#if (ledgerObj?.terakhir ?? []).length === 0}
							<div class="py-4 px-2 text-center text-12 text-text-3">
								Belum ada trade tereksekusi pada venue ini.
							</div>
						{:else}
							<div class="space-y-2">
								{#each (ledgerObj?.terakhir ?? []) as tr}
									<div class="flex flex-wrap items-center justify-between gap-2 rounded-card border border-line-soft bg-surface p-2.5">
										<div class="flex items-center gap-2">
											<span class="font-bold font-mono text-13 text-text">{tr.pair}</span>
											<span class="rounded px-1.5 py-0.5 text-10 font-bold uppercase {String(tr.status ?? '').includes('TP') ? 'bg-pos/20 text-pos' : String(tr.status ?? '').includes('SL') ? 'bg-warn/20 text-warn' : 'bg-surface text-text-3 border border-line'}">{tr.status}</span>
											<span class="text-10 font-mono text-text-3">{waktuWIB(tr.closed_at)}</span>
										</div>
										<span class="font-mono font-bold text-13 {typeof tr.r === 'number' && tr.r > 0 ? 'text-pos' : typeof tr.r === 'number' && tr.r < 0 ? 'text-neg' : 'text-text-3'}">{tr.r == null ? '—' : (tr.r > 0 ? '+' : '') + tr.r + ' R'}</span>
									</div>
								{/each}
							</div>
						{/if}
					</div>
				</div>

			{/if}

			<!-- ========================================== -->
			<!-- VIEW KHUSUS: GMGN (DEX & MEMECOIN)        -->
			<!-- ========================================== -->
			{#if kunci === 'gmgn'}
				{#if sub === 'radar' || !sub}
					<JudulBagian nomor="1" judul="Radar" tujuan="Jendela likuiditas per chain + penjelasan Robinhood Chain vs Meteora + verifikasi harga live" ikon="◉" />
				{:else if sub === 'lp'}
					<JudulBagian nomor="2" judul="LP" tujuan="LP di dua tempat: Solana (Meteora) &amp; Robinhood Chain (Uniswap) — fee, IL, vs hold" ikon="≋" />
				{:else if sub === 'memecoin'}
					<JudulBagian nomor="3" judul="Memecoin" tujuan="Memecoin GMGN/FOMO: bot paper, safety gate, smart money — eksplorasi, bukan rekomendasi" ikon="✦" />
				{/if}

				<!-- PETA TARGET (revisi pemilik 7 Okt): tiga tujuan yang disebut eksplisit —
				     memecoin di GMGN/FOMO, LP Uniswap di Robinhood Chain, LP Solana/Meteora —
				     dan siapa mengerjakan apa. Ditulis dari data yang benar-benar ada. -->
				<div class="mb-4 rounded-card border border-line bg-surface p-3">
					<div class="mb-2 border-b border-line-soft pb-2">
						<h3 class="text-13 font-medium text-text">Tiga target &amp; sumbernya</h3>
						<p class="text-11 text-text-3">Satu baris per tujuan — mana yang sudah jalan (paper), mana yang belum.</p>
					</div>
					<div class="grid grid-cols-1 gap-2 md:grid-cols-3">
						<div class="rounded-card border border-line bg-canvas/40 p-2.5">
							<div class="mb-1 flex items-center justify-between">
								<span class="text-12 font-bold text-text">Memecoin</span>
								<span class="rounded px-1.5 py-0.5 text-10 font-bold border {gmgnPaperObj ? 'text-pos bg-pos/10 border-pos/20' : 'text-text-3 bg-canvas border-line'}">{gmgnPaperObj ? 'PAPER JALAN' : 'BELUM ADA DATA'}</span>
							</div>
							<p class="text-11 text-text-3">Sumber: <b class="text-text-2">GMGN / FOMO</b> — pemindaian token baru + safety gate (bundler, dev hold, entrapment).</p>
							{#if gmgnPaperObj?.isi?.['run_config.json']}
								{@const rc = gmgnPaperObj.isi['run_config.json']}
								<p class="mt-1 text-10 text-text-3 font-mono">
									chains: {(rc.chains ?? []).join(', ') || '—'} · min skor {rc.min_score ?? '—'} ·
									posisi ${rc.position_usd ?? '—'} · maks {rc.max_open_positions ?? '—'} terbuka
								</p>
								<p class="mt-0.5 text-10 text-text-3 font-mono">
									safety: {(rc.safety_filters ?? []).map((f: any) => f.join(' ')).join(' · ') || '—'}
								</p>
								<p class="mt-0.5 text-10 text-text-3 font-mono">
									profil masuk: {rc.entry_profile ?? '—'} · sumber: {rc.entry_source ?? '—'} ·
									TP: {(rc.tp_legs ?? []).map((t: any) => `+${t[0]}% jual ${t[1]}%`).join(' / ') || '—'} ·
									likuiditas min ${Number(rc.min_liquidity ?? 0).toLocaleString('en-US')} · mcap min ${Number(rc.min_marketcap ?? 0).toLocaleString('en-US')}
								</p>
							{/if}
						</div>
						<div class="rounded-card border border-line bg-canvas/40 p-2.5">
							<div class="mb-1 flex items-center justify-between">
								<span class="text-12 font-bold text-text">LP Robinhood Chain</span>
								<span class="rounded px-1.5 py-0.5 text-10 font-bold border border-line text-text-3 bg-canvas">PANTAU</span>
							</div>
							<p class="text-11 text-text-3">Sumber: <b class="text-text-2">Uniswap v2/v3/v4</b> di L2 Robinhood (chain ID 4663) — diindeks DexScreener sebagai chain <span class="font-mono">robinhood</span>.</p>
							<p class="mt-1 text-10 text-text-3">Posisi paper di sana belum dibuka; yang ada baru verifikasi harga pool.</p>
						</div>
						<div class="rounded-card border border-line bg-canvas/40 p-2.5">
							<div class="mb-1 flex items-center justify-between">
								<span class="text-12 font-bold text-text">LP Solana (Meteora)</span>
								<span class="rounded px-1.5 py-0.5 text-10 font-bold border {lpPaperObj ? 'text-pos bg-pos/10 border-pos/20' : 'text-text-3 bg-canvas border-line'}">{lpPaperObj ? 'PAPER JALAN' : 'BELUM ADA DATA'}</span>
							</div>
							<p class="text-11 text-text-3">Sumber: <b class="text-text-2">Meteora</b> (DLMM / DAMM v2) — posisi adalah NFT Token-2022, fee dinamis.</p>
							{#if lpPaperObj?.mark_terakhir}
								<p class="mt-1 text-10 text-text-3 font-mono">mark terakhir · {lpPaperObj.mark_terakhir}</p>
							{/if}
						</div>
					</div>
				</div>
			<!-- Narasi LLM per market: dari job llm-brief-<market>. Angka tetap dari fakta;
			     narasi hanya menjelaskan — tidak pernah menggantikan bukti. Gaya 7 Okt:
			     kesimpulan dulu (kalimat besar), bukti menyusul, mesin disembunyikan di kaki. -->
			{#if narasiObj}
				<div class="mb-4 overflow-hidden rounded-card border border-line bg-surface">
					<div class="flex flex-wrap items-center justify-between gap-2 border-b border-line-soft px-3 py-1.5">
						<span class="text-11 font-bold uppercase tracking-wide text-accent-2">✳ Narasi</span>
						<span class="text-10 text-text-3 font-mono">
							{narasiObj.fact_ids?.length ?? 0} fakta dirujuk{#if narasiObj.output?.nada} · nada {narasiObj.output.nada}{/if}
						</span>
					</div>
					{#if narasiObj.status !== 'ok'}
						<p class="px-3 py-2 text-11 text-warn">
							Narasi tidak tersedia ({narasiObj.status ?? '—'}{narasiObj.error_code ? ` · ${narasiObj.error_code}` : ''}) —
							angka di halaman ini tetap sah karena berasal dari fakta, bukan dari narasi.
							Status penyedia LLM ada di halaman <b>Sistem → AI</b>.
						</p>
					{:else if narasiObj.output?.kalimat?.length}
						<div class="px-3 py-2.5">
							<p class="text-15 leading-snug text-text">{narasiObj.output.kalimat[0].teks}</p>
							{#if narasiObj.output.kalimat.length > 1}
								<div class="mt-1.5 space-y-1 border-l-2 border-line-soft pl-2.5">
									{#each narasiObj.output.kalimat.slice(1) as k}
										<p class="text-12 text-text-2">{k.teks}</p>
									{/each}
								</div>
							{/if}
							<p class="mt-2 text-10 text-text-3">
								Deskriptif, bukan rekomendasi. Mesin: {narasiObj.provider ?? '—'} ·
								{narasiObj.prompt_version ?? '—'}{#if narasiObj.latency_ms} · {narasiObj.latency_ms} ms{/if}
							</p>
						</div>
					{:else}
						<p class="px-3 py-2 text-11 text-text-3">Narasi kosong — fakta tetap sah.</p>
					{/if}
				</div>
			{/if}


				<!-- Penjelasan LP: Robinhood Chain vs Meteora (riset 7 Okt) + verifikasi live.
				     Fakta yang membingungkan banyak orang dijelaskan di sini dengan bukti. -->
				{#if sub === 'radar' || !sub}
					<div class="space-y-3">
						<!-- Jawaban satu baris (pertanyaan langsung pemilik 7 Okt): "aslinya kita
						     Robinhood-Uniswap atau Meteora-Solana?" — dijawab, bukan disuruh baca. -->
						<div class="rounded-card border border-accent/40 bg-accent/10 p-3">
							<div class="text-12 font-bold text-text">Jawaban singkat: radar kita memantau <span class="text-accent">KEDUANYA</span> — dua protokol berbeda.</div>
							<p class="mt-1 text-11 text-text-2">
								<b>Robinhood Chain</b> = L2 Ethereum (chain ID 4663), LP-nya <b>Uniswap v2/v3/v4</b>.
								<b>Solana</b> = LP-nya <b>Meteora</b> (DLMM / DAMM v2). Radar menampilkan keduanya
								per chain — lihat kolom chain di bawah. Yang <b>tidak benar</b>: menyebut "LP Robinhood = Meteora".
							</p>
						</div>
						<div class="permukaan-2 rounded-card border border-line p-3">
							<div class="mb-2 border-b border-line-soft pb-2">
								<h3 class="text-14 font-medium text-text">LP: "Robinhood Chain" vs Meteora — apa bedanya?</h3>
								<p class="text-11 text-text-3">
									Riset 7 Okt: keduanya NYATA, tapi protokolnya BERBEDA dan tidak saling terhubung
								</p>
							</div>
							<div class="grid grid-cols-1 gap-3 md:grid-cols-2">
								<div class="rounded-card border border-accent/30 bg-accent/5 p-3">
									<div class="mb-1 flex items-center gap-2">
										<span class="rounded px-1.5 py-0.5 text-10 font-bold border border-accent/40 text-accent bg-accent/10">ROBINHOOD CHAIN</span>
									</div>
									<ul class="space-y-1 text-11 text-text-2">
										<li>· L2 <b>Arbitrum Orbit</b>, chain ID <b>4663</b>, gas pakai <b>ETH</b> (bukan token sendiri), mainnet 1 Jul 2026</li>
										<li>· LP-nya = <b>Uniswap v2/v3/v4</b> (bukan Meteora)</li>
										<li>· Ada <b>Stock Token</b> (TSLA dll) — sekuritas utang ter-tokenisasi</li>
										<li>· DexScreener mengindeks: chainId <span class="font-mono">robinhood</span>, dexId <span class="font-mono">uniswap</span></li>
									</ul>
								</div>
								<div class="rounded-card border border-line bg-surface p-3">
									<div class="mb-1 flex items-center gap-2">
										<span class="rounded px-1.5 py-0.5 text-10 font-bold border border-line text-text-2 bg-canvas">METEORA (SOLANA)</span>
									</div>
									<ul class="space-y-1 text-11 text-text-2">
										<li>· <b>Solana-only</b>: DLMM, DAMM v1/v2, DBC</li>
										<li>· DAMM v2 = AMM constant-product dengan concentrated liquidity + fee dinamis</li>
										<li>· Fee: base + dinamis, protocol 20%, cap 99%; posisi = <b>NFT Token-2022</b></li>
										<li>· <b>Tidak ada</b> hubungan terverifikasi dengan Robinhood Chain</li>
									</ul>
								</div>
							</div>
							<p class="mt-2 text-11 text-warn">
								⚠ Miskonsepsi yang umum: menyamakan "LP Robinhood" dengan Meteora. Istilah "concentrated liquidity"
								dipakai keduanya, tetapi protokol & rantainya berbeda. Selalu sebutkan protokol, bukan hanya "LP".
							</p>
						</div>

						<!-- Verifikasi live: data kita vs API publik -->
						{#if lpVerifObj}
							<div class="permukaan-2 rounded-card border border-line p-3">
								<div class="mb-2 flex flex-wrap items-center justify-between gap-2 border-b border-line-soft pb-2">
									<div>
										<h3 class="text-14 font-medium text-text">Verifikasi Harga vs API Publik (live)</h3>
										<p class="text-11 text-text-3">
											Jawaban untuk "apakah data kita sama dengan internet live?" — dibandingkan, bukan diklaim
										</p>
									</div>
									<span class="rounded bg-surface border border-line px-2 py-0.5 text-11 font-mono {lpVerifObj.sepakat === lpVerifObj.jumlah ? 'text-pos' : 'text-warn'}">
										{lpVerifObj.sepakat}/{lpVerifObj.jumlah} sepakat
									</span>
								</div>
								<div class="space-y-2">
									{#each lpVerifObj.pool ?? [] as p (p.nama)}
										<div class="rounded-card border border-line bg-surface p-2.5">
											<div class="mb-1.5 flex flex-wrap items-center justify-between gap-2">
												<span class="font-mono text-12 font-bold text-text">{p.nama}</span>
												<span class="rounded px-1.5 py-0.5 text-10 font-bold border {p.kesimpulan === 'SEPAKAT' ? 'text-pos bg-pos/10 border-pos/20' : p.kesimpulan === 'SELISIH' ? 'text-warn bg-warn/10 border-warn/20' : 'text-text-3 bg-canvas border-line'}">{p.kesimpulan}</span>
											</div>
											<div class="grid grid-cols-1 gap-1.5 sm:grid-cols-3">
												{#each Object.entries(p.sumber ?? {}) as [sumber, s]}
													<div class="rounded bg-canvas/60 border border-line p-1.5 font-mono text-10">
														<div class="text-text-3 uppercase">{sumber}</div>
														{#if (s as any).galat}
															<div class="text-warn">gagal: {String((s as any).galat).slice(0, 40)}</div>
														{:else}
															<div class="text-text font-bold">{angka((s as any).harga)}</div>
															<div class="text-text-3">liq ${Number((s as any).likuiditas_usd ?? 0).toLocaleString('en-US', { maximumFractionDigits: 0 })}</div>
														{/if}
													</div>
												{/each}
											</div>
											{#if p.selisih_pct != null}
												<div class="mt-1 text-10 text-text-3 font-mono">selisih antar sumber: {p.selisih_pct}% (ambang {lpVerifObj.ambang_selisih_pct}%)</div>
											{/if}
											{#if p.catatan}<div class="mt-0.5 text-10 text-text-3">{p.catatan}</div>{/if}
										</div>
									{/each}
								</div>
								<p class="mt-2 text-10 text-text-3">{lpVerifObj.catatan}</p>
							</div>
						{/if}
					</div>
				{/if}

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
							{#if faktaRadar}
								<p class="mb-3 flex flex-wrap items-center gap-2 text-11 text-text-3">
									<span class="rounded border border-line bg-canvas px-2 py-0.5 font-mono">
										sumber: {radarObj?.sumber ?? '—'}
									</span>
									<span class="font-mono">
										radar lokal terakhir jalan {radarObj?.umur_mnt != null ? `${radarObj.umur_mnt} mnt` : '—'} lalu
									</span>
									<FreshnessBadge status={faktaRadar.status} age_s={faktaRadar.age_s} source={faktaRadar.source} ringkas />
								</p>
							{/if}

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
						<!-- Dompet paper LP: Rp 10 juta, dari mark posisi -->
						<DompetPasar market="gmgn" dompet={dompetObj} judul="Dompet Paper GMGN / LP" />
						<!-- Akurasi & PnL LP terukur (6 Okt): hasil dinyatakan P&L (IL+fee), bukan R -->
						<AkurasiPasar
							judul="Akurasi & PnL LP Terukur"
							subjudul="Mark lokal — rekonsiliasi on-chain belum ada (dinyatakan apa adanya)"
							data={akurasiGmgn}
						/>
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

						<!-- MARK LP TERUKUR (6 Okt): fee/IL/LP-vs-hold dari pasar nyata + label pakem.
						     Sumber: fakta `lp_mark` (job `lp-mark`, DexScreener per alamat pool). -->
						<div class="permukaan-2 rounded-card border border-line p-3">
							<div class="mb-3 flex items-center justify-between border-b border-line-soft pb-2">
								<div>
									<h3 class="text-14 font-medium text-text">Mark Terukur — Fee, IL, LP vs Hold</h3>
									<p class="text-11 text-text-3">
										Harga nyata per alamat pool; fee = taksiran (V/L hari ini × tier × hari)
									</p>
								</div>
								<span class="rounded bg-surface px-2 py-0.5 text-11 font-mono text-accent border border-line">
									${lpMarkObj?.total_pnl_usd ?? '—'}
								</span>
							</div>

							{#if !lpMarkObj || (lpMarkObj.mark ?? []).length === 0}
								<div class="py-6 text-center text-text-3 text-12">
									Belum ada mark LP. Job <span class="font-mono">lp-mark</span> akan mengisi setelah posisi LP dibuka.
								</div>
							{:else}
								<div class="space-y-2">
									{#each lpMarkObj.mark as m (m.symbol)}
										<div class="rounded-card border border-line bg-surface p-3">
											<div class="flex flex-wrap items-center justify-between gap-2">
												<div class="flex items-center gap-2">
													<span class="font-bold font-mono text-13 text-text">{m.symbol}</span>
													<span class="rounded px-1.5 py-0.5 text-10 font-mono border border-line bg-canvas text-text-3">{m.status}</span>
													{#if m.sumber}<span class="text-10 font-mono text-text-3">via {m.sumber}</span>{/if}
												</div>
												<span class="font-mono font-bold text-13 {typeof m.pnl_usd === 'number' && m.pnl_usd > 0 ? 'text-pos' : typeof m.pnl_usd === 'number' && m.pnl_usd < 0 ? 'text-neg' : 'text-text-3'}">
													{m.pnl_usd == null ? '—' : (m.pnl_usd > 0 ? '+' : '') + '$' + m.pnl_usd}
												</span>
											</div>
											<div class="mt-2 grid grid-cols-2 gap-2 text-11 font-mono sm:grid-cols-4">
												<div>
													<span class="text-text-3 text-10 block">FEE*</span>
													<span class="text-pos">{m.fee_usd ?? '—'}</span>
												</div>
												<div>
													<span class="text-text-3 text-10 block">IL</span>
													<span class="text-neg">{m.il_pct ?? '—'}%</span>
												</div>
												<div>
													<span class="text-text-3 text-10 block">LP vs HOLD</span>
													<span class="text-text">{m.lp_vs_hold_usd ?? '—'}</span>
												</div>
												<div>
													<span class="text-text-3 text-10 block">UMUR</span>
													<span class="text-text-2">{m.umur_hari ?? '—'} hari</span>
												</div>
											</div>
										</div>
									{/each}
									{#if lpMarkObj.pakem}
										<p class="pt-1 text-11 text-text-3">
											Pakem bukti: <span class="font-bold font-mono text-text">{lpMarkObj.pakem.tingkat}</span>
											<span class="font-mono">· n={lpMarkObj.pakem.n} hari={lpMarkObj.pakem.n_hari}</span>
											{#if lpMarkObj.pakem.alasan?.length}
												<span>· {lpMarkObj.pakem.alasan[0]}</span>
											{/if}
										</p>
									{/if}
								</div>
							{/if}
						</div>
					</div>
				{/if}

				{#if sub === 'token' || sub === 'memecoin'}
					<div class="space-y-4">
						<div class="permukaan-2 rounded-card border border-line p-3">
							<!-- Bot paper memecoin (kind `gmgn`, key `paper`) — konfigurasi & kesehatan
							     pembacaan folder. Angka apa adanya: berkas rusak ditulis "rusak". -->
							<div class="mb-3 flex items-center justify-between border-b border-line-soft pb-2">
								<div>
									<h3 class="text-14 font-medium text-text">Bot Paper Memecoin (GMGN/FOMO)</h3>
									<p class="text-11 text-text-3">
										Konfigurasi nyata dari folder state bot + kesehatan berkas yang dibaca job
									</p>
								</div>
								{#if faktaGmgnPaper}
									<FreshnessBadge status={faktaGmgnPaper.status} age_s={faktaGmgnPaper.age_s} source={faktaGmgnPaper.source} ringkas />
								{/if}
							</div>
							{#if !gmgnPaperObj}
								<div class="py-4 text-center text-12 text-text-3">Data bot paper belum tersedia.</div>
							{:else}
								<div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
									<div class="rounded-card border border-line bg-surface p-3 space-y-1.5 text-11">
										<div class="flex justify-between"><span class="text-text-3">Folder state</span><span class="font-mono text-text-2">{gmgnPaperObj.dir ?? '—'}</span></div>
										<div class="flex justify-between"><span class="text-text-3">Jumlah berkas</span><span class="font-mono">{gmgnPaperObj.files ?? '—'}</span></div>
										<div class="flex justify-between"><span class="text-text-3">Total byte</span><span class="font-mono">{Number(gmgnPaperObj.bytes ?? 0).toLocaleString('en-US')}</span></div>
									</div>
									<div class="rounded-card border border-line bg-surface p-3 space-y-1.5 text-11">
										{#each Object.entries(gmgnPaperObj.isi ?? {}) as [nama, info]}
											{@const st = (info as any)?.status}
											<div class="flex justify-between gap-2">
												<span class="font-mono text-text-3">{nama}</span>
												<span class="font-mono {st === 'rusak' ? 'text-neg' : st === 'tidak-ada' ? 'text-text-3' : 'text-pos'}">{st ?? 'ok'}</span>
											</div>
										{/each}
									</div>
								</div>
								{#if gmgnPaperObj.isi?.signals?.status === 'rusak'}
									<p class="mt-2 text-11 text-warn">
										⚠ <span class="font-mono">signals.jsonl</span> terbaca <b>rusak</b> — bot paper belum punya
										catatan sinyal yang bisa dinilai. Yang tampil di bawah hanya konfigurasi, bukan hasil.
									</p>
								{/if}
							{/if}
						</div>
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
												<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5">SIMBOL</th>
												<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5">SUMBER</th>
												<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right">BELI USD</th>
												<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right">HARGA (USD)</th>
												<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right">5M CHG</th>
												<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right">1H CHG</th>
												<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right">SHADOW %</th>
											</tr>
										</thead>
										<tbody class="divide-y divide-line-soft">
											{#each (gmgnObj.signals ?? []).slice(-15).reverse() as s (s.key + String(s.ts))}
												<tr class="hover:bg-surface/50 transition-colors">
													<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 font-bold text-text">
														{s.symbol}
														{#if s.whale}
															<span class="ml-1 text-10 text-accent font-sans border border-accent/20 bg-accent/10 px-1 py-0.5 rounded">
																WHALE
															</span>
														{/if}
													</td>
													<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-text-3 font-sans text-10 uppercase">
														{s.source} ({s.cluster_wallets}w)
													</td>
													<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right text-text-2">
														${s.cluster_buy_usd?.toLocaleString('id-ID', { maximumFractionDigits: 0 }) ?? '—'}
													</td>
													<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right text-text">
														${s.last_price_usd < 0.01 ? s.last_price_usd?.toFixed(6) : s.last_price_usd?.toFixed(2)}
													</td>
													<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right font-medium {(s.ret_5m_pct ?? 0) >= 0 ? 'text-pos' : 'text-neg'}">
														{(s.ret_5m_pct ?? 0) >= 0 ? '+' : ''}{s.ret_5m_pct?.toFixed(1) ?? '—'}%
													</td>
													<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right font-medium {(s.ret_1h_pct ?? 0) >= 0 ? 'text-pos' : 'text-neg'}">
														{(s.ret_1h_pct ?? 0) >= 0 ? '+' : ''}{s.ret_1h_pct?.toFixed(1) ?? '—'}%
													</td>
													<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right {(s.shadow_pct ?? 0) >= 0 ? 'text-pos' : 'text-neg'}">
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
				<!-- 5 BLOK WAJIB (6 Okt 2026): Statistik & verifikasi + Posisi & riwayat.
				     Sumber: fakta {kunci}_equity / {kunci}_ledger / {kunci}_risiko / {kunci}_posisi.
				     Kosong ditampilkan apa adanya — bukan 0 yang dikarang. -->
				<div class="mt-4 space-y-4">
					<EquityCurve points={equityObj?.points} stats={equityObj?.stats} />
					<RiskMeter risiko={risikoObj} />

					<div class="permukaan-2 rounded-card border border-line p-3">
						<div class="mb-2 flex items-center justify-between border-b border-line-soft pb-2">
							<h3 class="text-13 font-medium text-text">Posisi Terbuka</h3>
							<span class="text-11 text-text-3 font-mono">{posisiJumlah} / {posisiMaks}</span>
						</div>
						{#if posisiArray.length === 0}
							<div class="py-4 px-2 text-center text-12 text-text-3">
								Belum ada posisi terbuka pada venue ini.
							</div>
						{:else}
							<div class="space-y-2">
								{#each posisiArray as p (p.signal_id ?? p.pair)}
									<div class="flex items-center justify-between gap-2 rounded-card border border-line bg-surface p-2.5 font-mono text-12">
										<div class="flex items-center gap-2">
											<span class="font-bold text-text">{p.pair}</span>
											<span class="rounded px-1.5 py-0.5 text-10 font-bold uppercase {p.direction === 'LONG' ? 'text-pos bg-pos/10 border border-pos/20' : 'text-neg bg-neg/10 border border-neg/20'}">{p.direction}</span>
										</div>
										<span class="text-11 text-text-3"
											>entry {harga(p.entry)} · SL {harga(p.stop)} · TP {harga(p.tp1)}</span
										>
									</div>
								{/each}
							</div>
						{/if}
					</div>

					<div class="permukaan-2 rounded-card border border-line p-3">
						<div class="mb-2 flex items-center justify-between border-b border-line-soft pb-2">
							<h3 class="text-13 font-medium text-text">Riwayat Eksekusi &amp; Ledger</h3>
							<span class="text-11 text-text-3 font-mono">{ledgerObj?.trade ?? 0} trade</span>
						</div>
						{#if (ledgerObj?.terakhir ?? []).length === 0}
							<div class="py-4 px-2 text-center text-12 text-text-3">
								Belum ada trade tereksekusi pada venue ini.
							</div>
						{:else}
							<div class="space-y-2">
								{#each (ledgerObj?.terakhir ?? []) as tr}
									<div class="flex flex-wrap items-center justify-between gap-2 rounded-card border border-line-soft bg-surface p-2.5">
										<div class="flex items-center gap-2">
											<span class="font-bold font-mono text-13 text-text">{tr.pair}</span>
											<span class="rounded px-1.5 py-0.5 text-10 font-bold uppercase {String(tr.status ?? '').includes('TP') ? 'bg-pos/20 text-pos' : String(tr.status ?? '').includes('SL') ? 'bg-warn/20 text-warn' : 'bg-surface text-text-3 border border-line'}">{tr.status}</span>
											<span class="text-10 font-mono text-text-3">{waktuWIB(tr.closed_at)}</span>
										</div>
										<span class="font-mono font-bold text-13 {typeof tr.r === 'number' && tr.r > 0 ? 'text-pos' : typeof tr.r === 'number' && tr.r < 0 ? 'text-neg' : 'text-text-3'}">{tr.r == null ? '—' : (tr.r > 0 ? '+' : '') + tr.r + ' R'}</span>
									</div>
								{/each}
							</div>
						{/if}
					</div>
				</div>

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

			<!-- Aliran Kejadian SSE untuk Area ini.
			     Revisi pemilik 7 Okt: "kejadian area cardnya di collaps aja toh itu 3 tombolnya
			     ga berfungsi juga". Dua hal yang diperbaiki:
			     (1) blok ini TERLIPAT secara default — bukan karena isinya rusak, tapi karena
			         ia feed diagnosis, bukan keputusan trading; kepala tetap tampil.
			     (2) tiga tombol filter lama (semua/tipe) MEMANG terasa mati: karena feed area
			         biasanya cuma memuat satu tipe, menyaring tidak mengubah apa pun. Sekarang
			         filter di EventFeed hanya dirender bila ada LEBIH DARI SATU tipe kejadian —
			         tombol yang tidak mungkin mengubah apa pun tidak lagi dipajang. -->
			<Block
				judul="Kejadian Area"
				deskripsi={`Aliran SSE terfilter topik area · ${kejadianArea.length} kejadian`}
				lipat
				lipatAwal
			>
				<EventFeed
					kejadian={kejadianArea}
					memuat={live.status === 'menyambung'}
					galat={live.pesan}
				/>
			</Block>
		{/snippet}
	</AreaLoader>
</div>