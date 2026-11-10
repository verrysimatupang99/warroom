import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/svelte';
import ForexCockpitExness from './ForexCockpitExness.svelte';

// ForexCockpitExness memanggil fetch() global ke 3 endpoint (mt5/status,
// forex/sentinel, forex/levels) lalu polling tiap 2.5 dtk. Kita stub fetch
// agar komponen bisa dirender tanpa jaringan.
const mt5 = {
	connected: true,
	account: '36525553',
	broker: 'Exness-MT5Trial7',
	balance: 1000,
	equity: 512.5,
	floating_pnl: 12.5,
	margin: 100,
	free_margin: 412.5,
	positions: [],
	total_trades_today: 7,
	win_rate_pct: 57.1,
	wins: 4,
	losses: 3,
	net_pnl_usd: 12.5,
	seconds_ago: 3
};

const sentinel = {
	sentinel: 'LAYA',
	active: true,
	verdict: 'RISK-ON',
	security: 'OK',
	confidence: 0.82,
	engine: 'laya',
	active_strategy: 'momentum',
	all_strategies: []
};

const signal = { symbol: 'XAUUSD', bias: 'BUY', levels: [] };

function stubFetch(ok = true) {
	return vi.fn((url: string) => {
		const body = url.includes('mt5/status') ? mt5 : url.includes('sentinel') ? sentinel : signal;
		return Promise.resolve({ ok, json: () => Promise.resolve(body) } as Response);
	});
}

beforeEach(() => {
	vi.stubGlobal('fetch', stubFetch(true));
});
afterEach(() => {
	vi.unstubAllGlobals();
	vi.restoreAllMocks();
});

describe('ForexCockpitExness', () => {
	it('render judul cockpit', async () => {
		render(ForexCockpitExness);
		expect(await screen.findByText(/EXNESS MT5 ALGO COCKPIT/)).toBeTruthy();
	});

	it('setelah fetch → tampilkan sentinel LAYA', async () => {
		render(ForexCockpitExness);
		await waitFor(() => {
			expect(document.body.textContent).toContain('LAYA AI SENTINEL');
		});
	});

	it('fetch gagal → tetap render tanpa crash', async () => {
		vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('offline'))));
		render(ForexCockpitExness);
		// Judul tetap tampil meski data gagal
		expect(await screen.findByText(/EXNESS MT5 ALGO COCKPIT/)).toBeTruthy();
	});
});
