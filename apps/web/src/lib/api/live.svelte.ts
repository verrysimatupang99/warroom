/**
 * Store live (Svelte 5 runes). Prinsip: live lewat SSE, bukan `meta refresh`.
 *
 * Kenapa `fetch` + ReadableStream, bukan `EventSource`: server mengirim `event: <tipe>`
 * dinamis (mis. `snapshot.published`, `job.ran`) yang tidak bisa didengar EventSource tanpa
 * daftar nama tetap. Parser manual juga memberi kontrol koneksi/putus → fallback polling.
 */
import type { EventItem } from './types';
import { getKesegaran, urlApi } from './client';

export type StatusLive = 'menyambung' | 'live' | 'polling' | 'n/a';

const TOPIK_BAKU = 'signals,verdicts,trades,alerts,llm,services,params,facts';
const MAKS_KEJADIAN = 300;
const ULANG_MS = 3000;
const POLL_MS = 15000;

class StoreLive {
	status = $state<StatusLive>('menyambung');
	kejadian = $state<EventItem[]>([]);
	idTerakhir = $state<number | null>(null);
	terakhirPoll = $state<string | null>(null);
	pesan = $state<string | null>(null);

	#topik = TOPIK_BAKU;
	#abort: AbortController | null = null;
	#timerUlang: ReturnType<typeof setTimeout> | null = null;
	#timerPoll: ReturnType<typeof setInterval> | null = null;
	#gagal = 0;
	#berhenti = false;

	mulai(topik: string = TOPIK_BAKU): void {
		this.#topik = topik;
		this.#berhenti = false;
		if (typeof window === 'undefined' || typeof fetch === 'undefined') {
			this.status = 'n/a';
			return;
		}
		this.#alir();
	}

	#jadwalUlang(delay: number): void {
		if (this.#berhenti || this.#timerUlang) return;
		this.#timerUlang = setTimeout(() => {
			this.#timerUlang = null;
			if (!this.#berhenti) this.#alir();
		}, delay);
	}

	async #alir(): Promise<void> {
		this.#abort?.abort();
		this.#abort = new AbortController();
		this.status = 'menyambung';
		const jalur = urlApi(
			`/api/v1/stream?topics=${encodeURIComponent(this.#topik)}` +
				(this.idTerakhir != null ? `&last_event_id=${this.idTerakhir}` : '')
		);
		try {
			const res = await fetch(jalur, {
				credentials: 'include',
				headers: { Accept: 'text/event-stream' },
				signal: this.#abort.signal
			});
			if (!res.ok || !res.body) throw new Error(`stream HTTP ${res.status}`);
			this.status = 'live';
			this.#gagal = 0;
			this.pesan = null;
			this.#lupakanPolling();
			await this.#baca(res.body);
			// Aliran tertutup normal (server restart) → sambung ulang.
			if (!this.#berhenti) this.#jadwalUlang(ULANG_MS);
		} catch (e) {
			if (this.#berhenti) return;
			const abort = e instanceof DOMException && e.name === 'AbortError';
			if (abort) return;
			this.#gagal += 1;
			this.pesan = e instanceof Error ? e.message : String(e);
			// SSE putus → fallback polling 15 dtk + badge `realtime n/a` (aturan 2).
			this.#mulaiPolling();
		}
	}

	async #baca(body: ReadableStream<Uint8Array>): Promise<void> {
		const reader = body.getReader();
		const dec = new TextDecoder();
		let buf = '';
		for (;;) {
			const { value, done } = await reader.read();
			if (done) break;
			buf += dec.decode(value, { stream: true });
			let potong: number;
			while ((potong = buf.indexOf('\n\n')) >= 0) {
				const blok = buf.slice(0, potong);
				buf = buf.slice(potong + 2);
				this.#urai(blok);
			}
		}
	}

	#urai(blok: string): void {
		let id: number | null = null;
		let tipe: string | null = null;
		const data: string[] = [];
		for (const baris of blok.split('\n')) {
			if (baris.startsWith(':')) continue; // komentar/denyut
			const koma = baris.indexOf(':');
			if (koma < 0) continue;
			const medan = baris.slice(0, koma);
			const isi = baris.slice(koma + 1).replace(/^ /, '');
			if (medan === 'id') {
				const n = Number(isi);
				if (Number.isFinite(n)) id = n;
			} else if (medan === 'event') tipe = isi;
			else if (medan === 'data') data.push(isi);
		}
		if (tipe === null && data.length === 0) return;
		let payload: unknown = null;
		if (data.length) {
			try {
				payload = JSON.parse(data.join('\n'));
			} catch {
				payload = data.join('\n');
			}
		}
		// Pesan sambutan `{ok:true}` tidak punya tipe → bukan kejadian domain.
		if (tipe === null) return;
		const isi = (payload ?? {}) as Partial<EventItem> & { id?: number };
		const kid = typeof isi.id === 'number' ? isi.id : id;
		if (kid != null) this.idTerakhir = kid;
		const kj: EventItem = {
			id: kid ?? 0,
			type: tipe,
			actor: isi.actor ?? null,
			severity: isi.severity ?? null,
			payload: isi.payload ?? payload,
			fact_ids: isi.fact_ids ?? null,
			created_at: isi.created_at ?? null
		};
		this.kejadian = [kj, ...this.kejadian].slice(0, MAKS_KEJADIAN);
	}

	#lupakanPolling(): void {
		if (this.#timerPoll) {
			clearInterval(this.#timerPoll);
			this.#timerPoll = null;
		}
	}

	#mulaiPolling(): void {
		if (this.#timerPoll || this.#berhenti) return;
		this.status = 'polling';
		const denyut = async () => {
			try {
				const f = await getKesegaran();
				this.terakhirPoll = f.checked_at;
			} catch {
				/* polling gagal dicatat lewat status, bukan exception ke UI */
			}
		};
		void denyut();
		this.#timerPoll = setInterval(() => void denyut(), POLL_MS);
		// Tetap coba pulihkan SSE, makin jarang saat terus gagal.
		this.#jadwalUlang(Math.min(ULANG_MS * (this.#gagal + 1), POLL_MS * 2));
	}

	hentikan(): void {
		this.#berhenti = true;
		this.#abort?.abort();
		if (this.#timerUlang) clearTimeout(this.#timerUlang);
		this.#timerUlang = null;
		this.#lupakanPolling();
	}

	/** EventItem difilter berdasarkan prefiks tipe (mis. `alert.`). */
	berdasarkanTopik(prefiks: string[]): EventItem[] {
		if (!prefiks.length) return this.kejadian;
		return this.kejadian.filter((k) => prefiks.some((p) => k.type.startsWith(p)));
	}
}

export const live = new StoreLive();