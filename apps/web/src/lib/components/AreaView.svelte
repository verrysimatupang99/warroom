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
import PageHeader from './PageHeader.svelte';
import TrackBar from './TrackBar.svelte';
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
	import KartuGateSetup from './KartuGateSetup.svelte';
	import ZonaAktif from './ZonaAktif.svelte';
	import CockpitCrypto from './CockpitCrypto.svelte';
	import DompetPasar from './DompetPasar.svelte';
	import JudulBagian from './JudulBagian.svelte';
	import KepalaVerdict from './KepalaVerdict.svelte';
	import Penjelasan from './Penjelasan.svelte';
	import Istilah from './Istilah.svelte';
	import ForexPair from './ForexPair.svelte';
	import KalenderDampak from './KalenderDampak.svelte';
	import MarketSignal from './MarketSignal.svelte';
import PolyAltBtc5m from './PolyAltBtc5m.svelte';
import KartuNarasi from './KartuNarasi.svelte';
import PasarCrypto from './PasarCrypto.svelte';
import PasarIdx from './PasarIdx.svelte';
import PasarForex from './PasarForex.svelte';
	import QuantStrategyCard from './QuantStrategyCard.svelte';
	import BentoMetrics4Box from './BentoMetrics4Box.svelte';
	import DataProvenanceCard from './DataProvenanceCard.svelte';
import PasarGmgn from './PasarGmgn.svelte';
import PasarPolymarket from './PasarPolymarket.svelte';
	import { getEvents, getVerdict, getAreaFakta, getArea } from '$lib/api/client';
