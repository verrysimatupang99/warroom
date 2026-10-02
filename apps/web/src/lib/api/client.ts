/**
 * Klien API bertipe. Base URL kosong = same-origin (produksi lewat Caddy; dev lewat proxy
 * vite.config.ts) sehingga cookie sesi `wr_session` ikut tanpa CORS.
 * Semua panggilan membawa `credentials: 'include'`.
 */
import { env as envPublik } from '$env/dynamic/public';
import type {
	AreaPayload,
	AreasPayload,
	Aku,
	FaktaSatu,
	HasilGate,
	Kesehatan,
	KesegaranPayload,
	MasukanGate
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

/** `/metrics` Prometheus: teks, bukan JSON. */
export async function getMetrikTeks(): Promise<string> {
	const res = await fetch(`${BASE}/metrics`, { credentials: 'include' });
	if (!res.ok) throw new ApiError(res.status, `gagal memuat /metrics (HTTP ${res.status})`);
	return res.text();
}

export const basisApi = BASE;