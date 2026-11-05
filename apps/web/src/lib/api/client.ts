/**
 * Klien API bertipe. Base URL kosong = same-origin (produksi lewat Caddy; dev lewat proxy
 * vite.config.ts) sehingga cookie sesi `wr_session` ikut tanpa CORS.
 * Semua panggilan membawa `credentials: 'include'`.
 */
import { env as envPublik } from '$env/dynamic/public';
import type {
	AlertsPayload,
	AreaPayload,
	AreasPayload,
	Me,
	DocContent,
	DocsPayload,
	SingleFact,
	MarketVerdict,
	GateResult,
	EventItem,
	Health,
	Readiness,
	FreshnessPayload,
	LiveArming,
	GateInput,
	MarketSummaryPayload,
	ResearchRecordsPayload,
	ResearchRunDetail,
	ResearchRunsPayload,
	ProposalsPayload,
	SignalPayload,
	LeaderboardPayload
} from './types';

export class ApiError extends Error {
	readonly status: number;
	readonly code: string | null;

	constructor(status: number, message: string, code: string | null = null) {
		super(message);
		this.name = 'ApiError';
		this.status = status;
		this.code = code;
	}
}

/**
 * Base URL API dari `$env/dynamic/public` (`PUBLIC_API_BASE`) — dibaca saat RUNTIME, bukan
 * saat build: `import.meta.env.PUBLIC_*` tidak pernah terisi karena Vite hanya menyuntik
 * variabel berawalan `VITE_`, sehingga fetch jadi relatif ke origin web dan berakhir 404.
 * Kosong = same-origin (produksi lewat Caddy; dev lewat proxy vite).
 */
const BASE = (envPublik.PUBLIC_API_BASE ?? '').replace(/\/$/, '');
const TIMEOUT_MS = 12000;

/**
 * URL absolut ke API. Wajib dipakai semua pemanggil (termasuk SSE): tanpa ini, fetch dari
 * browser menuju origin web dan berakhir 404 karena web tidak mem-proxy `/api/v1/*`.
 */
export function urlApi(jalur: string): string {
	return `${BASE}${jalur}`;
}

/** Balasan error API: `{error:{code,message}}` — pesan asli diteruskan ke UI. */
function pesanDari(n: number, body: unknown): ApiError {
	const b = body as { error?: { code?: string; message?: string }; detail?: unknown } | null;
	const code = b?.error?.code ?? null;
	let msg = b?.error?.message;
	if (!msg && typeof b?.detail === 'string') msg = b.detail;
	if (!msg) msg = `permintaan gagal (HTTP ${n})`;
	return new ApiError(n, msg, code);
}

async function minta<T>(jalur: string, init: RequestInit = {}): Promise<T> {
	const ctrl = new AbortController();
	const t = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
	try {
		const res = await fetch(`${BASE}${jalur}`, {
			...init,
			credentials: 'include',
			headers: {
				Accept: 'application/json',
				...(init.body ? { 'Content-Type': 'application/json' } : {}),
				...init.headers
			},
			signal: ctrl.signal
		});
		if (!res.ok) {
			let body: unknown = null;
			try {
				body = await res.json();
			} catch {
				body = null;
			}
			throw pesanDari(res.status, body);
		}
		return (await res.json()) as T;
	} catch (e) {
		if (e instanceof ApiError) throw e;
		if (e instanceof DOMException && e.name === 'AbortError') {
			throw new ApiError(0, `waktu habis (${TIMEOUT_MS} ms)`);
		}
		throw new ApiError(0, e instanceof Error ? e.message : String(e));
	} finally {
		clearTimeout(t);
	}
}

export const getKesehatan = () => minta<Health>('/api/v1/health');
export const getKesiapan = () => minta<Readiness>('/api/v1/ready');
export const getKesegaran = () => minta<FreshnessPayload>('/api/v1/freshness');
export const getAreas = () => minta<AreasPayload>('/api/v1/areas');
export const getArea = (area: string) => minta<AreaPayload>(`/api/v1/${encodeURIComponent(area)}`);
/** Area token kind-nonsnapshot (lpagent, paper20) — endpoint /api/v1/areas/{area}. */
export const getAreaFakta = (area: string) =>
	minta<AreaPayload>(`/api/v1/areas/${encodeURIComponent(area)}`);
export const getAku = () => minta<Me>('/api/v1/auth/me');
export const getFakta = (kind: string, key: string, riwayat = 20) =>
	minta<SingleFact>(
		`/api/v1/facts/${encodeURIComponent(kind)}/${encodeURIComponent(key)}?riwayat=${riwayat}`
	);
export const nilaiGate = (masukan: GateInput) =>
	minta<GateResult>('/api/v1/gate/evaluate', { method: 'POST', body: JSON.stringify(masukan) });

/** Alert terbuka + status transport (W5). Transport kosong tidak pernah diklaim terkirim. */
export const getAlerts = () => minta<AlertsPayload>('/api/v1/alerts');

/** Usulan parameter learner (P5-T4): baca untuk semua peran; terapkan/rollback khusus owner. */
export const getProposals = () => minta<ProposalsPayload>('/api/v1/proposals');

export const applyProposal = (id: number) =>
	minta<{ ok: boolean; oleh: string }>(`/api/v1/proposals/${id}/apply`, { method: 'POST' });