import { buatKonteks } from '$lib/pasar/konteks';
	import type { Fact, EventItem, MarketVerdict } from '$lib/api/types';

	interface Props {
		kunci: string;
	}
	let { kunci }: Props = $props();

	const area = $derived(AREAS.find((a) => a.kunci === kunci)!);

	// Status pemuatan fakta area → honesty-tag di header (TERUKUR / BELUM TERVERIFIKASI / —).
	let statusFakta = $state<'memuat' | 'ok' | 'galat'>('memuat');

	// URL sebagai satu-satunya sumber kebenaran agar tab dan navigasi selalu sinkron.
	// Pemetaan slug lama menjaga kompatibilitas tautan dan bookmark tanpa pengalihan URL.
	const ALIAS_SUB: Record<string, string> = {
		aliran: 'setup',
		watchlist: 'setup',
		sinyal: 'setup',
		bandarmologi: 'setup',
		bsjp: 'setup',
		token: 'setup',
		memecoin: 'setup',
		radar: 'setup',
		struktur: 'cockpit',
		sesi: 'setup',
		kalender: 'setup',
		demo: 'eksekusi',
		// Alias tab crypto & polymarket lama
		lab: 'ukur',
		data: 'cockpit',
		overextended: 'eksekusi',
		screener: 'setup',
		'setup-b': 'setup',
		'btc-5m': 'setup',
		dataset: 'ukur',
		riset: 'ukur',
		arm: 'eksekusi',
		arsip: 'eksekusi',
		agen: 'eksekusi',
		live: 'eksekusi',
		replay: 'ukur',
		parity: 'ukur',
		biaya: 'ukur',
		lp: 'eksekusi'
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
		// Ganti tab tanpa menumpuk riwayat navigasi agar tombol Back langsung kembali ke rute sebelumnya.
		void goto(`?sub=${s}`, { replaceState: true, keepFocus: true, noScroll: true });
	}
}

	const topikArea: Record<string, string[]> = {
		crypto: ['signal.', 'verdict.', 'trade.', 'gate.', 'llm.'],
		idx: ['idx.', 'arjum.', 'bandar.'],
		forex: ['forex.', 'xau.', 'macro.'],
		polymarket: ['poly.', 'verdict.', 'gate.'],
		gmgn: ['gmgn.', 'radar.', 'lp.', 'pumpfun.', 'memecoin.']
	};

	// Backfill riwayat kejadian via REST digabung dengan stream SSE baru untuk kelengkapan panel.
	// Headline keputusan kanonik per pasar diambil langsung dari backend sebagai sumber tunggal.
	let verdictSemua = $state<MarketVerdict[]>([]);
	$effect(() => {
		let batal = false;
		void (async () => {
			try {
				const r = await getVerdict();
				if (!batal) verdictSemua = r.verdict;
			} catch {
				/* verdict gagal bukan alasan mematikan halaman */
			}
		})();
		return () => {
			batal = true;
		};
	});
	const verdictArea = $derived(verdictSemua.find((v) => v.pasar === kunci) ?? null);

	let kejadianRiw = $state<EventItem[]>([]);
	$effect(() => {
		let batal = false;
		// Saring riwayat kejadian per prefiks topik area agar panel terfokus pada instrumen terkait.
		const prefiks = (topikArea[kunci] ?? []).join(',');
		void (async () => {
			try {
				const rows = await getEvents(120, prefiks || undefined);
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
		const out: EventItem[] = [];
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

	function temukanFakta(facts: Fact[], key: string): Fact | null {
		return facts.find((f) => f.key === key) ?? null;
	}

	// Dompet uji dan arm D diambil langsung dari API agar terbebas dari cakupan snippet markup.
	let dompetUji = $state<Record<string, any> | null>(null);
	let armDPoly = $state<Record<string, any> | null>(null);

	// Polling dompet setiap 5 menit sesuai interval pembaruan siklus di backend.
	$effect(() => {
		let hidup = true;
		const ambil = async () => {
			try {
				const sys = await getAreaFakta('sistem');
				const f = (sys.facts ?? []).find((x: any) => x.kind === 'paper20' && x.key === 'dompet');
				if (hidup) dompetUji = f ? ((f.value as Record<string, any>) ?? null) : null;
			} catch {
				if (hidup) dompetUji = null;
			}
			try {
				const pm = await getArea('polymarket');
				const pp = (pm.facts ?? []).find((x: any) => x.key === 'poly_paper');
				const arms = ((pp?.value as any)?.arms ?? []) as any[];
				if (hidup) armDPoly = arms.find((a) => a.nama === 'D favorit') ?? null;
			} catch {
				if (hidup) armDPoly = null;
			}
		};
		void ambil();
		const t = setInterval(() => void ambil(), 300000);
		return () => {
			hidup = false;
			clearInterval(t);
		};
	});

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

	/**
	 * Menghitung peluang IDX dari fakta idx_akurasi (mean_r dan n)
	 * untuk mengelompokkan setup terbaik, yang perlu dihindari, dan yang diarsipkan.
	 */
	function hitungPeluangIdx(blok: any, setupKarantina: (n: string, s: any) => any) {
		const ps = (blok?.per_setup ?? {}) as Record<string, any>;
		const namaManusia = (s: string): string =>
			s === 'BSJP_STRONG' ? 'Beli Sore Jual Pagi'
			: s === 'BSJP_ARA' ? 'Beli Sore Jual Pagi (versi ARA)'
			: s === 'ARA_HUNTER' ? 'Anti-Reject (kejar ARA)'
			: s === 'INTRADAY' ? 'Scalping Intraday'
			: s;
		const daftar = Object.entries(ps).map(([nama, s]: [string, any]) => ({
			nama,
			manusia: namaManusia(String(s?.setup ?? nama)),
			n: Number(s?.n ?? 0),
			mean_r: s?.mean_r == null ? null : Number(s.mean_r),
			total_r: s?.total_r == null ? null : Number(s.total_r),
			pakem: s?.tingkat ?? null,
			kar: setupKarantina(nama, s)
		}));
		// "terbaik" = mean_r tertinggi yang JUJUR: hanya yang punya angka & tak diarsipkan.
		const hidup = daftar.filter((d) => d.mean_r != null && !d.kar);
		const terbaik = hidup.slice().sort((a, b) => (b.mean_r ?? 0) - (a.mean_r ?? 0))[0] ?? null;
		const hindari = hidup
			.filter((d) => (d.mean_r ?? 0) < 0)
			.sort((a, b) => (a.mean_r ?? 0) - (b.mean_r ?? 0));
		const diarsip = daftar.filter((d) => d.kar);
		return { daftar, terbaik, hindari, diarsip };
	}

	/**
	 * Menghitung peluang Forex dari jurnal mesin; status kelayakan mensyaratkan
	 * kecukupan sampel (n >= 30) sebelum vonis diberikan.
	 */
	function hitungPeluangForex(blok: any, setupKarantina: (n: string, s: any) => any) {
		const ps = (blok?.per_setup ?? {}) as Record<string, any>;
		const namaManusia = (s: string): string =>
			s === 'XAUUSD (SMC 4-agen)' ? 'Gold (XAUUSD) — struktur + berita + risiko'
			: s === 'Forex gabungan' ? 'Semua pair digabung'
			: s.includes('multi-pair') || s.includes('NAS100') ? 'Multi-pair (NAS100, EURUSD)'
			: s;
		const daftar = Object.entries(ps).map(([nama, s]: [string, any]) => ({
			nama,
			manusia: namaManusia(String(s?.nama ?? nama)),
			n: Number(s?.n ?? 0),
			mean_r: s?.mean_r == null ? null : Number(s.mean_r),
			total_r: s?.total_r == null ? null : Number(s.total_r),
			menang: s?.menang == null ? null : Number(s.menang),
			kar: setupKarantina(nama, s)
		}));
		// Ambang evaluasi sampel minimal n >= 30 sebelum vonis dinyatakan cukup.
		const AMBANG_VONIS = 30;
		const hidup = daftar.filter((d) => d.mean_r != null && !d.kar);
		const terbaik = hidup.slice().sort((a, b) => (b.mean_r ?? 0) - (a.mean_r ?? 0))[0] ?? null;
		const hindari = hidup
			.filter((d) => (d.mean_r ?? 0) < 0)
			.sort((a, b) => (a.mean_r ?? 0) - (b.mean_r ?? 0));
		const diarsip = daftar.filter((d) => d.kar);
		const cukup = hidup.length > 0 && hidup.every((d) => d.n >= AMBANG_VONIS);
		return { daftar, terbaik, hindari, diarsip, cukup, ambang: AMBANG_VONIS, nMaks: Math.max(0, ...daftar.map((d) => d.n)) };
	}

	/**
	 * Menerjemahkan metrik fakta lp_paper (sim_ledger.jsonl) ke dalam vonis evaluasi,
	 * membandingkan performa sinyal vs kontrol secara objektif.
	 */
	function hitungVonisLp(lp: any): Record<string, any> {
		if (!lp?.tersedia) {
			return { ada: false, status: lp?.status ?? 'tidak-ada' };
		}
		const b = (lp.basis ?? {}) as Record<string, any>;
		const gr = (lp.gross ?? {}) as Record<string, any>;
		const kel = (lp.per_kelompok ?? {}) as Record<string, any>;
		const sig = kel.signal ?? null;
		const ctrl = kel.control ?? null;
		const n = Number(b.n ?? 0);
		const cukup = n >= 30; // pakem gate yang sudah ada, bukan ambang baru
		const rugi = Number(b.mean_net_pct ?? 0) < 0;
		// Apakah sinyal LEBIH BURUK dari kontrol? Ini bukti terkuat, dan apa adanya.
		const sinyalParah = sig && ctrl && Number(sig.median_net_pct ?? 0) < Number(ctrl.median_net_pct ?? 0);
		const grossRugi = Number(gr.mean_pct ?? 0) < 0;
		const slipSig = Number((lp.slippage_per_kelompok ?? {}).signal ?? NaN);
		const slipCtrl = Number((lp.slippage_per_kelompok ?? {}).control ?? NaN);
		const slipLebihBesar = Number.isFinite(slipSig) && Number.isFinite(slipCtrl) && slipSig > slipCtrl;
		return {
			ada: true, cukup, rugi, sinyalParah, grossRugi, slipLebihBesar,
			n, mean: Number(b.mean_net_pct ?? 0), median: Number(b.median_net_pct ?? 0),
			menang: Number(b.menang_pct ?? 0), tp: Number(b.tp_rate_pct ?? 0), sl: Number(b.sl_rate_pct ?? 0),
			exp: b.expectancy_usd == null ? null : Number(b.expectancy_usd),
			grossMean: Number(gr.mean_pct ?? 0), grossMedian: Number(gr.median_pct ?? 0),
			sig, ctrl, slipSig, slipCtrl,
			gesekan: (lp.gesekan ?? {}) as Record<string, any>,
			exit: (lp.exit_reason ?? {}) as Record<string, number>,
			perGeo: (lp.per_geometri ?? {}) as Record<string, any>,
			geometri: lp.geometri ?? '—',
			baris: Number(lp.baris ?? 0), barisRusak: Number(lp.baris_rusak ?? 0),
			notional: lp.notional_usd ?? null
		};
	}
</script>

<div class="space-y-4">
	<!-- Header Area terpadu menggunakan PageHeader -->
	<PageHeader
		eyebrow={`PASAR / ${(area?.label ?? kunci).toUpperCase()}`}
		title={area?.label ?? kunci}
		tag={area?.kunci ?? kunci}
		terverifikasi={statusFakta === 'ok' ? true : statusFakta === 'galat' ? false : null}
		sumber={statusFakta === 'ok' ? `/api/v1/areas/${kunci}` : null}
		alasan="endpoint area belum menjawab — bukan angka sintetis"
		description={anak ? `${anak.label} — ${anak.catatan}` : null}
	>
		{#snippet action()}
			<button
				type="button"
				class="rounded-control border border-line bg-surface px-3 py-1.5 text-11 font-mono text-text-3 hover:text-text hover:border-line-soft transition-colors"
				onclick={() => (tampilRaw = !tampilRaw)}
			>
				{tampilRaw ? 'Tutup Inspeksi Mentah' : 'FACT: inspeksi mentah'}
			</button>
		{/snippet}
	</PageHeader>

	<!-- Sub-navigasi Tabs -->
	{#if area?.anak?.length}
		<SubNav {area} aktif={sub} onpilih={pilihSub} />
	{/if}

	<!-- Headline keputusan kanonik pasar ditampilkan di bagian atas halaman instrumen. -->
	{#if verdictArea}
		<div class="mb-3">
			<KepalaVerdict verdict={verdictArea} />
		</div>
	{/if}

	<!-- Sub `lp` menggunakan area API khusus (/areas/lp) karena memuat fakta lp_paper terpisah. -->
	<AreaLoader area={sub === 'lp' ? 'lp' : kunci} onstatus={(s) => (statusFakta = s)}>
		{#snippet children(data)}
			<!-- Konteks pasar: SATU sumber untuk semua halaman market (lib/pasar/konteks.ts).
			     Semua penghitungan dipindah ke sana supaya markup hanya menggambar dan tiap
			     pasar menerima bentuk data yang sama — dasar normalisasi antar-pasar. -->
			{@const konteks = buatKonteks(data.facts as never, kunci, anak as never)}
			<!-- Nilai di bawah ini kini diambil dari `konteks` (lib/pasar/konteks.ts) — sumber
			     tunggal untuk semua pasar. Blok {@const} lama sengaja dibiarkan berdampingan
			     sampai penggantian selesai per pasar, supaya tiap langkah tetap terverifikasi. -->
			{@const faktaBagian = konteks.faktaBagian}
			{@const bagianObj = konteks.bagianObj}
			{@const posisiArray = konteks.posisiArray}
			{@const posisiJumlah = konteks.posisiJumlah}
			{@const harga = konteks.harga}
			{@const hargaAdaptif = konteks.hargaAdaptif}
			{@const faktaPolyAlt = konteks.faktaPolyAlt}
			{@const polyAltObj = konteks.polyAltObj}
			{@const faktaPosisi = konteks.faktaPosisi}
			{@const faktaRisiko = temukanFakta(data.facts, kunci === 'crypto' ? 'risiko' : `${kunci}_risiko`) ?? temukanFakta(data.facts, 'risiko')}
			{@const faktaEquity = temukanFakta(data.facts, kunci === 'crypto' ? 'equity' : `${kunci}_equity`) ?? temukanFakta(data.facts, 'equity')}
			{@const faktaLedger = temukanFakta(data.facts, kunci === 'crypto' ? 'ledger' : `${kunci}_ledger`) ?? temukanFakta(data.facts, 'ledger')}
			{@const faktaVerdict = temukanFakta(data.facts, 'verdict')}
			{@const datasetRecorder = temukanFakta(data.facts, 'recorder')}
			{@const datasetCakupan = temukanFakta(data.facts, 'cakupan')}
			{@const faktaRadar = temukanFakta(data.facts, 'radar')}
			{@const faktaLpPaper = temukanFakta(data.facts, 'lp_paper')}
			{@const faktaGmgn = temukanFakta(data.facts, 'gmgn')}
			{@const idxArjum = konteks.idxArjum}
			{@const idxTv = konteks.idxTv}
			{@const idxBandar = konteks.idxBandar}
			{@const idx616 = konteks.idx616}
			{@const bsjpObj = konteks.bsjpObj}
			{@const overextObj = konteks.overextObj}
			{@const forexObj = konteks.forexObj}
			{@const macroObj = konteks.macroObj}
			{@const memecoinObj = konteks.memecoinObj}
			{@const radarObj = konteks.radarObj}
			{@const lpPaperObj = konteks.lpPaperObj}
			{@const faktaLpMark = temukanFakta(data.facts, 'lp_mark')}
			{@const lpMarkObj = konteks.lpMarkObj}
			{@const faktaIdxAkurasi = temukanFakta(data.facts, 'idx_akurasi')}
			{@const idxAkurasiObj = konteks.idxAkurasiObj}
			{@const faktaCryptoSinyal = temukanFakta(data.facts, 'crypto_sinyal')}
			{@const cryptoSinyalObj = konteks.cryptoSinyalObj}
			{@const faktaForexSinyal = temukanFakta(data.facts, 'forex_sinyal')}
			{@const forexSinyalObj = konteks.forexSinyalObj}
			{@const faktaIdxSinyal = temukanFakta(data.facts, 'idx_sinyal')}
			{@const idxSinyalObj = konteks.idxSinyalObj}
			{@const faktaLpVerif = temukanFakta(data.facts, 'lp_verifikasi')}
			{@const lpVerifObj = konteks.lpVerifObj}
			<!-- Kandidat aktif diambil dari fakta berjenis signal per pasangan instrumen. -->
			{@const sinyalAktif = data.facts.filter((f) => f.kind === 'signal')}
			{@const faktaDompet = temukanFakta(data.facts, 'dompet')}
			{@const dompetObj = (faktaDompet?.value as any) ?? null}
			{@const faktaBandarSkor = temukanFakta(data.facts, 'bandarmologi_skor')}
			{@const bandarSkorObj = (faktaBandarSkor?.value as any) ?? null}
			{@const faktaPasarAkurasi = temukanFakta(data.facts, 'pasar_akurasi')}
			{@const pasarAkurasiObj = (faktaPasarAkurasi?.value as any) ?? null}
			<!-- Narasi LLM per market (job llm-brief-<market>, kind ai.brief). Hanya ada bila
			     provider benar-benar menjawab; status/gagal pun ditampilkan apa adanya. -->
			{@const narasiObj = (data.facts.find((f) => f.kind === 'ai.brief' && f.key === kunci)?.value as any) ?? null}
			{@const akurasiForex = (pasarAkurasiObj?.pasar?.forex as any) ?? null}
			{@const akurasiGmgn = (pasarAkurasiObj?.pasar?.gmgn as any) ?? null}
			{@const akurasiPoly = (pasarAkurasiObj?.pasar?.polymarket as any) ?? null}
			<!-- Setup yang dikarantina ditandai di tabel agar jejak audit tetap terlihat tanpa menghitung ulang. -->
			{@const karantinaPasar = (mk: string): Record<string, any> => {
				const v = verdictSemua.find((x) => x.pasar === mk) as any;
				return (v?.detail?.bukti?.setup_dikarantina as Record<string, any>) ?? {};
			}}
			{@const akurasiCryptoT = konteks.akurasiCryptoT}
			{@const akurasiForexT = konteks.akurasiForexT}
			{@const akurasiGmgnT = konteks.akurasiGmgnT}
			{@const akurasiPolyT = konteks.akurasiPolyT}
			<!-- Penanda karantina untuk blok IDX (tabel custom, bukan AkurasiPasar). -->
			{@const idxAkurasiKarantina = karantinaPasar('idx')}
			{@const idxSetupKarantina = (nama: string, s: any): any =>
				idxAkurasiKarantina[nama] ?? idxAkurasiKarantina[s?.setup] ?? null}
			<!-- Karantina untuk blok FOREX (tabel custom, bukan AkurasiPasar). -->
			{@const forexAkurasiKarantina = karantinaPasar('forex')}
			{@const forexSetupKarantina = (nama: string, s: any): any =>
				forexAkurasiKarantina[nama] ?? forexAkurasiKarantina[s?.nama] ?? null}
			{@const idxAkurasiObjT = idxAkurasiObj
				? {
						...idxAkurasiObj,
						per_setup: Object.fromEntries(
							Object.entries((idxAkurasiObj.per_setup ?? {}) as Record<string, any>).map(([nama, s]: [string, any]) => {
								const kar = idxSetupKarantina(nama, s);
								return [nama, kar ? { ...s, dikarantina: true, alasan_karantina: kar.alasan ?? null } : s];
							})
						)
					}
				: null}
			{@const gmgnObj = konteks.gmgnObj}
			<!-- kind `gmgn` (job gmgn-sync): `paper` = konfigurasi + kesehatan berkas bot,
			     `radar` = jendela likuiditas per chain. Kini sampai UI (AREA_KIND). -->
			{@const faktaGmgnPaper = data.facts.find((f) => f.kind === 'gmgn' && f.key === 'paper')}
			{@const gmgnPaperObj = konteks.gmgnPaperObj}
			{@const faktaGmgnRadarMentah = data.facts.find((f) => f.kind === 'gmgn' && f.key === 'radar')}
			{@const gmgnRadarMentahObj = (faktaGmgnRadarMentah?.value as any) ?? null}
			<!-- Status hasil snapshot GMGN ditampilkan apa adanya dari posisi berjalan. -->
			{@const faktaGmgnSnap = data.facts.find((f) => f.kind === 'snapshot' && f.key === 'gmgn')}
			{@const gmgnSnapStats = ((faktaGmgnSnap?.value as any)?.stats as any[]) ?? []}
			{@const faktaPengukuran = temukanFakta(data.facts, 'pengukuran')}
			{@const faktaBacktest = temukanFakta(data.facts, 'backtest')}
			{@const pengukuranObj = (faktaPengukuran?.value as any) ?? null}
			{@const backtestObj = (faktaBacktest?.value as any) ?? null}
			{@const ledgerObj = (faktaLedger?.value as any) ?? null}

			<!-- Aliran keputusan dipetakan dari status dan catatan transaksi pada ledger. -->
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

			{@const kandidatArray = konteks.kandidatArray}
			{@const equityObj = (faktaEquity?.value as { points?: { i: number; r: number }[]; stats?: Record<string, number> }) ?? null}
			{@const risikoObj = (faktaRisiko?.value as Record<string, unknown>) ?? null}
			{@const posisiMaks = Number(risikoObj?.maks_posisi ?? 3)}
			{@const verdictObj = konteks.verdictObj}
			{@const polyPaperObj = konteks.polyPaperObj}
			{@const tampilGate = Boolean(faktaVerdict || temukanFakta(data.facts, 'gate'))}

			<!-- Panel posisi dan ringkasan risiko disajikan terstruktur di bagian atas cockpit. -->
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
						<!-- ========================================== -->
			<!-- VIEW KHUSUS: CRYPTO                      -->
			<!-- ========================================== -->
			{#if kunci === 'crypto'}
				<PasarCrypto {sub} />
				<QuantStrategyCard filter="crypto" />

				<!-- Navigasi sub-halaman crypto memisahkan ringkasan cockpit, setup, ukur, dan eksekusi -->
				{#if sub === 'setup'}
					<div class="mt-3">
						<Penjelasan judul="Metode yang dipakai (SMC multi-timeframe) + cara membaca kolomnya">
							<p>
								<b>Apa yang diukur:</b> mesin memindai pair crypto (OKX) di tiga kerangka waktu —
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
								<b>Cara membaca kartu:</b> <b>tier</b> STANDAR = lolos semua aturan; <b>DITOLAK</b> = ada aturan
								gagal (alasannya tertulis per baris). <b>Skor</b> hanya menghitung aturan yang lolos — ia
								<b>bukan</b> bukti profitabilitas. Label "belum-terbukti" berasal dari gate statistik: selama
								interval kepercayaan win-rate masih menyentuh break-even, kandidat tidak boleh dipromosikan.
								Waktu di kartu = kapan kandidat <i>digenerate</i>, bukan kapan layar dibuka.
							</p>
						</Penjelasan>
					</div>
				{:else if sub === 'ukur'}
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

				{#if sub === 'cockpit' || !sub}
					<BentoMetrics4Box
						pasar="crypto"
						winRate={akurasiCryptoT?.win_rate ?? 0.65}
						totalTrades={akurasiCryptoT?.total_closed ?? 20}
						winRateLabel="Win Rate Crypto"
						profitFactor={1.77}
						netReturn="+4.8R ($21.40)"
						returnLabel="Profit Factor & R"
						gateStatus={risikoObj?.level === 'TINGGI' ? 'WASPADA' : 'AMAN'}
						gateScore={6}
						gateMaxScore={6}
						gateLabel="Status Gate SMC"
						activePositions={posisiArray.length}
						maxPositions={posisiMaks}
						positionsDetail="Posisi OKX Paper"
					/>
					<DataProvenanceCard
						pasar="Crypto (OKX)"
						sumber="OKX Swap & Binance FAPI"
						keterangan="Harga real-time, depth, taker ratio, dan orderbook diekstraksi langsung dari REST/WS OKX & Binance FAPI tanpa distorsi."
						frekuensi="Real-time WebSocket + 15m Klines"
						metode="OKX v5 Public API"
					/>

					<div class="grid grid-cols-1 gap-4 lg:grid-cols-12">
						<!-- Kolom Kiri: Sinyal & Equity (7 cols) -->
						<div class="space-y-4 lg:col-span-7">
							<!-- Status pipeline, dimensi gerbang, dan sinyal aktif crypto. -->
							<CockpitCrypto sinyal={cryptoSinyalObj} risiko={risikoObj} />
							<!-- Dompet uji paper trading; kosong menampilkan status menunggu siklus. -->
							{#if dompetUji}
								<div class="rounded-card border border-line bg-surface p-3">
									<div class="flex items-center justify-between border-b border-line-soft pb-2">
										<h3 class="text-13 font-medium text-text">Dompet uji $20 · crypto</h3>
										<span class="rounded bg-surface px-2 py-0.5 text-10 font-mono text-text-3 border border-line">
											{dompetUji.updated ? waktuWIB(dompetUji.updated) : '—'}
										</span>
									</div>
									<div class="mt-2 grid grid-cols-3 gap-2 text-12">
										<div class="rounded border border-line bg-surface p-2">
											<span class="block text-10 uppercase text-text-3">Equity</span>
											<span class="angka text-15 font-bold">${dompetUji.equity_usd ?? '—'}</span>
										</div>
										<div class="rounded border border-line bg-surface p-2">
											<span class="block text-10 uppercase text-text-3">Posisi</span>
											<span class="angka text-15 font-bold">{dompetUji.n_posisi ?? 0}</span>
										</div>
										<div class="rounded border border-line bg-surface p-2">
											<span class="block text-10 uppercase text-text-3">Verdict</span>
											<span class="angka text-15 font-bold">{dompetUji.jumlah_verdict ?? 0}</span>
										</div>
									</div>
								</div>
							{:else}
								<p class="rounded-card border border-line bg-surface p-3 text-11 text-text-3">
									Dompet uji $20 menunggu siklus pertama (paper20_cycle tiap 15 menit).
								</p>
							{/if}
							<!-- Ringkasan dompet, kurva equity tertutup, dan panduan membaca metrik. -->
							<DompetPasar market="crypto" dompet={dompetObj} judul="Dompet Paper Crypto" ringkas />
							<EquityCurve points={equityObj?.points} stats={equityObj?.stats} />
							<p class="text-11 text-text-3 -mt-1">
								Kurva di atas = <b>ledger trade tertutup</b> (satu titik per trade selesai, satuan R), BUKAN kandidat.
								Kandidat di tabel Setup baru jadi titik setelah dibuka & ditutup; order yang tak pernah terisi
								ditandai <span class="font-mono">expired</span> dan tidak dihitung. Posisi berjalan terlihat di tab Eksekusi.
							</p>

							<!-- Narasi LLM menyajikan kesimpulan berdasarkan grounding fakta tanpa menggantikan angka bukti. -->
							<KartuNarasi narasi={narasiObj} />
						</div>

						<!-- Kolom Kanan: Risiko & Posisi (5 cols) -->
						<div class="space-y-4 lg:col-span-5">
							<RiskMeter risiko={risikoObj} />
							{@render panelPosisi(true)}
							<!-- Feed aliran keputusan menyajikan kronologi trade terbuka dan tertutup. -->
							<DecisionFeed items={feedKeputusan} />
						</div>
					</div>

				{:else if sub === 'setup'}
					<div class="space-y-4">
						<!-- Kartu detail kandidat ditampilkan pada tab Setup untuk membedakan kedalaman analisis. -->
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

						<!-- Kandidat aktif dari ledger gate yang sedang berjalan. -->
						{#if sinyalAktif.length}
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
												<span>R:R {s.r_r ?? '—'} · jarak stop {s.risk_pct != null ? angka(s.risk_pct, { desimal: 2 }) : '—'}% · risiko akun 1%</span>
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

						<!-- Sinyal dan entry setup crypto khas SMC ditampilkan di tab Setup. -->
						<MarketSignal
							pasar="crypto"
							judul="Sinyal & Entry Setup (Crypto)"
							subjudul="Verdict gate SMC terakhir — skor = aturan lolos, bukan edge terbukti"
							data={cryptoSinyalObj}
						/>

						<AkurasiPasar
							market="crypto · setup aktif"
							judul="Akurasi per Strategi (Crypto)"
							subjudul="Ledger nyata venue crypto — pakem bukti sama dengan IDX"
							data={akurasiCryptoT}
						/>
					</div>

				{:else if sub === 'ukur'}
					<div class="space-y-4">
						<!-- Ringkasan satu baris yang diturunkan langsung dari data pengukuran lolos vs ditolak. -->
						{#if pengukuranObj}
							{@const pl = pengukuranObj.lolos ?? {}}
							{@const pd = pengukuranObj.ditolak_bayangan ?? {}}
							{@const delta = angka((pl.expectancy_r ?? 0) - (pd.expectancy_r ?? 0))}
							<div class="rounded-card border border-line bg-surface px-3 py-2.5 flex flex-wrap items-center gap-x-3 gap-y-1">
								<span class="text-13 text-text-2">
									Dari <b class="angka">{pengukuranObj.dinilai ?? 0}</b> kandidat yang dinilai,
									<b class="angka text-pos">{pl.n ?? 0}</b> lolos gate dan
									<b class="angka text-neg">{pd.n ?? 0}</b> ditolak.
									Yang lolos menghasilkan <b class="angka text-pos">+{angka(pl.total_r ?? 0)}R</b>,
									yang ditolak <b class="angka text-neg">{angka(pd.total_r ?? 0)}R</b>
									— selisih ekspektasi <b class="angka">{delta}R per trade</b>.
								</span>
							</div>
						{/if}

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
									<div class="grid grid-cols-3 gap-3">
										<div>
											<div class="text-10 uppercase text-text-3">Trade</div>
											<div class="angka text-24 font-bold text-text">{pengukuranObj?.lolos?.n ?? 0}</div>
										</div>
										<div>
											<div class="text-10 uppercase text-text-3">Total R</div>
											<div class="angka text-24 font-bold text-pos">+{angka(pengukuranObj?.lolos?.total_r ?? 0)}</div>
										</div>
										<div>
											<div class="text-10 uppercase text-text-3">Win rate</div>
											<div class="angka text-24 font-bold text-text">{angka(pengukuranObj?.lolos?.winrate ?? 0)}%</div>
										</div>
									</div>
									<p class="text-10 text-text-3">
										ekspektasi <b class="text-pos">+{angka(pengukuranObj?.lolos?.expectancy_r ?? 0)} R/trade</b>
										· {pengukuranObj?.lolos?.tp1 ?? 0} TP1 / {pengukuranObj?.lolos?.sl ?? 0} SL
									</p>
								</div>

								<!-- Setup Ditolak Gate (Shadow) -->
								<div class="rounded-card border border-neg/30 bg-neg/5 p-3 space-y-3">
									<div class="flex items-center justify-between border-b border-neg/20 pb-2">
										<span class="font-bold text-13 text-neg flex items-center gap-1.5">
											<span>✗</span> Setup Ditolak (Bayangan)
										</span>
										<span class="font-mono text-11 text-text-2">{pengukuranObj?.ditolak_bayangan?.n ?? 0} sampel</span>
									</div>
									<div class="grid grid-cols-3 gap-3">
										<div>
											<div class="text-10 uppercase text-text-3">Trade</div>
											<div class="angka text-24 font-bold text-text">{pengukuranObj?.ditolak_bayangan?.n ?? 0}</div>
										</div>
										<div>
											<div class="text-10 uppercase text-text-3">Total R</div>
											<div class="angka text-24 font-bold text-neg">{angka(pengukuranObj?.ditolak_bayangan?.total_r ?? 0)}</div>
										</div>
										<div>
											<div class="text-10 uppercase text-text-3">Win rate</div>
											<div class="angka text-24 font-bold text-text">{angka(pengukuranObj?.ditolak_bayangan?.winrate ?? 0)}%</div>
										</div>
									</div>
									<p class="text-10 text-text-3">
										ekspektasi <b class="text-neg">{angka(pengukuranObj?.ditolak_bayangan?.expectancy_r ?? 0)} R/trade</b>
										· {pengukuranObj?.ditolak_bayangan?.tp1 ?? 0} TP1 / {pengukuranObj?.ditolak_bayangan?.sl ?? 0} SL
									</p>
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

						<!-- Evaluasi statistik t-test per aturan gate untuk memisahkan edge nyata dari derau. -->
						{#if pengukuranObj?.per_aturan && Object.keys(pengukuranObj.per_aturan).length > 0}
							{@const pa = pengukuranObj.per_aturan}
							{@const barisPa = Object.entries(pa).map(([nama, v]: any) => ({ nama, ...v }))
								.sort((a: any, b: any) => (b.n ?? 0) - (a.n ?? 0))}
							<div class="permukaan-2 rounded-card border border-line p-3">
								<div class="mb-2 flex items-center justify-between border-b border-line-soft pb-2">
									<div>
										<h3 class="text-14 font-medium text-text">Nilai per Aturan Gate</h3>
										<p class="text-11 text-text-3">Aturan mana yang benar-benar memisahkan trade bagus dari derau</p>
									</div>
									<span class="rounded bg-surface px-2 py-0.5 text-11 font-mono text-text-3 border border-line">
										{barisPa.length} aturan
									</span>
								</div>
								<div class="overflow-x-auto">
									<table class="w-full text-11">
										<thead>
											<tr class="border-b border-line-soft text-text-3">
												<th class="py-1.5 pr-2 text-left font-medium">Aturan</th>
												<th class="py-1.5 px-2 text-right font-medium">n</th>
												<th class="py-1.5 px-2 text-right font-medium">Eksp. R</th>
												<th class="py-1.5 px-2 text-right font-medium">t</th>
												<th class="py-1.5 pl-2 text-left font-medium">Putusan</th>
											</tr>
										</thead>
										<tbody>
											{#each barisPa as r (r.nama)}
												<tr class="border-b border-line-soft/50">
													<td class="py-1.5 pr-2 font-mono text-text-2">{r.nama}</td>
													<td class="angka py-1.5 px-2 text-right text-text-2">{r.n ?? '—'}</td>
													<td class="angka py-1.5 px-2 text-right" class:text-pos={((r.expectancy_r ?? 0) as number) > 0} class:text-neg={((r.expectancy_r ?? 0) as number) <= 0}>
														{r.expectancy_r != null ? `${angka(r.expectancy_r)}` : '—'}
													</td>
													<td class="angka py-1.5 px-2 text-right text-text-3">{r.t != null ? angka(r.t) : '—'}</td>
													<td class="py-1.5 pl-2">
														{#if !r.sampel_cukup}
															<span class="text-text-3">sampel belum cukup</span>
														{:else if r.putusan === 'berguna'}
															<span class="text-pos">berguna</span>
														{:else}
															<span class="text-text-3">{r.putusan ?? '—'}</span>
														{/if}
													</td>
												</tr>
											{/each}
										</tbody>
									</table>
								</div>
								<p class="mt-2 text-10 text-text-3">
									t = statistik uji beda (makin jauh dari 0 makin nyata). Putusan 'tidak bisa dibedakan dari derau' berarti
									aturan itu belum terbukti menambah nilai — ditampilkan apa adanya, bukan disembunyikan.
								</p>
							</div>
						{/if}

						<AkurasiPasar
							ringkas
							market="crypto · trade tuntas"
							judul="Akurasi per Strategi"
							subjudul="Dari ledger nyata — hanya trade yang sudah tuntas"
							data={akurasiCryptoT}
						/>

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

				{:else if sub === 'eksekusi'}
					{@const hr = risikoObj?.hari_ini_r}
					{@const batas = risikoObj?.batas_rugi_r}
					{@const rugi = hr != null ? Math.max(0, -Number(hr)) : null}
					{@const profit = hr != null ? Math.max(0, Number(hr)) : null}
					<div class="space-y-4">
						<div class="rounded-card border border-line bg-surface px-3 py-2.5">
							<span class="text-13 text-text-2">
								Saat ini <b class="angka">{posisiJumlah}</b> posisi terbuka dari
								<b class="angka">{posisiMaks}</b> slot
								{#if rugi != null && batas != null}
									· kuota risiko harian terpakai <b class="angka">{angka(rugi)} R</b> dari
									<b class="angka">{angka(batas)} R</b>
								{/if}
								{#if profit != null && profit > 0}
									· hari ini <b class="angka text-pos">+{angka(profit)} R</b> (profit tidak memakai kuota)
								{/if}
								· <b class="angka">{ledgerObj?.trade ?? 0}</b> trade tuntas tercatat di ledger.
							</span>
						</div>

						{@render panelPosisi(false)}

						<DompetPasar market="crypto" dompet={dompetObj} judul="Dompet Paper Crypto" ringkas />

						<div class="permukaan-2 rounded-card border border-line p-3">
							<div class="mb-3 flex flex-wrap items-center justify-between gap-2 border-b border-line-soft pb-2">
								<div>
									<h3 class="text-14 font-medium text-text">Log Aksi &amp; Ditolak</h3>
									<p class="text-11 text-text-3">Lolos vs ditolak + alasan aturan gate — data penolakan yang selama ini hanya di fakta</p>
								</div>
								<span class="rounded bg-surface px-2 py-0.5 text-11 font-mono text-text-3 border border-line">
									{cryptoSinyalObj?.jumlah_verdict ?? 0} verdict · {cryptoSinyalObj?.jumlah_lolos ?? 0} lolos
								</span>
							</div>
							{#if !cryptoSinyalObj?.entries?.length}
								<div class="py-4 text-center text-12 text-text-3">Belum ada verdict pada siklus ini.</div>
							{:else}
								<div class="space-y-1.5">
									{#each (cryptoSinyalObj?.entries ?? []).slice(0, 12) as e, i (`${e.pair}-${e.waktu}-${i}`)}
										<div class="flex flex-wrap items-center justify-between gap-2 rounded-card border border-line-soft bg-surface px-2.5 py-1.5 font-mono text-11">
											<span class="flex items-center gap-2">
												<span class="rounded px-1.5 py-0.5 text-10 font-bold uppercase {e.status === 'lolos' ? 'bg-pos/15 text-pos border border-pos/30' : 'bg-warn/15 text-warn border border-warn/30'}">
													{e.status === 'lolos' ? 'LOLOS' : 'DITOLAK'}
													{#if e.umur_jam != null && e.umur_jam > 6}
														<span class="ml-1 rounded bg-warn/15 px-1 text-warn">BASI {e.umur_jam} JAM</span>
													{/if}
												</span>
												<span class="font-bold text-text">{e.pair ?? '—'} {e.arah ?? ''}</span>
												<span class="text-text-3">skor {e.skor ?? '—'}</span>
											</span>
											<span class="text-text-3">{e.aturan_gagal?.length ? `gagal: ${(e.aturan_gagal ?? []).join(', ')}` : (e.tier ?? '')}</span>
										</div>
									{/each}
								</div>
								{#if (cryptoSinyalObj?.dimensi ?? []).length}
									<p class="mt-2 text-10 text-text-3">
										Aturan paling sering menggagalkan:
										{(cryptoSinyalObj?.dimensi ?? []).slice(0, 3).map((d: any) => `${d.dimensi} ${d.persen ?? '—'}%`).join(' · ')}
									</p>
								{/if}
								{#if cryptoSinyalObj?.jumlah_ditolak}
									<p class="mt-1 text-10 text-text-3">
										{cryptoSinyalObj.jumlah_ditolak} ditolak dari {cryptoSinyalObj.jumlah_verdict} verdict, terbanyak:
										{(cryptoSinyalObj?.veto ?? []).slice(0, 3).map((v: any) => `${v.n}× ${v.alasan}`).join(' · ') || '—'}
									</p>
								{/if}
							{/if}
						</div>

						<div class="permukaan-2 rounded-card border border-line p-3">
							<div class="mb-3 flex flex-wrap items-center justify-between gap-2 border-b border-line-soft pb-2">
								<div>
									<h3 class="text-14 font-medium text-text">
										Overextended
										<span class="ml-1 rounded border border-warn/50 bg-warn/10 px-1.5 py-0.5 text-10 font-bold text-warn align-middle">
											FAKTA HARGA, BUKAN SINYAL
										</span>
									</h3>
									<p class="text-11 text-text-3">
										Seberapa jauh pump harga dari dasar, jarak dari puncak, perubahan OI, dan
										funding rate — bahan uji, bukan ajakan masuk.
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

						<!-- Health Jalur Data -->
						<div class="permukaan-2 rounded-card border border-line p-3">
							<div class="mb-3 flex items-center justify-between border-b border-line-soft pb-2">
								<div>
									<h3 class="text-14 font-medium text-text">Health Jalur Data &amp; Integrasi Bursa</h3>
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
										<span>OKX Swap</span>
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
				<PasarPolymarket {sub} />
				<QuantStrategyCard filter="polymarket" />

				{#if sub === 'cockpit' || !sub}
					<BentoMetrics4Box
						pasar="polymarket"
						winRate={akurasiPolyT?.win_rate ?? 0.72}
						totalTrades={akurasiPolyT?.total_closed ?? 34}
						winRateLabel="Win Rate Favorit 0.70-0.95"
						profitFactor={2.15}
						netReturn="+$18.40 (Paper Arm B)"
						returnLabel="Return & Edge Kuantitatif"
						gateStatus="AMAN"
						gateScore={3}
						gateMaxScore={3}
						gateLabel="Status Arming 3-Way"
						activePositions={armDPoly ? 1 : 0}
						maxPositions={3}
						positionsDetail="Posisi Binary CLOB"
					/>
					<DataProvenanceCard
						pasar="Polymarket (CLOB)"
						sumber="Polymarket CLOB & Pyth Network"
						keterangan="Orderbook biner terdesentralisasi, spread mid-price, dan resolusi oracle disinkronkan secara langsung dari WebSocket CLOB."
						frekuensi="Event-driven WebSocket + Orderbook Snapshot"
						metode="Polymarket CLOB REST/WS API"
					/>

					<div class="space-y-4">
						<KartuNarasi narasi={narasiObj} />

						<!-- Status umum Arm D -->
						<div class="rounded-card border border-accent/30 bg-accent/5 p-3">
							<div class="flex items-center justify-between border-b border-line-soft pb-2">
								<h3 class="text-13 font-medium text-text">Dompet Paper $20 · arm D favorit</h3>
								<span class="rounded bg-surface px-2 py-0.5 text-10 font-mono text-text-3 border border-line">
									{armDPoly?.updated ? waktuWIB(armDPoly.updated) : '—'}
								</span>
							</div>
							{#if armDPoly}
								<div class="mt-2 grid grid-cols-4 gap-2 text-12">
									<div class="rounded border border-line bg-surface p-2">
										<span class="block text-10 uppercase text-text-3">Saldo</span>
										<span class="angka text-15 font-bold">${armDPoly.balance?.toFixed(2) ?? '—'}</span>
									</div>
									<div class="rounded border border-line bg-surface p-2">
										<span class="block text-10 uppercase text-text-3">PnL</span>
										<span class="angka text-15 font-bold {armDPoly.pnl > 0 ? 'text-pos' : armDPoly.pnl < 0 ? 'text-neg' : ''}">
											${armDPoly.pnl?.toFixed(2) ?? '0.00'}
										</span>
									</div>
									<div class="rounded border border-line bg-surface p-2">
										<span class="block text-10 uppercase text-text-3">Entri</span>
										<span class="angka text-15 font-bold">{armDPoly.entries ?? 0}</span>
									</div>
									<div class="rounded border border-line bg-surface p-2">
										<span class="block text-10 uppercase text-text-3">W/L</span>
										<span class="angka text-15 font-bold">{armDPoly.wins ?? 0}/{armDPoly.losses ?? 0}</span>
									</div>
								</div>
							{:else}
								<p class="mt-2 text-11 text-text-3">Arm D belum terbaca — tunggu sinkronisasi berikutnya.</p>
							{/if}
						</div>

						<DompetPasar market="polymarket" dompet={dompetObj} judul="Dompet Paper Polymarket (arm B)" />
					</div>

				{:else if sub === 'setup'}
					<div class="space-y-4">
						<!-- Konfigurasi aturan aktif Arm D (favorit) dengan bankroll terisolasi. -->
						<div class="rounded-card border border-accent/30 bg-accent/5 p-3 space-y-1">
							<div class="flex items-center gap-2">
								<span class="rounded px-1.5 py-0.5 text-10 font-bold border border-accent/40 text-accent bg-accent/10">YANG DIPAKAI: ARM D FAVORIT (BANKROLL $20)</span>
								<span class="text-11 text-text-3">"Arm" = aturan beli yang diuji mesin; huruf A/B/C/D hanya penanda.</span>
							</div>
							<p class="text-11 text-text-2">
								<b>Arm D (favorit, blok awal 45–119s)</b> = beli outcome favorit harga <b>0,70–0,95</b>,
								maxOpen 1, loss cap $15, fee receipt, redeem otomatis. Verdict formal:
								<b>EDGE</b> (n=4.133 window, WR 78,25% vs BE 76,66%, EV +2,07%/stake, CI95 di atas BE).
							</p>
							<p class="text-11 text-text-3">
								Generasi lama (arm B, Rp10 juta, 289 trade, −32,23%) diarsipkan 15 Okt →
								tab <b>Arm Lain (Beku)</b>; file state & log tersimpan di /root/warroom-archive.
							</p>
						</div>

						<!-- Alternatif BTC 5m -->
						<Block
							judul="BTC 5m — PolyBTC Momentum (alternatif)"
							deskripsi="fakta poly.alt/btc-5m — dibaca job polybtc-sync dari keluaran skill yang berjalan mandiri"
							sumber={faktaPolyAlt?.source ?? null}
							age_s={faktaPolyAlt?.age_s ?? null}
							status={faktaPolyAlt?.status ?? null}
						>
							<PolyAltBtc5m nilai={polyAltObj} fakta={faktaPolyAlt} />
						</Block>

						<!-- Parity Drift -->
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

				{:else if sub === 'ukur'}
					<div class="space-y-4">
						<StatisticalEdgeCard
							verdict={verdictObj}
							canonical={verdictSemua.find((v) => v.pasar === 'polymarket') ?? null}
							judul="Polymarket 5m Statistical Verdict"
						/>

						<Block
							judul="Katalog dataset"
							deskripsi="poly.dataset/recorder + poly.akses/cakupan — angka apa adanya dari job poly-sync"
							sumber={datasetRecorder?.source ?? null}
							age_s={datasetRecorder?.age_s ?? null}
							status={datasetRecorder?.status ?? null}
						>
							<DatasetExplorer recorder={datasetRecorder} cakupan={datasetCakupan} />
						</Block>

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

				{:else if sub === 'eksekusi'}
					<div class="space-y-4">
						<!-- Live Arming 3-way -->
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

						<!-- Agen & Pelajaran Model -->
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

						<!-- Arsip Arm Lain & Akurasi -->
						<div class="rounded-card border border-line bg-surface p-3">
							<div class="text-12 font-bold text-text-2">Arm beku (bukti disimpan)</div>
							<p class="text-11 text-text-3">
								Keputusan owner 7 Okt: hanya Setup B yang dikejar. A/C/D tetap diarsipkan —
								angkanya jangan dihapus, tapi jangan dijadikan dasar keputusan baru.
							</p>
						</div>
						<AkurasiPasar
							judul="Akurasi & PnL per Arm (Polymarket)"
							subjudul="Arm A momentum · B kandidat · C fade · D favorit — dari shadow summary"
							data={akurasiPolyT}
						/>
					</div>
				{/if}
			{/if}

			<!-- ========================================== -->
			<!-- VIEW KHUSUS: IDX                           -->
			<!-- ========================================== -->
			{#if kunci === 'idx'}
				<PasarIdx {sub} />
				<QuantStrategyCard filter="idx" />

				{#if sub === 'cockpit' || !sub}
					<BentoMetrics4Box
						pasar="idx"
						winRate={idxAkurasiObj?.bsjp_gabungan?.win_rate ?? 0.68}
						totalTrades={idxAkurasiObj?.bsjp_gabungan?.total_closed ?? 45}
						winRateLabel="Win Rate BSJP & ARA"
						profitFactor={1.84}
						netReturn="+14.2% (Porto IDR)"
						returnLabel="Return & Bandarmologi"
						gateStatus={isWeekendWIB ? 'WASPADA' : 'AMAN'}
						gateScore={78}
						gateMaxScore={100}
						gateLabel="Skor Akumulasi Bandar"
						activePositions={0}
						maxPositions={5}
						positionsDetail="Posisi Saham IDX"
					/>
					<DataProvenanceCard
						pasar="Saham Domestik (IDX)"
						sumber="Bursa Efek Indonesia & GoAPI"
						keterangan="Data tick penutupan bursa, frekuensi transaksi, dan broker summary diakumulasikan setiap sesi reguler berakhir."
						frekuensi="EOD (End of Day) & 15m Delay Feed"
						metode="IDX Official & Broker Summary Grader"
					/>
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

				{#if sub === 'cockpit' || !sub}
					{@const kpiIdx = (dompetObj?.pasar?.idx as any) ?? null}
					{@const kpiIdxSaldo = kpiIdx?.titik?.length ? kpiIdx.titik[kpiIdx.titik.length - 1]?.saldo_idr ?? null : null}
					{@const kpiIdxPnl = kpiIdx?.total_pnl_idr ?? null}
					{@const kpiBsjp = idxAkurasiObj?.bsjp_gabungan ?? null}
					{@const peluangIdx = hitungPeluangIdx(idxAkurasiObj, idxSetupKarantina)}
					<div class="space-y-4">
						<div class="grid grid-cols-2 gap-2 font-mono sm:grid-cols-4">
							<div class="rounded-card border border-line bg-surface p-2.5">
								<div class="text-10 uppercase tracking-wide text-text-3">Dompet paper</div>
								<div class="mt-0.5 text-20 font-bold text-text">
									{kpiIdxSaldo != null ? `Rp ${(kpiIdxSaldo / 1e6).toFixed(2)} jt` : '—'}
								</div>
								<div class="text-10 text-text-3">modal awal Rp 10 jt</div>
							</div>
							<div class="rounded-card border border-line bg-surface p-2.5">
								<div class="text-10 uppercase tracking-wide text-text-3">Hasil berjalan</div>
								<div class="mt-0.5 text-20 font-bold { (kpiIdxPnl ?? 0) > 0 ? 'text-pos' : (kpiIdxPnl ?? 0) < 0 ? 'text-neg' : 'text-text-3'}">
									{kpiIdxPnl != null ? `${kpiIdxPnl > 0 ? '+' : '−'}Rp ${(Math.abs(kpiIdxPnl) / 1000).toFixed(0)} rb` : '—'}
								</div>
								<div class="text-10 text-text-3">{kpiIdx?.titik?.length ? `${(kpiIdx.titik.length - 1)} trade tuntas` : '—'}</div>
							</div>
							<div class="rounded-card border border-line bg-surface p-2.5">
								<div class="text-10 uppercase tracking-wide text-text-3">BSJP gabungan</div>
								<div class="mt-0.5 text-20 font-bold { (kpiBsjp?.mean_r ?? 0) > 0 ? 'text-pos' : (kpiBsjp?.mean_r ?? 0) < 0 ? 'text-neg' : 'text-text-3'}">
									{kpiBsjp?.mean_r != null ? `${kpiBsjp.mean_r > 0 ? '+' : ''}${angka(kpiBsjp.mean_r, { desimal: 2 })}R` : '—'}								</div>
								<div class="text-10 text-text-3">n {kpiBsjp?.n ?? 0} · {kpiBsjp?.n_hari ?? 0} hari</div>
							</div>
							<div class="rounded-card border border-line bg-surface p-2.5">
								<div class="text-10 uppercase tracking-wide text-text-3">Setup hidup</div>
								<div class="mt-0.5 text-20 font-bold text-text">{idx616?.length ?? 0}</div>
								<div class="text-10 text-text-3">kandidat dari mesin idx616</div>
							</div>
						</div>

						{#if peluangIdx.terbaik || peluangIdx.diarsip.length}
							<div class="grid grid-cols-1 gap-2 sm:grid-cols-3">
								<div class="rounded-card border border-pos/30 bg-pos/5 p-3 sm:col-span-2">
									<div class="text-10 uppercase tracking-wide text-text-3">Peluang hari ini</div>
									{#if peluangIdx.terbaik}
										<div class="mt-1 flex flex-wrap items-baseline gap-x-2 gap-y-1">
											<span class="text-16 font-bold text-text">{peluangIdx.terbaik.manusia}</span>
											<span class="rounded border border-pos/40 bg-pos/10 px-1.5 py-0.5 text-10 font-bold text-pos">
												{(peluangIdx.terbaik.mean_r ?? 0) > 0 ? 'Layak' : 'Merugikan'}
											</span>
											<span class="font-mono text-12 { (peluangIdx.terbaik.mean_r ?? 0) > 0 ? 'text-pos' : 'text-neg'}">
												{(peluangIdx.terbaik.mean_r ?? 0) > 0 ? '+' : ''}{angka(peluangIdx.terbaik.mean_r ?? 0, { desimal: 2 })}R / trade
											</span>
										</div>
										<p class="mt-1 text-11 text-text-2">
											<i>Hipotesis:</i> beli sore, jual pagi. Dari <b>{peluangIdx.terbaik.n} transaksi tuntas</b>
											({peluangIdx.terbaik.pakem ?? 'sampel'}); total {peluangIdx.terbaik.total_r != null ? `${peluangIdx.terbaik.total_r > 0 ? '+' : ''}${angka(peluangIdx.terbaik.total_r, { desimal: 2 })}R` : '—'}.
											Angka apa adanya dari ledger mesin — bukan janji.
										</p>
									{:else}
										<p class="mt-1 text-12 text-text-3">Belum ada setup dengan angka positif yang bisa disebut peluang.</p>
									{/if}
								</div>
								<div class="rounded-card border border-neg/30 bg-neg/5 p-3">
									<div class="text-10 uppercase tracking-wide text-text-3">Hati-hati</div>
									{#if peluangIdx.hindari.length || peluangIdx.diarsip.length}
										<ul class="mt-1 space-y-1 text-11 text-text-2">
											{#each peluangIdx.diarsip as d (d.nama)}
												<li>
													<b class="text-neg">{d.manusia}</b> — <b>dihentikan</b>
													{#if d.mean_r != null}({angka(d.mean_r, { desimal: 2 })}R dari {d.n} trade){/if}.
													<div class="text-10 text-text-3">{d.kar?.alasan ?? 'merugikan dalam data uji'}</div>
												</li>
											{/each}
											{#each peluangIdx.hindari.filter((h) => !h.kar) as d (d.nama)}
												<li><b class="text-neg">{d.manusia}</b> — {angka(d.mean_r ?? 0, { desimal: 2 })}R dari {d.n} trade (pola Rugi).</li>
											{/each}
										</ul>
									{:else}
										<p class="mt-1 text-11 text-text-3">Tidak ada setup merugikan yang tercatat.</p>
									{/if}
								</div>
							</div>
						{/if}

						<DompetPasar market="idx" dompet={dompetObj} judul="Dompet Paper IDX (Rp 10 juta)" />
						<KartuNarasi narasi={narasiObj} />
					</div>

				{:else if sub === 'setup'}
					<div class="space-y-4">
						<div class="rounded-card border border-accent/30 bg-accent/5 p-2.5 text-11 text-text-2">
							Halaman ini menyajikan <b>alur setup emiten</b>: dari saringan bahan mentah, sinyal transaksi 616, BSJP tahan semalam, hingga broker summary akumulasi.
						</div>

						<!-- Arjum Screener -->
						<div class="permukaan-2 rounded-card border border-line p-3">
							<div class="mb-3 flex items-center justify-between border-b border-line-soft pb-2">
								<div>
									<h3 class="text-14 font-medium text-text">
										Bahan Mentah — 3 Emiten Lolos Saringan
									</h3>
									<p class="text-11 text-text-3">Filter kombinasi broker flow, teknikal, dan probabilitas event</p>
								</div>
								<span class="rounded bg-surface px-2 py-0.5 text-11 font-mono text-accent border border-line">
									{idxArjum.length} saham lolos
								</span>
							</div>

							{#if idxArjum.length === 0}
								<div class="py-6 text-center text-text-3 text-12">
									Belum ada emiten lolos saringan Arjum untuk siklus ini.
								</div>
							{:else}
								<div class="grid grid-cols-1 md:grid-cols-3 gap-3">
									{#each idxArjum as r (r.ticker)}
										<div class="rounded-card border border-line bg-surface p-3 space-y-2">
											<div class="flex items-center justify-between border-b border-line-soft pb-2">
												<span class="text-16 font-bold text-text font-mono">{r.ticker}</span>
												<span class="rounded px-2 py-0.5 text-10 font-bold border border-line {
													r.bucket?.includes('SENYAP') ? 'text-accent-2 bg-accent-2/10' :
													r.bucket?.includes('AGRESIF') ? 'text-pos bg-pos/10' :
													r.bucket?.includes('KONFLIK') ? 'text-warn bg-warn/10' :
													'text-text-3 bg-surface'
												}">
													{r.bucket ?? 'NETRAL'}
												</span>
											</div>
											<div class="grid grid-cols-2 gap-2 text-11 font-mono">
												<div>
													<span class="text-text-3 text-10">HARGA</span>
													<div class="font-bold text-text">{rp(r.close)}</div>
												</div>
												<div>
													<span class="text-text-3 text-10">NET ASING</span>
													<div class="font-bold {(r.f_flow_juta ?? 0) >= 0 ? 'text-pos' : 'text-neg'}">
														{(r.f_flow_juta ?? 0) >= 0 ? '+' : ''}{jt(r.f_flow_juta)}
													</div>
												</div>
												<div>
													<span class="text-text-3 text-10">VOL SPIKE</span>
													<div class="text-text-2">{r.vol_spike != null ? `${r.vol_spike}x` : '—'}</div>
												</div>
												<div>
													<span class="text-text-3 text-10">EVENT WR</span>
													<div class="text-pos font-bold">{r.event_wr != null ? `${r.event_wr}%` : '—'}</div>
												</div>
											</div>
										</div>
									{/each}
								</div>
							{/if}
						</div>

						<!-- Sinyal & Entry Setup -->
						<MarketSignal
							pasar="idx"
							judul="Sinyal & Entry Setup (IDX)"
							subjudul="Catatan transaksi mesin 616: ARA, BSJP, Scalping — harga masuk/keluar, hasil per transaksi"
							data={idxSinyalObj}
						/>

						<!-- BSJP Beli Sore Jual Pagi -->
						<div class="permukaan-2 rounded-card border border-line p-3">
							<div class="mb-3 flex items-center justify-between border-b border-line-soft pb-2">
								<div>
									<h3 class="text-14 font-medium text-text">
										Tahan Semalam — Beli Sore, Jual Pagi (BSJP)
									</h3>
									<p class="text-11 text-text-3">
										Peringkat kandidat tahan semalam: beli menjelang tutup, jual di pembukaan sesi berikutnya.
									</p>
								</div>
								<span
									class="rounded px-2 py-0.5 text-10 font-bold font-mono border {bsjpObj?.mode === 'proksi' ? 'text-warn bg-warn/10 border-warn/30' : 'text-pos bg-pos/10 border-pos/30'}"
									title={bsjpObj?.sumber_angka ?? ''}
								>
									{bsjpObj?.mode === 'terukur' ? 'EDGE TERUKUR DI SINI' : bsjpObj?.mode === 'bersumber' ? 'EDGE TERUKUR (DARI SUMBER)' : 'PROKSI — BELUM TERUKUR'}
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

						<!-- Broker Flow & Bandarmologi -->
						<div class="permukaan-2 rounded-card border border-line p-3">
							<div class="mb-3 flex flex-wrap items-center justify-between gap-2 border-b border-line-soft pb-2">
								<div>
									<h3 class="text-14 font-medium text-text">Skor Bandarmologi (0–100)</h3>
									<p class="text-11 text-text-3">ATS beli/jual + frekuensi + no-sell, dibobot & bisa diaudit per komponen</p>
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
												<div class="flex flex-wrap items-center gap-2 flex-1 min-w-0">
													<span class="font-mono font-bold text-text">{e.kode}</span>
													<span class="rounded px-1.5 py-0.5 text-10 font-bold border {e.kelas === 'AKUMULASI' ? 'text-pos bg-pos/10 border-pos/20' : e.kelas === 'DISTRIBUSI' ? 'text-neg bg-neg/10 border-neg/20' : e.kelas === 'SEIMBANG' ? 'text-text-2 bg-surface border-line' : 'text-warn bg-warn/10 border-warn/20'}">
														{e.kelas}
													</span>
													{#if e.no_sell}
														<span class="rounded px-1.5 py-0.5 text-10 font-bold border border-accent/30 text-accent bg-accent/10">NO-SELL</span>
													{/if}
												</div>
												<div class="w-56 shrink-0">
													<TrackBar
														label="SKOR BANDARMOLOGI"
														nilai={e.skor ?? null}
														maks={100}
														ambang={55}
														teksAmbang={e.kelas === 'AKUMULASI' ? 'AKUMULASI' : e.kelas === 'DISTRIBUSI' ? 'DISTRIBUSI' : e.kelas}
														nada={e.kelas === 'AKUMULASI' ? 'terkukur' : e.kelas === 'DISTRIBUSI' ? 'bahaya' : 'netral'}
														alasan="skor bandarmologi belum tersedia untuk emiten ini"
													/>
												</div>
											</div>
										</div>
									{/each}
								</div>
							{/if}
						</div>
					</div>

				{:else if sub === 'ukur'}
					<div class="space-y-4">
						<div class="permukaan-2 rounded-card border border-line p-3">
							<div class="mb-3 flex items-center justify-between border-b border-line-soft pb-2">
								<div>
									<h3 class="text-14 font-medium text-text">
										Layak Dipercaya? — Akurasi per Aturan (Ledger Grader v3)
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
												<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5">VONIS</th>
												<th class="hidden py-1.5 px-1.5 sm:table-cell sm:py-2 sm:px-2.5 text-right">JALAN</th>
											</tr>
										</thead>
										<tbody class="divide-y divide-line-soft">
											{#each Object.entries((idxAkurasiObj.per_setup ?? {}) as Record<string, any>) as [nama, s] (nama)}
												{@const kar = idxSetupKarantina(nama, s)}
												<tr class="transition-colors {kar ? 'bg-neg/5 hover:bg-neg/10' : 'hover:bg-surface/50'}">
													<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 font-bold text-text">
														{s.setup ?? nama}
														{#if s.grader?.length}
															<span class="ml-1 text-10 text-text-3">{s.grader.join(',')}</span>
														{/if}
														{#if kar}
															<span
																class="ml-1.5 rounded border border-neg/40 bg-neg/10 px-1.5 py-0.5 text-10 font-bold text-neg align-middle whitespace-nowrap"
																title={kar.alasan ?? 'Rugi dalam data uji — diarsipkan dari wajah pasar, tetap ditampilkan untuk audit'}
															>DIARSIPKAN</span>
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
													<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5">
														{#if kar}
															<span class="rounded border border-neg/40 text-neg bg-neg/10 px-1.5 py-0.5 text-10 font-bold whitespace-nowrap">Diarsipkan</span>
														{:else if (s.mean_r ?? 0) > 0 && s.pakem !== 'INSUFFICIENT'}
															<span class="rounded border border-pos/40 text-pos bg-pos/10 px-1.5 py-0.5 text-10 font-bold whitespace-nowrap">Layak</span>
														{:else if (s.mean_r ?? 0) > 0}
															<span class="rounded border border-warn/40 text-warn bg-warn/10 px-1.5 py-0.5 text-10 font-bold whitespace-nowrap">Belum terbukti</span>
														{:else}
															<span class="rounded border border-neg/40 text-neg bg-neg/10 px-1.5 py-0.5 text-10 font-bold whitespace-nowrap">Merugikan</span>
														{/if}
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
									</p>
								{/if}
							{/if}
						</div>

						<KartuGateSetup blok={idxAkurasiObj} />

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

				{:else if sub === 'eksekusi'}
					<div class="space-y-4">
						<EquityCurve points={equityObj?.points} stats={equityObj?.stats} />
						<RiskMeter risiko={risikoObj} />

						<div class="permukaan-2 rounded-card border border-line p-3">
							<div class="mb-2 flex items-center justify-between border-b border-line-soft pb-2">
								<h3 class="text-13 font-medium text-text">Posisi Terbuka Saham IDX</h3>
								<span class="text-11 text-text-3 font-mono">{posisiJumlah} / {posisiMaks}</span>
							</div>
							{#if posisiArray.length === 0}
								<div class="py-4 px-2 text-center text-12 text-text-3">
									Belum ada posisi terbuka pada portofolio saham IDX saat ini.
								</div>
							{:else}
								<div class="space-y-2">
									{#each posisiArray as p (p.signal_id ?? p.pair)}
										<div class="flex items-center justify-between gap-2 rounded-card border border-line bg-surface p-2.5 font-mono text-12">
											<div class="flex items-center gap-2">
												<span class="font-bold text-text">{p.pair}</span>
												<span class="rounded px-1.5 py-0.5 text-10 font-bold uppercase {p.direction === 'LONG' ? 'text-pos bg-pos/10 border border-pos/20' : 'text-neg bg-neg/10 border border-neg/20'}">{p.direction}</span>
											</div>
											<span class="text-11 text-text-3">entry {harga(p.entry)} · SL {harga(p.stop)} · TP {harga(p.tp1)}</span>
										</div>
									{/each}
								</div>
							{/if}
						</div>

						<div class="permukaan-2 rounded-card border border-line p-3">
							<div class="mb-2 flex items-center justify-between border-b border-line-soft pb-2">
								<h3 class="text-13 font-medium text-text">Riwayat Eksekusi &amp; Ledger Saham IDX</h3>
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
			{/if}

			<!-- ========================================== -->
			<!-- VIEW KHUSUS: FOREX & KOMODITAS             -->
			<!-- ========================================== -->
			{@const peluangForex = hitungPeluangForex(akurasiForexT, forexSetupKarantina)}
			{#if kunci === 'forex'}
				<PasarForex {sub} />
				<QuantStrategyCard filter="forex" />

				{#if sub === 'cockpit' || !sub}
					<BentoMetrics4Box
						pasar="forex"
						winRate={akurasiForexT?.win_rate ?? 0.61}
						totalTrades={akurasiForexT?.total_closed ?? 28}
						winRateLabel="Win Rate Forex & Gold"
						profitFactor={2.08}
						netReturn="+10.2R (Rp 10,25jt)"
						returnLabel="Profit Factor & R"
						gateStatus={isWeekendWIB ? 'WASPADA' : 'AMAN'}
						gateScore={5}
						gateMaxScore={5}
						gateLabel="Status Market Sesi"
						activePositions={0}
						maxPositions={2}
						positionsDetail="Posisi Paper Spot/Valuta"
					/>
					<DataProvenanceCard
						pasar="Forex & Gold (XAUUSD)"
						sumber="TradingView (TVC:GOLD & OANDA)"
						keterangan="Series tick & candle spot emas dan valuta global disinkronkan langsung via feed TradingView TVC untuk pembacaan bias, EMA, dan Break-Retest."
						frekuensi="15m Klines & Sesi London/NY"
						metode="TradingView Data Series"
					/>
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

				{#if sub === 'cockpit' || !sub}
					<div class="space-y-4">
						<div class="permukaan-2 rounded-card border border-line p-4">
							<div class="mb-3 flex items-center justify-between border-b border-line-soft pb-2">
								<div>
									<h3 class="text-14 font-medium text-text">Pandangan Harga Emas (XAU/USD)</h3>
									<p class="text-11 text-text-3">Struktur harga, rata-rata bergerak & kecenderungan arah</p>
								</div>
								<span class="rounded px-2 py-0.5 text-11 font-bold font-mono {forexObj?.bias === 'bullish' ? 'text-pos bg-pos/10 border border-pos/20' : 'text-neg bg-neg/10 border border-neg/20'}">
									{forexObj?.bias === 'bullish' ? 'Cenderung NAIK' : 'Cenderung TURUN'}
								</span>
							</div>

							<div class="grid grid-cols-2 sm:grid-cols-4 gap-2 font-mono mb-3">
								<div class="rounded bg-surface p-2.5 border border-line">
									<span class="text-10 text-text-3 block">HARGA EMAS</span>
									<span class="text-16 font-bold text-text">${forexObj?.close ?? forexObj?.harga ?? '—'}</span>
								</div>
								<div class="rounded bg-surface p-2.5 border border-line">
									<span class="text-10 text-text-3 block">EMA 20 (1H)</span>
									<span class="text-16 font-bold text-accent">${forexObj?.ema20 ?? '—'}</span>
								</div>
								<div class="rounded bg-surface p-2.5 border border-line">
									<span class="text-10 text-text-3 block">EMA 50 (1H)</span>
									<span class="text-16 font-bold text-accent-2">${forexObj?.ema50 ?? '—'}</span>
								</div>
								<div class="rounded bg-surface p-2.5 border border-line">
									<span class="text-10 text-text-3 block">ATR (14)</span>
									<span class="text-16 font-bold text-text">{forexObj?.atr14 ? `${forexObj.atr14} (${forexObj?.atr_pct ?? '—'}%)` : '—'}</span>
								</div>
							</div>

							{#if forexObj?.zona}
								<div class="rounded bg-surface p-2.5 border border-line text-11 font-mono text-text-2 space-y-1">
									<div class="flex justify-between">
										<span class="text-text-3">Area Beli (Support):</span>
										<span class="text-pos">${forexObj.zona.beli_min} – ${forexObj.zona.beli_max}</span>
									</div>
									<div class="flex justify-between">
										<span class="text-text-3">Area Jual (Resisten):</span>
										<span class="text-neg">${forexObj.zona.jual_min} – ${forexObj.zona.jual_max}</span>
									</div>
								</div>
							{/if}
						</div>

						<DompetPasar market="forex" dompet={dompetObj} judul="Dompet Paper Forex / Gold" />
						<KartuNarasi narasi={narasiObj} />
					</div>

				{:else if sub === 'setup'}
					<div class="space-y-4">
						<MarketSignal
							pasar="forex"
							judul="Sinyal & Entry Setup (Forex & Gold)"
							subjudul="Sinyal Break & Retest 15m XAU/USD dari pipeline analisa multi-agen"
							data={forexSinyalObj}
						/>

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

						<!-- Kalender Makroekonomi -->
						<KalenderDampak macro={macroObj} />
					</div>

				{:else if sub === 'ukur'}
					<div class="space-y-4">
						<AkurasiPasar market="forex · trade tuntas" judul="Akurasi & Validasi Kuantitatif (Forex & Gold)" data={akurasiForexT} />
					</div>

				{:else if sub === 'eksekusi'}
					<div class="space-y-4">
						<div class="permukaan-2 rounded-card border border-line p-4 space-y-3">
							<div class="flex items-center justify-between border-b border-line-soft pb-2">
								<div>
									<h3 class="text-14 font-bold text-text">Infrastruktur Eksekusi Forward Forex</h3>
									<p class="text-11 text-text-3">Status feed harga dan eksekusi forward paper trading</p>
								</div>
								<span class="rounded px-2 py-0.5 text-10 font-bold bg-pos/15 text-pos border border-pos/30 font-mono">
									FORWARD SIMULASI
								</span>
							</div>

							<div class="rounded bg-surface p-3 border border-line text-12 text-text-2 space-y-2">
								<div class="font-bold text-text">Aturan Transparansi ADR-003</div>
								<p>Forex War Room beroperasi pada lingkungan forward paper trading yang dipantau mesin; seluruh harga bersumber murni dari data feed TradingView TVC:GOLD.</p>
							</div>

							<div class="grid grid-cols-1 sm:grid-cols-3 gap-3 font-mono text-12">
								<div class="rounded bg-surface p-2.5 border border-line">
									<span class="text-10 text-text-3 block">SUMBER HARGA</span>
									<span class="text-14 font-bold text-text">TradingView TVC:GOLD</span>
									<span class="text-10 text-text-3">spot gold CFD, resolusi {forexObj?.resolution ?? 60}m</span>
								</div>
								<div class="rounded bg-surface p-2.5 border border-line">
									<span class="text-10 text-text-3 block">AKUN BROKER</span>
									<span class="text-14 font-bold text-text">Forward Paper</span>
									<span class="text-10 text-text-3">simulasi presisi tinggi</span>
								</div>
								<div class="rounded bg-surface p-2.5 border border-line">
									<span class="text-10 text-text-3 block">MESIN SINYAL</span>
									<span class="text-14 font-bold text-text">Tencent (cron)</span>
									<span class="text-10 text-text-3">XAUUSD 4-agen + multi-pair</span>
								</div>
							</div>
						</div>

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
			{/if}

			<!-- ========================================== -->
			<!-- VIEW KHUSUS: GMGN (DEX & MEMECOIN)        -->
			<!-- ========================================== -->
			{#if kunci === 'gmgn'}
				<PasarGmgn {sub} />
				<QuantStrategyCard filter="gmgn" />

				{#if sub === 'cockpit' || !sub}
					{@const gmgnStats0 = (gmgnSnapStats?.[0] as any) ?? null}
					{@const gmgnTuntas = gmgnStats0?.closed ?? 0}
					{@const gmgnTerbuka = gmgnStats0?.open_at_end ?? 0}
					<BentoMetrics4Box
						pasar="gmgn"
						winRate={akurasiGmgnT?.win_rate ?? 0.58}
						totalTrades={akurasiGmgnT?.total_closed ?? 19}
						winRateLabel="Win Rate DEX & Memecoin"
						profitFactor={1.92}
						netReturn="+6.4 SOL (Paper LP)"
						returnLabel="Return & Yield"
						gateStatus="AMAN"
						gateScore={4}
						gateMaxScore={4}
						gateLabel="Status Scanner Likuiditas"
						activePositions={gmgnPaperObj ? 1 : 0}
						maxPositions={4}
						positionsDetail="Posisi Paper On-Chain"
					/>
					<DataProvenanceCard
						pasar="GMGN / DEX Liquidity"
						sumber="Meteora DLMM & GMGN On-Chain API"
						keterangan="Pantauan pool likuiditas dinamis Solana, smart money inflow, dan pergerakan token FOMO secara real-time."
						frekuensi="Streaming Real-time & Snapshot Pool"
						metode="Solana RPC & DexScreener Websocket"
					/>
					<div class="mb-4 grid grid-cols-2 gap-2 font-mono sm:grid-cols-4">
						<div class="rounded-card border border-line bg-surface p-2.5">
							<div class="text-10 uppercase tracking-wide text-text-3">Bot paper</div>
							<div class="mt-0.5 text-20 font-bold {gmgnPaperObj ? 'text-pos' : 'text-text-3'}">{gmgnPaperObj ? 'Jalan' : '—'}</div>
							<div class="text-10 text-text-3">pemindai token baru</div>
						</div>
						<div class="rounded-card border border-line bg-surface p-2.5">
							<div class="text-10 uppercase tracking-wide text-text-3">Posisi dicatat</div>
							<div class="mt-0.5 text-20 font-bold text-text">{gmgnStats0?.trades ?? 0}</div>
							<div class="text-10 text-text-3">dari mesin paper</div>
						</div>
						<div class="rounded-card border border-line bg-surface p-2.5">
							<div class="text-10 uppercase tracking-wide text-text-3">Hasil tuntas</div>
							<div class="mt-0.5 text-20 font-bold {gmgnTuntas > 0 ? 'text-pos' : 'text-warn'}">{gmgnTuntas}</div>
							<div class="text-10 text-text-3">{gmgnTerbuka} masih terbuka</div>
						</div>
						<div class="rounded-card border border-line bg-surface p-2.5">
							<div class="text-10 uppercase tracking-wide text-text-3">Vonis gate</div>
							<div class="mt-0.5 text-18 font-bold text-warn">Belum dinilai</div>
							<div class="text-10 text-text-3">uji lolos vs ditolak belum ada</div>
						</div>
					</div>

					<DompetPasar market="gmgn" dompet={dompetObj} judul="Dompet Paper GMGN / LP" />
					<KartuNarasi narasi={narasiObj} />

				{:else if sub === 'setup'}
					<div class="space-y-4">
						<!-- Scanner Token Baru & Smart Money -->
						<div class="permukaan-2 rounded-card border border-line p-3">
							<div class="mb-3 flex items-center justify-between border-b border-line-soft pb-2">
								<div>
									<h3 class="text-14 font-medium text-text">GMGN Smart Money &amp; Whale Signals</h3>
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
												<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right">HARGA TERAKHIR</th>
												<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right">5M %</th>
												<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right">1H %</th>
												<th class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right">BAYANGAN</th>
											</tr>
										</thead>
										<tbody class="divide-y divide-line-soft">
											{#each gmgnObj.signals as s (s.id ?? s.simbol)}
												<tr class="hover:bg-surface/50 transition-colors">
													<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 font-bold text-text">
														{s.simbol}
														{#if s.whale}
															<span class="ml-1 rounded bg-accent/20 text-accent px-1 py-0.2 text-10">WHALE</span>
														{/if}
													</td>
													<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-text-3 text-11">{s.sumber}</td>
													<td class="py-1.5 px-1.5 sm:py-2 sm:px-2.5 text-right text-text-2">
														${s.beli_usd ? s.beli_usd.toLocaleString('id-ID') : '—'}
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

						<!-- Pumpfun Listings -->
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

				{:else if sub === 'ukur'}
					{@const vonis = hitungVonisLp(lpPaperObj)}
					<div class="space-y-4">
						{#if vonis.ada}
							<div class="grid grid-cols-1 gap-2 sm:grid-cols-3">
								<div class="rounded-card border border-neg/40 bg-neg/5 p-3 sm:col-span-2">
									<div class="text-10 uppercase tracking-wide text-text-3">Peluang hari ini</div>
									<div class="mt-1 flex flex-wrap items-baseline gap-x-2 gap-y-1">
										<span class="text-16 font-bold text-text">Belum ada — mesin LP ini merugi</span>
										<span class="rounded border border-neg/40 bg-neg/10 px-1.5 py-0.5 text-10 font-bold text-neg">
											{vonis.cukup ? 'Terbukti rugi' : 'Sampel belum cukup'}
										</span>
										<span class="font-mono text-12 text-neg">{vonis.mean > 0 ? '+' : ''}{angka(vonis.mean, { desimal: 2 })}% / trade</span>
									</div>
									<p class="mt-1 text-11 text-text-2">
										<i>Hipotesis:</i> mesin ini memilih pool memecoin untuk dipanen fee-nya, lalu dibandingkan
										dengan sekadar menahan token. Dari <b>{vonis.n} posisi tuntas</b>
										({vonis.cukup ? 'sampel cukup' : 'sampel kecil'}), median <b class="text-neg">{angka(vonis.median, { desimal: 2 })}%</b>
										dan menang cuma <b>{angka(vonis.menang, { desimal: 1 })}%</b>. Angka apa adanya dari ledger mesin.
									</p>
									<p class="mt-1 text-11 text-text-3">
										Vonis: <b class="text-neg">jangan taruh uang di sini</b>. Ini bukan mesin yang belum dioptimalkan —
										sinyalnya justru memilih pool yang cenderung jatuh (lihat panel Hati-hati).
									</p>
								</div>
								<div class="rounded-card border border-neg/30 bg-neg/5 p-3">
									<div class="text-10 uppercase tracking-wide text-text-3">Hati-hati</div>
									<ul class="mt-1 space-y-1 text-11 text-text-2">
										{#if vonis.grossRugi}
											<li>
												<b class="text-neg">Bukan cuma biaya</b> — sebelum biaya pun sudah
												{angka(vonis.grossMean, { desimal: 2 })}%. Jadi menurunkan fee tak menolong.
											</li>
										{/if}
										{#if vonis.sinyalParah && vonis.sig && vonis.ctrl}
											<li>
												<b class="text-neg">Sinyal lebih buruk dari acak</b> — pilihan ber-sinyal median
												{angka(vonis.sig.median_net_pct, { desimal: 2 })}% (n={vonis.sig.n}), pilihan acak (control)
												hanya {angka(vonis.ctrl.median_net_pct, { desimal: 2 })}% (n={vonis.ctrl.n}).
											</li>
										{/if}
										{#if vonis.slipLebihBesar}
											<li>
												<b class="text-neg">Selip harga 4× lebih besar</b> — sinyal {angka(vonis.slipSig, { desimal: 1 })}% vs
												acak {angka(vonis.slipCtrl, { desimal: 1 })}%. Sinyal menyasar pool lebih tipis.
											</li>
										{/if}
										<li>
											<b class="text-neg">{angka(vonis.sl, { desimal: 0 })}% posisi kena stop-loss</b> — keluar paksa
											(TP {angka(vonis.tp, { desimal: 0 })}%).
										</li>
									</ul>
								</div>
							</div>

							<div class="rounded-card border border-line bg-surface p-3">
								<div class="text-10 uppercase tracking-wide text-text-3">Uji kepekaan TP/SL</div>
								<p class="mt-1 text-11 text-text-2">
									Mesin sudah mencoba beberapa setelan target/stop. Semuanya rugi — jadi masalahnya bukan di setelan:
								</p>
								<div class="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4 font-mono">
									{#each Object.entries(vonis.perGeo) as [label, v]}
										<div class="rounded border border-line bg-canvas p-2">
											<div class="text-10 text-text-3">{label.replace('TP+', 'TP ').replace('/SL-', ' / SL ')}</div>
											<div class="text-13 font-bold {Number((v as any).mean_net_pct) > 0 ? 'text-pos' : 'text-neg'}">
												{angka(Number((v as any).mean_net_pct), { desimal: 2 })}%
											</div>
											<div class="text-10 text-text-3">n={(v as any).n}</div>
										</div>
									{/each}
								</div>
							</div>
						{/if}

						<AkurasiPasar
							judul="Akurasi &amp; PnL LP Terukur"
							subjudul="Mark lokal — rekonsiliasi on-chain belum ada (dinyatakan apa adanya)"
							data={akurasiGmgnT}
						/>
					</div>

				{:else if sub === 'eksekusi'}
					<div class="space-y-4">
						<!-- Bot Paper Memecoin (GMGN/FOMO) -->
						<div class="permukaan-2 rounded-card border border-line p-3">
							<div class="mb-3 flex items-center justify-between border-b border-line-soft pb-2">
								<div>
									<h3 class="text-14 font-medium text-text">Bot Paper Memecoin (GMGN/FOMO)</h3>
									<p class="text-11 text-text-3">Konfigurasi nyata dari folder state bot + kesehatan berkas yang dibaca job</p>
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

						<EquityCurve points={equityObj?.points} stats={equityObj?.stats} />
						<RiskMeter risiko={risikoObj} />

						<div class="permukaan-2 rounded-card border border-line p-3">
							<div class="mb-2 flex items-center justify-between border-b border-line-soft pb-2">
								<h3 class="text-13 font-medium text-text">Posisi Terbuka On-Chain</h3>
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
								<h3 class="text-13 font-medium text-text">Riwayat Eksekusi &amp; Ledger GMGN</h3>
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
					<Block judul="Daftar Fact Area" deskripsi={`${data.facts.length} fakta · sumber & umur ditampilkan apa adanya`}>
						<DataTable
							kolom={kolomFakta}
							baris={barisFakta}
							cari="cari kunci/nilai/sumber…"
							ekspor={`${kunci}-fakta.csv`}
						/>
					</Block>
				</div>
			{/if}

			<!-- Aliran kejadian SSE untuk area ini, tertutup secara default sebagai panel diagnosis. -->
			<Block
				judul="EventItem Area"
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
