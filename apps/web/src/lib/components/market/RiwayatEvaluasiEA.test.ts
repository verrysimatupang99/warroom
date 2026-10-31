import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import RiwayatEvaluasiEA from './RiwayatEvaluasiEA.svelte';

function mockFetch(payload: unknown, ok = true) {
	const spy = vi.fn(async () => ({ ok, status: ok ? 200 : 503, json: async () => payload }));
	vi.stubGlobal('fetch', spy);
	return spy;
}

afterEach(() => vi.unstubAllGlobals());

describe('RiwayatEvaluasiEA', () => {
	it('menampilkan evaluasi EA dan menandai sesi', async () => {
		const spy = mockFetch({
			n: 2,
			terakhir: [
				{
					ts: '2026-10-30T08:05:00+00:00',
					pair: 'XAUUSD',
					sesi: true,
					alasan: 'menunggu breakout',
					atr: 3.8,
					spread: 0.24,
					rsi: 55.2,
					tren: 'BULL'
				},
				{
					ts: '2026-10-29T20:05:00+00:00',
					pair: 'XAUUSD',
					sesi: false,
					alasan: 'di luar sesi Reaper',
					atr: 4.1,
					spread: 0.3,
					rsi: 48.0,
					tren: 'BEAR'
				}
			]
		});
		render(RiwayatEvaluasiEA);
		expect(await screen.findByText('menunggu breakout')).toBeInTheDocument();
		expect(screen.getByText('di luar sesi Reaper')).toBeInTheDocument();
		expect(screen.getByText('SESI')).toBeInTheDocument();
		expect(screen.getByText('LUAR')).toBeInTheDocument();
		expect(spy).toHaveBeenCalledWith(
			expect.stringContaining('/api/v1/journal/scanlog?market=forex'),
			expect.anything()
		);
	});

	it('menampilkan alasan saat API menolak', async () => {
		mockFetch({ detail: { message: 'belum ada telemetri' } }, false);
		render(RiwayatEvaluasiEA);
		expect(await screen.findByText(/belum ada telemetri/)).toBeInTheDocument();
	});
});