export const rollbackProposal = (id: number) =>
	minta<{ ok: boolean; oleh: string }>(`/api/v1/proposals/${id}/rollback`, { method: 'POST' });

/** Ack alert; `snoozeS > 0` menunda alih-alih meng-ack. Butuh peran operator. */
export const ackAlert = (id: number, snoozeS = 0) =>
	minta<{ ok: boolean; id: number; snooze_s: number }>(`/api/v1/alerts/${id}/ack`, {
		method: 'POST',
		body: JSON.stringify({ snooze_s: snoozeS })
	});

/** Login: menaruh cookie sesi HttpOnly. TLS & same-origin ditangani reverse proxy (Caddy). */
export const masuk = (username: string, password: string, totp?: string) =>
	minta<{ ok: boolean }>('/api/v1/auth/login', {
		method: 'POST',
		body: JSON.stringify({ username, password, totp: totp ?? null })
	});

/** Metrik Prometheus (teks) lewat jalur ber-sesi `/api/v1/metrics` — `/metrics` sengaja
 * tidak diekspos reverse proxy ke publik (berisi nama job & hitungan). */
export async function getMetrikTeks(): Promise<string> {
	const res = await fetch(`${BASE}/api/v1/metrics`, { credentials: 'include' });
	if (!res.ok) throw new ApiError(res.status, `gagal memuat /api/v1/metrics (HTTP ${res.status})`);
	return res.text();
}

export const basisApi = BASE;

/** Sinyal terbaik per pasar untuk Home (5 Okt 2026). Selalu mengembalikan SEMUA pasar —
 * yang kosong pun, supaya kartu tidak hilang diam-diam. */
export const getSinyalPerPasar = () => minta<SignalPayload>('/api/v1/sinyal/per-pasar');
/** Ringkas akurasi+PnL per market untuk Home — dari fakta pasar_akurasi/idx_akurasi. */
export const getPasarRingkas = () => minta<MarketSummaryPayload>('/api/v1/pasar/ringkas');
/** Read-only research catalog and immutable provenance. */
export const getResearchRuns = (researchKey?: string) =>
	minta<ResearchRunsPayload>(`/api/v1/research/runs${researchKey ? `?research_key=${encodeURIComponent(researchKey)}` : ''}`);
export const getResearchRun = (id: string) => minta<ResearchRunDetail>(`/api/v1/research/runs/${encodeURIComponent(id)}`);
export const getResearchRecords = (id: string) => minta<ResearchRecordsPayload>(`/api/v1/research/runs/${encodeURIComponent(id)}/records`);

export const getDocs = () => minta<DocsPayload>('/api/v1/docs');

/** Isi satu catatan menurut slug. */
export const getDoc = (slug: string) => minta<DocContent>(`/api/v1/docs/${encodeURIComponent(slug)}`);

/** EventItem terakhir (backfill panel EventItem Area). SSE hanya mengirim yang BARU. */
export async function getEvents(limit = 120, tipe?: string): Promise<EventItem[]> {
	// `tipe` boleh daftar dipisah koma (mis. 'trade.,signal.,verdict.').
	const q = new URLSearchParams({ limit: String(limit) });
	if (tipe) q.set('tipe', tipe);
	const res = await fetch(urlApi(`/api/v1/events?${q}`), { credentials: 'include' });
	if (!res.ok) throw new Error(`events HTTP ${res.status}`);
	const j = (await res.json()) as { events: EventItem[] };
	return j.events ?? [];
}

/** Sumber data tiap pasar (satu tempat: OKX, Stock Arjum, TVC, PM, GMGN/FOMO, Meteora/Uniswap). */
export async function getSumber(): Promise<{
	sumber: { pasar: string; label: string; sumber: string; keterangan: string }[];
	sumber_atom: { nama: string; dipakai: string }[];
}> {
	const res = await fetch(urlApi('/api/v1/sumber'), { credentials: 'include' });
	if (!res.ok) throw new Error(`sumber HTTP ${res.status}`);
	return (await res.json()) as {
		sumber: { pasar: string; label: string; sumber: string; keterangan: string }[];
		sumber_atom: { nama: string; dipakai: string }[];
	};
}

/** Verdict kanonik semua pasar — satu sumber keputusan (audit QA 7 Okt). */
export async function getVerdict(): Promise<{ verdict: MarketVerdict[]; aturan: Record<string, unknown> }> {
	const res = await fetch(urlApi('/api/v1/verdict'), { credentials: 'include' });
	if (!res.ok) throw new Error(`verdict HTTP ${res.status}`);
	return (await res.json()) as { verdict: MarketVerdict[]; aturan: Record<string, unknown> };
}
/** Status arming live — SATU-SATUNYA sumber badge mode global di UI (armed = LIVE, else PAPER).
 *  Gagal fetch = null (jujur: badge disembunyikan, bukan dikarang). */
export async function getLiveArming(): Promise<LiveArming | null> {
	try {
		const res = await fetch(urlApi('/api/v1/live/arming'), { credentials: 'include' });
		if (!res.ok) return null;
		return (await res.json()) as LiveArming;
	} catch {
		return null;
	}
}

/** Leaderboard performa strategi kuantitatif lintas instrumen. */
export const getLeaderboard = () => minta<LeaderboardPayload>('/api/v1/leaderboard');
