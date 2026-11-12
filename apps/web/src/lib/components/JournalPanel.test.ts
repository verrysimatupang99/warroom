import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/svelte';
import JournalPanel from './JournalPanel.svelte';

const statsUsd = {
	market: 'forex',
	akun: '12345678',
	currency: 'USD',
	saldo: 1000.0,
	ekuitas: 1050.0,
	pnl_hari_ini_usd: 50.0,
	n_fill_forex: 5
};

const statsUsc = {
	market: 'forex',
	akun: '452009427',
	currency: 'USC',
	cent_factor: 100.0,
	saldo: 1074.81,
	ekuitas: 1074.81,
	pnl_hari_ini_usd: 12.5,
	n_fill_forex: 2
};

const tradesUsc = {
	closed: [
		{
			iso: '2026-10-15 14:30:00',
			symbol: 'XAUUSD',
			side: 'BUY',
			price_filled: '2650.50',
			market: 'forex',
			currency: 'USC',
			account: '452009427',
			net_usc: 12.5,
			pnl_usd: '0.125',
			ticket: '1001'
		}
	]
};

function stubFetch(isCent = true) {
	return vi.fn((url: string) => {
		if (url.includes('/api/v1/journal/stats')) {
			return Promise.resolve({ ok: true, json: () => Promise.resolve(isCent ? statsUsc : statsUsd) } as Response);
		}
		if (url.includes('/api/v1/journal/trades')) {
			return Promise.resolve({ ok: true, json: () => Promise.resolve(isCent ? tradesUsc : { closed: [] }) } as Response);
		}
		return Promise.resolve({ ok: true, json: () => Promise.resolve({}) } as Response);
	});
}

describe('JournalPanel', () => {
	afterEach(() => {
		vi.unstubAllGlobals();
		vi.restoreAllMocks();
	});

	it('memformat saldo dan ekuitas dengan USC ($...) untuk akun Cent (FE-03 / US-09)', async () => {
		vi.stubGlobal('fetch', stubFetch(true));
		render(JournalPanel, { props: { market: 'forex' } });

		await waitFor(() => {
			expect(screen.getByText('FOREX · EKUITAS')).toBeTruthy();
		});

		// 1074.81 USC ($10.75)
		expect(document.body.textContent).toContain('1074.81 USC ($10.75)');
		expect(document.body.textContent).toContain('+12.50 USC (+$0.13)');
	});

	it('memformat saldo standar USD untuk akun non-cent', async () => {
		vi.stubGlobal('fetch', stubFetch(false));
		render(JournalPanel, { props: { market: 'forex' } });

		await waitFor(() => {
			expect(screen.getByText('FOREX · EKUITAS')).toBeTruthy();
		});

		expect(document.body.textContent).toContain('$1050.00');
		expect(document.body.textContent).toContain('saldo $1000.00');
	});
});
