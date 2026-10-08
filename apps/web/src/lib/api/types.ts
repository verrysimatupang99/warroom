/**
 * API War Room (P1) — tipe balasan. Disalin dari kontrak FastAPI
 * (`services/api/src/warroom_api`); sumber kebenaran tetap OpenAPI di /api/openapi.json.
 * Semua angka domain datang dari `facts`; tidak ada perhitungan ulang di klien.
 */

export type StatusKesegaran = 'segar' | 'basi';
export type SourceState = 'fresh' | 'stale' | 'degraded' | 'unknown';
export type Peran = 'viewer' | 'operator' | 'owner';

export interface Fakta {
	fact_id: number;
	kind: string;
	key: string;
	value: unknown;
	source: string;
	observed_at: string;
	ttl_s: number;
	age_s: number;
	status: StatusKesegaran;
	hash: string;
}

/** Balasan `/api/v1/{area}`. `kunci_hilang` = kunci yang diminta area tapi belum ada fakta. */
export interface AreaPayload {
	area: string;
	dikenal: boolean;
	source_state?: SourceState;
	kunci_diminta?: string[];
	kunci_hilang?: string[];
	/** only emitted by the area endpoint when facts exist */
	areas?: string[];
	facts: Fakta[];
	data: Record<string, unknown>;
}

export interface BarisKesegaran {
	kind: string;
	key: string;
	source: string;
	observed_at: string;
	age_s: number;
	ttl_s: number;
	status: StatusKesegaran;
}

export interface KesegaranPayload {
	facts: BarisKesegaran[];
	count: number;
	checked_at: string;
}

export interface RingkasArea {
	area: string;
	fakta: number;
	hilang: number;
	basi: number;
	source_state: SourceState;
	observed_at_terakhir: string | null;
}

export interface AreasPayload {
	areas: RingkasArea[];
}

export interface FaktaSatu {
	kind: string;
	key: string;
	facts: {
		fact_id: number;
		value: unknown;
		source: string;
		observed_at: string;
		ttl_s: number;
		status: StatusKesegaran;
	}[];
}

export interface HasilGate {
	verdict: 'lolos' | 'gagal' | 'insufficient';
	reason: string;
	ci_low: number;
	ci_high: number;
	win_rate: number;
	be: number;
	n: number;
	required_n: number | null;
	policy_version: string;
	notes: string[];
	/** Kebijakan yang dipakai — UI wajib melabeli hasil dengan ini (90% vs 95%+deff). */
	ci?: number;
	deff?: number;
	/** n terkoreksi klaster (n ÷ deff); hadir bila gate memakai koreksi. */
	nEff?: number | null;
	/** Pakem bukti (6 Okt): kematangan sampel pada n efektif — terpisah dari verdict. */
	pakem?: 'INSUFFICIENT' | 'DIRECTIONAL' | 'PRELIMINARY' | 'TUNING';
	n_efektif?: number;
}

export interface MasukanGate {
	n: number;
	win: number;
	be: number;
	ci?: number;
	min_n?: number;
	/** Koreksi klaster (>= 1). Meneruskan nilai dari fakta supaya kebijakan sama dengan sumber. */
	deff?: number;
	/** n terkoreksi klaster dari fakta (n ÷ deff), bila sumber menyediakannya. */
	nEff?: number;
	split?: string | null;
	label?: string;
	subject?: string;
	rule?: string;
}

export interface Kesehatan {
	status: 'ok' | 'degraded';
	db: boolean;
	time: string;
	user: string;
}

export interface Aku {
	username: string;
	role: Peran;
}

/** Satu kejadian SSE (`/api/v1/stream`). */
export interface Kejadian {
	id: number;
	type: string;
	actor: string | null;
	severity: string | null;
	payload: unknown;
	fact_ids: unknown;
	created_at: string | null;
}
export interface ProviderSehat {
	provider: string;
	n: number;
	ok: number;
	gagal: number;
	ok_rate: number | null;
	fallback: number;
	p50_ms: number | null;
	p95_ms: number | null;
	token_in: number;
	token_out: number;
	error_terakhir: string | null;
}

export interface AiConsole {
	total_panggilan: number;
	fallback_rate: number | null;
	biaya_usd: number;
	per_provider: ProviderSehat[];
	per_peran: { role: string; n: number; gagal: number }[];
	catatan: string;
}

