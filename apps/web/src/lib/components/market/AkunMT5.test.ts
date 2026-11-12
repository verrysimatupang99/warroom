import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/svelte';
import AkunMT5 from './AkunMT5.svelte';

function mockApi() {
	const fetchMock = vi.fn(async (url: string) => {
		const u = String(url);
		if (u.includes('/mt5/accounts')) {
			return {
				ok: true,
				status: 200,
				json: async () => ({
					primary: '416510164',
					accounts: [
						{ account: '416510164', primary: true, connected: true, balance: 1000, equity: 1000, positions: 0, seconds_ago: 4 },
						{ account: '999001', primary: false, connected: true, balance: 10, equity: 10.2, positions: 1, seconds_ago: 3 }
					]
				})
			};
		}
		if (u.includes('/mt5/status')) {
			const kedua = u.includes('999001');
			return {
				ok: true,
				status: 200,
				json: async () => ({
					account: kedua ? '999001' : '416510164',
					balance: kedua ? 10 : 1000,
					equity: kedua ? 10.2 : 1000,
					floating_pnl: kedua ? 0.2 : 0,
					seconds_ago: 3,
					positions: kedua
						? [{ ticket: 1, symbol: 'XAUUSDm', side: 'BUY', volume: 0.01, open_price: 4000, current_price: 4001, pnl_usd: 0.2 }]
						: []
				})
			};
		}
		if (u.includes('/journal/performance')) {
			return {
				ok: true,
				status: 200,
				json: async () => ({
					n_titik: u.includes('999001') ? 2 : 0,
					deret: [{ t: '2026-10-31T00:00:00+00:00', equity: 10 }, { t: '2026-10-31T01:00:00+00:00', equity: 10.2 }],
					markers: [],
					drawdown_max_pct: 0
				})
			};
		}
		return { ok: true, status: 200, json: async () => ({ closed: [] }) };
	});
	vi.stubGlobal('fetch', fetchMock);
	return fetchMock;
}


afterEach(() => vi.unstubAllGlobals());

describe('AkunMT5', () => {
	it('menampilkan akun utama dan detail posisi akun kedua', async () => {
		mockApi();
		render(AkunMT5);
		expect(await screen.findByText('Akun MT5')).toBeInTheDocument();
		expect(await screen.findByText('#416510164')).toBeInTheDocument();
		expect(await screen.findByText('#999001')).toBeInTheDocument();
		expect((await screen.findAllByText('$1000.00')).length).toBeGreaterThan(0);

		await fireEvent.click(screen.getByText('#999001'));
		expect((await screen.findAllByText('$10.00')).length).toBeGreaterThan(0);
		expect(await screen.findByText('XAUUSDm')).toBeInTheDocument();
		expect((await screen.findAllByText('$0.20')).length).toBeGreaterThan(0);
	});

	it('menampilkan format USC dan badge CENT bila akun menggunakan mata uang USC', async () => {
		const fetchMock = vi.fn(async (url: string) => {
			const u = String(url);
			if (u.includes('/mt5/accounts')) {
				return {
					ok: true,
					status: 200,
					json: async () => ({
						primary: '452009427',
						accounts: [
							{ account: '452009427', currency: 'USC', primary: true, connected: true, balance: 1074.81, equity: 1074.81, positions: 0, seconds_ago: 2 }
						]
					})
				};
			}
			if (u.includes('/mt5/status')) {
				return {
					ok: true,
					status: 200,
					json: async () => ({
						account: '452009427',
						currency: 'USC',
						balance: 1074.81,
						equity: 1074.81,
						floating_pnl: 0,
						seconds_ago: 2,
						positions: []
					})
				};
			}
			return { ok: true, status: 200, json: async () => ({ closed: [] }) };
		});
		vi.stubGlobal('fetch', fetchMock);

		render(AkunMT5);
		expect(await screen.findByText('#452009427')).toBeInTheDocument();
		expect(await screen.findByText('CENT')).toBeInTheDocument();
		expect((await screen.findAllByText('1074.81 USC ($10.75)')).length).toBeGreaterThan(0);
	});

	it('menampilkan alasan saat belum ada akun', async () => {
		vi.stubGlobal(
			'fetch',
			vi.fn(async () => ({ ok: true, status: 200, json: async () => ({ accounts: [] }) }))
		);
		render(AkunMT5);
		expect(await screen.findByText(/Belum ada telemetri akun/)).toBeInTheDocument();
	});
});
