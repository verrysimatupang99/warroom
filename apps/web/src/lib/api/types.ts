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
}

export interface MasukanGate {
	n: number;
	win: number;
	be: number;
	ci?: number;
	min_n?: number;
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