export interface AlertItem {
	id: number;
	severity: string;
	subject: string;
	message: string;
	suggested_action: string;
	ack_at: string | null;
	snooze_until: string | null;
	created_at: string;
	/** Jumlah percobaan kirim; >= 3 berarti notifier berhenti mencoba (tetap terbuka). */
	percobaan: number;
	kesalahan_terakhir: string | null;
	/** null = belum pernah dicoba; true = percobaan terakhir sukses. */
	terakhir_ok: boolean | null;
}

export interface AlertsPayload {
	transport: { nama: string; terkonfigurasi: boolean; detail?: string };
	terbuka: number;
	alerts: AlertItem[];
	percobaan_terakhir: Record<string, unknown> | null;
}

/** Usulan parameter dari learner (P5). `status`: menunggu | diterapkan | ditolak | dibatalkan | butuh_manusia. */
export interface Proposal {
	id: number;
	parameter: string;
	dari: unknown;
	ke: unknown;
	alasan: string;
	bukti: unknown;
	gate: string | null;
	status: string;
	ditolak_karena: string | null;
	diputuskan_oleh: string | null;
	diterapkan_pada: string | null;
	config_hash: string | null;
	dibuat: string | null;
}

export interface ProposalsPayload {
	proposals: Proposal[];
	count: number;
}

/** Satu sinyal terbaik untuk satu pasar (GET /api/v1/sinyal/per-pasar, 5 Okt 2026).
 * `skor` = None berarti tidak ada angka (BUKAN 0). `terverifikasi` = sudah lewat split beku;
 * selama false, sinyal ini klaim eksplorasi dan UI wajib menampilkannya apa adanya. */
export interface SinyalPasar {
	pasar: string;
	label: string;
	ada: boolean;
	arah: string | null;
	subjek: string | null;
	skor: number | null;
	tier: string | null;
	alasan: string;
	terverifikasi: boolean;
	catatan_kejujuran: string;
	umur_s: number | null;
	sumber_fakta: string;
	/** Kapan sinyal DIGENERATE (ISO apa adanya dari mesin) + umurnya saat ini (detik). */
	dibuat_pada: string | null;
	umur_sinyal_s: number | null;
	/** Status ketersediaan (revisi 7 Okt): "ada" · "kosong" (mesin hidup, tak ada setup
	 *  cocok) · "gagal" (sumber tak terbaca / mesin mati). Dua yang terakhir TIDAK sama. */
	status_data: 'ada' | 'kosong' | 'gagal';
	detail: Record<string, unknown>;
}

export interface SinyalItem {
	pair: string | null;
	arah: string | null;
	tier: string | null;
	entry: unknown;
	sl: unknown;
	tp1: unknown;
	r_r: unknown;
	risk_pct: unknown;
	strategy?: string | null;
	mode?: 'PAPER' | 'LIVE' | 'HISTORIS' | null;
	detail?: Record<string, unknown>;
	aturan_gagal: string[];
	label: string | null;
	umur_s: number | null;
	skor: number | null;
}

/** Sinyal satu pasar untuk Home: maks 3 + status jujur (ada/kosong/gagal). */
export interface DaftarSinyalPasar {
	pasar: string;
	label: string;
	/** "ada" = ada sinyal · "kosong" = mesin hidup tapi tak ada setup cocok ·
	 *  "gagal" = sumber tak terbaca/mesin mati (JANGAN ditulis "tidak ada sinyal"). */
	status_data: 'ada' | 'kosong' | 'gagal';
	alasan: string;
	rute: string;
	jumlah: number;
	/** Dari mana angka ini datang (mis. "MEXC", "Stock Arjum") — QA 7 Okt. */
	sumber?: string;
	/** Tingkat kepercayaan eksekusi: LIVE (belum ada) · PAPER · HISTORIS (beku). */
	mode?: 'LIVE' | 'PAPER' | 'HISTORIS';
	catatan_mode?: string;
	sinyal: SinyalItem[];
}

export interface SinyalPayload {
	sinyal: SinyalPasar[];
	pasar?: DaftarSinyalPasar[];
	count: number;
	ada: number;
}

