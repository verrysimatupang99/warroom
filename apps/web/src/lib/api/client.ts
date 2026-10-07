/**
 * Klien API bertipe. Base URL kosong = same-origin (produksi lewat Caddy; dev lewat proxy
 * vite.config.ts) sehingga cookie sesi `wr_session` ikut tanpa CORS.
 * Semua panggilan membawa `credentials: 'include'`.
 */
import { env as envPublik } from '$env/dynamic/public';
import type {
	AiConsole,
	AlertsPayload,
	AreaPayload,
	AreasPayload,
	Aku,
	DocIsi,
	DocsPayload,
	FaktaSatu,
	HasilGate,
	Kejadian,
	Kesehatan,
	KesegaranPayload,
	MasukanGate,
	PasarRingkasPayload,
	ProposalsPayload,
	SinyalPayload
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

export const getKesehatan = () => minta<Kesehatan>('/api/v1/health');
export const getKesegaran = () => minta<KesegaranPayload>('/api/v1/freshness');
export const getAreas = () => minta<AreasPayload>('/api/v1/areas');
export const getArea = (area: string) => minta<AreaPayload>(`/api/v1/${encodeURIComponent(area)}`);
export const getAku = () => minta<Aku>('/api/v1/auth/me');
export const getFakta = (kind: string, key: string, riwayat = 20) =>
	minta<FaktaSatu>(
		`/api/v1/facts/${encodeURIComponent(kind)}/${encodeURIComponent(key)}?riwayat=${riwayat}`
	);
export const nilaiGate = (masukan: MasukanGate) =>
	minta<HasilGate>('/api/v1/gate/evaluate', { method: 'POST', body: JSON.stringify(masukan) });

/** Kesehatan provider LLM (W6): dari tabel `llm_calls`, tanpa penghitung di memori. */
export const getAiConsole = () => minta<AiConsole>('/api/v1/ai/llm-console');

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
export const getSinyalPerPasar = () => minta<SinyalPayload>('/api/v1/sinyal/per-pasar');
/** Ringkas akurasi+PnL per market untuk Home — dari fakta pasar_akurasi/idx_akurasi. */
export const getPasarRingkas = () => minta<PasarRingkasPayload>('/api/v1/pasar/ringkas');
/** Daftar catatan (docs/belajar) — endpoint membaca berkas markdown langsung. */
export const getDocs = () => minta<DocsPayload>('/api/v1/docs');

/** Isi satu catatan menurut slug. */
export const getDoc = (slug: string) => minta<DocIsi>(`/api/v1/docs/${encodeURIComponent(slug)}`);

/** Kejadian terakhir (backfill panel Kejadian Area). SSE hanya mengirim yang BARU. */
export async function getEvents(limit = 120, tipe?: string): Promise<Kejadian[]> {
	// `tipe` boleh daftar dipisah koma (mis. 'trade.,signal.,verdict.').
	const q = new URLSearchParams({ limit: String(limit) });
	if (tipe) q.set('tipe', tipe);
	const res = await fetch(urlApi(`/api/v1/events?${q}`), { credentials: 'include' });
	if (!res.ok) throw new Error(`events HTTP ${res.status}`);
	const j = (await res.json()) as { events: Kejadian[] };
	return j.events ?? [];
}

/** Sumber data tiap pasar (satu tempat: MEXC, Stock Arjum, TVC, PM, GMGN/FOMO, Meteora/Uniswap). */
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
