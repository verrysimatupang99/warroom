/**
 * API War Room (P1) — tipe balasan. Disalin dari kontrak FastAPI
 * (`services/api/src/warroom_api`); sumber kebenaran tetap OpenAPI di /api/openapi.json.
 * Semua angka domain datang dari `facts`; tidak ada perhitungan ulang di klien.
 */

export type StatusKesegaran = 'segar' | 'basi';
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
	kunci_diminta?: string[];
	kunci_hilang?: string[];
	/** hanya muncul bila area tidak dikenal */
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
}

export interface MasukanGate {
	n: number;
	win: number;
	be: number;
	ci?: number;
	min_n?: number;
	/** Koreksi klaster (>= 1). Meneruskan nilai dari fakta supaya kebijakan sama dengan sumber. */
	deff?: number;
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
}

export interface AlertsPayload {
	transport: { nama: string; terkonfigurasi: boolean; detail?: string };
	terbuka: number;
	alerts: AlertItem[];
	percobaan_terakhir: Record<string, unknown> | null;
}
