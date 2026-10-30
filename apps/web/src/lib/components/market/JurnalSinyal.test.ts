import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import JurnalSinyal from './JurnalSinyal.svelte';

function mockFetch(payload: unknown, ok = true) {
	return vi.fn(async () => ({ ok, status: ok ? 200 : 503, json: async () => payload }));
}

afterEach(() => vi.unstubAllGlobals());

describe('JurnalSinyal', () => {
	it('menampilkan ringkasan dan baris sinyal', async () => {
		vi.stubGlobal(
			'fetch',
			mockFetch({
				dihitung_at: '2026-10-30T20:48:00+00:00',
				fee_bps_per_sisi: 5,
				montecarlo: { n_sampel: 334, n_simulasi: 10000, p_profit: 72.5, total_p5: -12.3, total_p50: 34.0, total_p95: 81.2, maxdd_p95: 9.4 },
				ringkas: {
					n_terkirim: 450,
					n_terisi: 334,
					winrate: 54.5,
					expectancy_r: 0.1651,
					expectancy_net_r: 0.102,
					total_r: 55.14,
					total_r_net: 34.64,
					biaya_r_rata: 0.061,
					beda_cache: 10,
					per_versi: { legacy: { n_terisi: 334, winrate: 54.5, expectancy_net_r: 0.102 } },
					per_tier: {
						PREMIUM: { n_terkirim: 213, n_terisi: 157, tp1: 92, sl: 48, winrate: 58.6, expectancy_r: 0.29, expectancy_net_r: 0.23 },
						STANDAR: { n_terkirim: 237, n_terisi: 177, tp1: 90, sl: 81, winrate: 50.8, expectancy_r: 0.054, expectancy_net_r: -0.012 }
					}
				},
				rows: [
					{ dikirim: '2026-10-30T09:00:00+00:00', pair: 'INJUSDT', side: 'SHORT', tier: 'PREMIUM', entry: 7.2, hasil: 'tp1', r: 1, r_net: 0.94 },
					{ dikirim: '2026-10-30T10:00:00+00:00', pair: 'APTUSDT', side: 'SHORT', tier: 'PREMIUM', entry: 4.4, hasil: 'sl', r: -1, r_net: -1.06 }
				]
			})
		);
		render(JurnalSinyal);
		expect(await screen.findByText('Jurnal sinyal terkirim')).toBeInTheDocument();
		expect(await screen.findByText('450')).toBeInTheDocument();
		expect(await screen.findByText('54.5%')).toBeInTheDocument();
		expect(await screen.findByText('0.102R')).toBeInTheDocument();
		expect(await screen.findByText(/Net setelah biaya 5 bps\/sisi/)).toBeInTheDocument();
		expect(await screen.findByTestId('montecarlo')).toHaveTextContent(/P\(profit\) 72.5%/);
		expect(await screen.findByText(/legacy · n=334/)).toBeInTheDocument();
		expect(await screen.findByText('INJUSDT')).toBeInTheDocument();
		expect(await screen.findByText('APTUSDT')).toBeInTheDocument();
		expect(await screen.findByText(/10 hasil berbeda dari cache/)).toBeInTheDocument();
	});

	it('menampilkan alasan saat jurnal belum ada', async () => {
		vi.stubGlobal('fetch', mockFetch({ detail: { message: 'belum dihitung' } }, false));
		render(JurnalSinyal);
		expect(await screen.findByText(/belum tersedia: belum dihitung/)).toBeInTheDocument();
	});
});
