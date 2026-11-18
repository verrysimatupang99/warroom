import { describe, expect, it, vi, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/svelte';
import QuantStrategyCard from './QuantStrategyCard.svelte';

const mockLeaderboard = {
	diperbarui_pada: '2026-10-15T12:00:00Z',
	total_strategi: 2,
	strategi: [
		{
			rank: 1,
			id: 'LIVE_GOLD_M5',
			nama: 'Live Gold M5 Scalper',
			venue: 'Exness Cent',
			pasar: 'forex',
			tipe: 'LIVE',
			ekuitas: 1074.81,
			winrate_pct: 58.5,
			total_r: 4.8,
			expectancy_r: 0.85,
			n_samples: 42,
			max_dd_pct: 1.85,
			total_fee: 0.5,
			status_operasional: 'AKTIF',
			rekonsiliasi: {
				status: 'SEIMBANG',
				saldo: 1074.81,
				modal_awal: 1000.0,
				realized_pnl: 74.81,
				total_fee: 0.5,
				selisih: 0
			}
		},
		{
			rank: 2,
			id: 'LIVE_SOL_M15',
			nama: 'Live Solana Momentum',
			venue: 'Binance Paper',
			pasar: 'crypto',
			tipe: 'PAPER',
			ekuitas: 520.0,
			winrate_pct: 45.0,
			total_r: 8.2,
			expectancy_r: 1.15,
			n_samples: 28,
			max_dd_pct: 3.2,
			total_fee: 0.2,
			status_operasional: 'AKTIF',
			rekonsiliasi: {
				status: 'SEIMBANG',
				saldo: 520.0,
				modal_awal: 500.0,
				realized_pnl: 20.0,
				total_fee: 0.2,
				selisih: 0
			}
		}
	]
};

const mockRuns = {
	count: 3,
	runs: [
		{
			id: 'run-001',
			research_key: 'breakout-m5',
			hypothesis_id: 'hypo-1',
			hypothesis_version: 'v1.0',
			hypothesis_hash: 'hash1',
			execution_hash: 'exehash1',
			status: 'completed',
			created_at: '2026-10-14T10:00:00Z',
			completed_at: '2026-10-14T10:05:00Z'
		}
	]
};

function stubApis(withData = true) {
	return vi.fn((url: string) => {
		if (url.includes('/api/v1/leaderboard')) {
			return Promise.resolve({
				ok: true,
				json: () => Promise.resolve(withData ? mockLeaderboard : { total_strategi: 0, strategi: [] })
			} as Response);
		}
		if (url.includes('/api/v1/research/runs')) {
			return Promise.resolve({
				ok: true,
				json: () => Promise.resolve(withData ? mockRuns : { count: 0, runs: [] })
			} as Response);
		}
		return Promise.resolve({ ok: true, json: () => Promise.resolve({}) } as Response);
	});
}

describe('QuantStrategyCard', () => {
	afterEach(() => {
		vi.unstubAllGlobals();
		vi.restoreAllMocks();
	});

	it('mengambil data live dari client API endpoints (FE-04 / US-10)', async () => {
		vi.stubGlobal('fetch', stubApis(true));
		render(QuantStrategyCard);

		await waitFor(() => {
			expect(screen.getByText(/LIVE API/)).toBeTruthy();
		});

		expect(document.body.textContent).toContain('Live Gold M5 Scalper');
		expect(document.body.textContent).toContain('LIVE_GOLD_M5');
		expect(document.body.textContent).toContain('Live Solana Momentum');
	});

	it('graceful fallback saat backend memiliki 0 runs / data kosong', async () => {
		vi.stubGlobal('fetch', stubApis(false));
		render(QuantStrategyCard);

		await waitFor(() => {
			expect(screen.getByText(/FALLBACK BASELINE/)).toBeTruthy();
		});

		// Fallback baseline assets tetap tampil
		expect(document.body.textContent).toContain('XAUUSD');
		expect(document.body.textContent).toContain('BTCUSDT');
		expect(document.body.textContent).toContain('SOLUSDT');
	});
});
