import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/svelte';
import ForexCockpitExness from './ForexCockpitExness.svelte';

const mt5 = {
	connected: true,
	account: '452009427',
	broker: 'Exness Technologies Ltd',
	currency: 'USC',
	balance: 1095.44,
	equity: 1095.44,
	floating_pnl: 0,
	margin: 0,
	free_margin: 1095.44,
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

const signal = { symbol: 'XAUUSD', bias: 'BUY', status: 'OK', price: 2650.0, rrr: 2.0, levels: { entry: 2650, sl: 2640, tp1: 2670, tp2: 2690, risk: 10, reward: 20 } };

class MockEventSource {
	url: string;
	onopen: (() => void) | null = null;
	onmessage: ((ev: { data: string }) => void) | null = null;
	onerror: ((ev: any) => void) | null = null;
	static instances: MockEventSource[] = [];

	constructor(url: string) {
		this.url = url;
		MockEventSource.instances.push(this);
	}
	close() {}
}

function stubFetch(ok = true) {
	return vi.fn((url: string) => {
		const body = url.includes('mt5/status') ? mt5 : url.includes('sentinel') ? sentinel : signal;
		return Promise.resolve({ ok, json: () => Promise.resolve(body) } as Response);
	});
}

beforeEach(() => {
	MockEventSource.instances = [];
	vi.stubGlobal('fetch', stubFetch(true));
	vi.stubGlobal('EventSource', MockEventSource);
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

	it('tampilkan badge CENT dan format USC untuk akun cent', async () => {
		const centMt5 = {
			...mt5,
			account: '452009427',
			currency: 'USC',
			balance: 1074.81,
			equity: 1074.81,
			floating_pnl: 0,
			seconds_ago: 2
		};
		vi.stubGlobal('fetch', vi.fn((url: string) => {
			const body = url.includes('mt5/status') ? centMt5 : url.includes('sentinel') ? sentinel : signal;
			return Promise.resolve({ ok: true, json: () => Promise.resolve(body) } as Response);
		}));

		render(ForexCockpitExness);
		expect(await screen.findByText('CENT')).toBeTruthy();
		expect(await screen.findByText('#452009427')).toBeTruthy();
		expect(await screen.findAllByText(/1074.81 USC/)).toBeTruthy();
	});

	it('fetch gagal → tampilkan banner galat visual dan tombol coba lagi (FE-02 / US-08)', async () => {
		vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('Koneksi jaringan terputus'))));
		render(ForexCockpitExness);
		// Judul tetap tampil meski data gagal
		expect(await screen.findByText(/EXNESS MT5 ALGO COCKPIT/)).toBeTruthy();
		// Banner galat visual dan tombol retry tampil
		expect(await screen.findByRole('alert')).toBeTruthy();
		expect(screen.getByText(/Gagal memuat telemetri forex/)).toBeTruthy();
		expect(screen.getByText('Coba Lagi')).toBeTruthy();
	});

	it('berlangganan SSE stream GET /api/v1/tencent/forex/stream dan update live real-time (FE-01 / US-07)', async () => {
		render(ForexCockpitExness);

		await waitFor(() => {
			expect(MockEventSource.instances.length).toBeGreaterThan(0);
		});

		const es = MockEventSource.instances[0];
		expect(es.url).toContain('/api/v1/tencent/forex/stream?account=452009427');

		// Simulasikan koneksi tersambung
		es.onopen?.();
		await waitFor(() => {
			expect(document.body.textContent).toContain('LIVE STREAM');
		});

		// Kirim packet telemetri SSE live
		const livePacket = {
			account: '452009427',
			currency: 'USC',
			balance: 1250.75,
			equity: 1280.00,
			bid: 2665.40,
			ask: 2665.70,
			positions: [
				{
					ticket: 88812,
					symbol: 'XAUUSD',
					type: 'BUY',
					volume: 0.1,
					open_price: 2660.0,
					current_price: 2665.4,
					pnl: 54.0
				}
			]
		};

		es.onmessage?.({ data: JSON.stringify(livePacket) });

		await waitFor(() => {
			expect(document.body.textContent).toContain('BID: $2665.40 / ASK: $2665.70');
			expect(document.body.textContent).toContain('1250.75 USC');
			expect(document.body.textContent).toContain('1280.00 USC');
			expect(document.body.textContent).toContain('#88812');
		});
	});
});