/** Ringkas akurasi+PnL per market (endpoint /pasar/ringkas) — angka apa adanya dari fakta. */
export interface BarisPasarRingkas {
	pasar: string;
	label: string;
	tersedia: boolean;
	alasan: string | null;
	n: number | null;
	n_hari: number | null;
	winrate_pct: number | null;
	mean_r: number | null;
	total_r: number | null;
	pnl_usd: number | null;
	tingkat: string | null;
	setup: string | null;
	jumlah_setup: number;
	/** Blok BUKTI (audit QA putaran 3) — tujuh jawaban untuk halaman Kinerja & Bukti.
	 *  `null` bila mesin belum menghitungnya; UI wajib menulis "—", bukan 0. */
	bukti?: {
		closed_trades?: number | null;
		win_rate_pct?: number | null;
		mean_r?: number | null;
		total_r?: number | null;
		pnl_usd?: number | null;
		max_drawdown_r?: number | null;
		biaya_tercatat?: boolean | null;
		biaya_keterangan?: string;
		periode?: { dari?: string | null; sampai?: string | null };
		denominator?: string;
		n_hari?: number | null;
		tingkat?: string | null;
		sumber?: string | null;
	} | null;
}

export interface ResearchRunSummary {
	id: string;
	research_key: string;
	hypothesis_id: string;
	hypothesis_version: string;
	hypothesis_hash: string;
	execution_hash: string;
	status: string;
	created_at: string | null;
	completed_at: string | null;
}

export interface ResearchRunsPayload {
	runs: ResearchRunSummary[];
	count: number;
}

export interface ResearchRecord {
	id: string;
	kind: string;
	uri: string;
	sha256: string;
	status: string;
	provenance: Record<string, unknown>;
	observed_at: string | null;
	created_at: string | null;
}

export interface ResearchRunDetail extends ResearchRunSummary {
	hypothesis: Record<string, unknown>;
	execution: Record<string, unknown>;
	provenance: Record<string, unknown>;
	artifacts: ResearchRecord[];
	artifact_count: number;
	evidence_status: 'available' | 'blocked';
	blocked_reason: string | null;
}

export interface ResearchRecordsPayload {
	records: ResearchRecord[];
	count: number;
}

export interface PasarRingkasPayload {
	pasar: Record<string, BarisPasarRingkas>;
	standar: string | null;
	sumber: string;
}

/** Fakta `poly.dataset/recorder` — katalog dataset Polymarket (P4-T3). Bentuk longgar: hanya
 * field yang benar-benar dikirim sumber yang ditampilkan. */
export interface FaktaDataset {
	paired?: { path?: string; bytes?: number; files?: number; [k: string]: unknown };
	labels?: { [k: string]: unknown };
	[k: string]: unknown;
}

/** `GET /api/v1/design/tokens` — token dari app.css, dibaca API (bukan disalin).
 *
 * Arahnya SENGAJA terbalik dari biasanya: CSS adalah sumbernya, API yang membacanya.
 * Jadi frontend tidak perlu memanggil ini untuk merender (token sudah di CSS-nya);
 * tipe ini untuk alat lain (ekspor, chart, atau sesi agen) yang butuh nilainya. */
export interface DesignTokens {
	ada: boolean;
	sumber?: string;
	jumlah?: number;
	token?: Record<string, string>;
	alasan?: string;
}

/** `GET /api/v1/docs` — daftar catatan. */
export interface DocsPayload {
	ada: boolean;
	alasan?: string;
	jumlah?: number;
	dokumen: { slug: string; judul: string; ukuran: number }[];
}

/** `GET /api/v1/docs/{slug}` — isi satu catatan (markdown mentah). */
export interface DocIsi {
	slug: string;
	judul: string;
	isi: string;
}

/** Verdict KANONIK per pasar (audit QA 7 Okt) — backend yang memutuskan, UI merender. */
export interface VerdictPasar {
	pasar: string;
	label: string;
	signal_state: 'none' | 'candidate' | 'confirmed';
	evidence_state: string;
	risk_state: 'unknown' | 'ok' | 'warning' | 'breach';
	execution_state: 'unknown' | 'paper' | 'frozen' | 'live';
	promotion_state: 'blocked' | 'promotable';
	headline: string;
	decision: string;
	blocked_reason: string | null;
	observed_edge: boolean;
	validated_edge: boolean;
	promotable_edge: boolean;
	detail: Record<string, unknown>;
}
