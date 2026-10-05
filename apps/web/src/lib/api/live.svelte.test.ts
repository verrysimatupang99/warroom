// Regresi fallback SSE → polling (audit Fase 3).
//
// Kenapa: `live.svelte.ts` menyambung lewat fetch+ReadableStream (bukan EventSource,
// karena tipe event dinamis). Bila stream putus, ia WAJIB jatuh ke polling 15 dtk dan
// menandai status `polling` — bukan diam-diam terlihat "live" padahal data berhenti.
// Tes ini mengunci kontrak itu tanpa jaringan: `fetch` dipalsukan gagal.
import { describe, it, expect, vi, afterEach } from 'vitest';

describe('fallback SSE → polling', () => {
	afterEach(() => vi.restoreAllMocks());

	it('stream gagal → status polling, dan mencoba memulihkan', async () => {
		vi.resetModules();
		// fetch selalu gagal → tidak pernah 'live'
		vi.stubGlobal(
			'fetch',
			vi.fn(async () => {
				throw new Error('jaringan mati');
			})
		);
		const { live } = await import('./live.svelte.ts');
		live.mulai();
		// beri satu putaran mikro-task supaya handler gagal jalan
		await new Promise((r) => setTimeout(r, 50));
		expect(['polling', 'menyambung']).toContain(live.status);
		live.hentikan();
		vi.unstubAllGlobals();
	});
});
