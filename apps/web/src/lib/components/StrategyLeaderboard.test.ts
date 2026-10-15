import { describe, expect, it } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/svelte';
import StrategyLeaderboard from './StrategyLeaderboard.svelte';
import type { LeaderboardStrategy, LeaderboardPayload } from '$lib/api/types';

const strategiSMC: LeaderboardStrategy = {
	rank: 1,
	id: 'strat-smc',
	nama: 'Crypto SMC Trend',
	venue: 'Binance / OKX',
	pasar: 'crypto',
	tipe: 'PAPER',
	ekuitas: 24.50,
	modal_awal: 20.0,
	winrate_pct: 66.7,
	total_r: 3.84,
	expectancy_r: 0.64,
	n_samples: 6,
	max_dd_r: -1.2,
	total_fee: 0.08,
	status_operasional: 'AKTIF',
	alasan_status: null,
	setup_status: 'RUNNING',
	setup_terakhir: {
		setup_id: 'smc-1',
		pair: 'SOL/USDT',
		status: 'RUNNING',
		arah: 'LONG',
		entry: 135.2,
		tp: 148.0,
		sl: 130.5
	},
	rekonsiliasi: {
		status: 'SEIMBANG',
		saldo: 24.50,
		modal_awal: 20.0,
		realized_pnl: 4.58,
		total_fee: 0.08,
		selisih: 0.0,
		catatan: 'Formula seimbang: $20.00 + $4.58 - $0.08 = $24.50'
	},
	friksi_est_pct: 0.1
};

const strategiBenched: LeaderboardStrategy = {
	rank: 2,
	id: 'strat-poly',
	nama: 'Polymarket Favorit B',
	venue: 'Polymarket CTF',
	pasar: 'polymarket',
	tipe: 'PAPER',
	ekuitas: 19.80,
	modal_awal: 20.0,
	winrate_pct: 45.0,
	total_r: -0.5,
	expectancy_r: -0.1,
	n_samples: 12,
	max_dd_r: -2.0,
	total_fee: 0.25,
	status_operasional: 'BENCHED',
	alasan_status: 'Batas fee harian terlampaui',
	setup_status: 'WAITING',
	setup_terakhir: {
		setup_id: 'poly-1',
		pair: 'US-ELECTION',
		status: 'WAITING',
		arah: 'BUY',
		entry: 0.72,
		tp: 0.95,
		sl: null
	},
	rekonsiliasi: {
		status: 'SELISIH',
		saldo: 19.80,
		modal_awal: 20.0,
		realized_pnl: 0.10,
		total_fee: 0.25,
		selisih: 0.05,
		catatan: 'Ada selisih pembulatan $0.05'
	},
	friksi_est_pct: 0.1
};

const payloadUji: LeaderboardPayload = {
	diperbarui_pada: '2026-10-15T20:00:00Z',
	total_strategi: 2,
	strategi: [strategiSMC, strategiBenched],
	rekonsiliasi_global: {
		seimbang: false,
		total_selisih: 0.05
	}
};

describe('StrategyLeaderboard', () => {
	it('menampilkan EmptyState ketika tidak ada strategi terdata', () => {
		render(StrategyLeaderboard, { props: { strategies: [] } });
		expect(screen.getByTestId('empty-state')).toBeInTheDocument();
		expect(screen.getByText('Belum ada data strategi yang memenuhi kriteria')).toBeInTheDocument();
	});

	it('menampilkan strategi dengan identitas, metrik, status setup, dan rekonsiliasi', () => {
		render(StrategyLeaderboard, { props: { payload: payloadUji } });
		const container = screen.getByTestId('strategy-leaderboard');
		const teks = container.textContent ?? '';

		// Identitas
		expect(teks).toContain('Crypto SMC Trend');
		expect(teks).toContain('Polymarket Favorit B');
		expect(teks).toContain('PAPER');
		expect(teks.toLowerCase()).toContain('crypto');
		expect(teks.toLowerCase()).toContain('polymarket');

		// Status setup
		expect(teks).toContain('RUNNING');
		expect(teks).toContain('WAITING');
		expect(teks).toContain('SOL/USDT');

		// Badge rekonsiliasi
		expect(teks).toContain('SEIMBANG');
		expect(teks).toContain('SELISIH $0,05');

		// Status operasional
		expect(teks).toContain('AKTIF');
		expect(teks).toContain('BENCHED');

		// Nilai metrik
		expect(teks).toContain('66,7%');
		expect(teks).toContain('+0,64R');
		expect(teks).toContain('$24,50');
	});

	it('menangani nilai null secara jujur dengan dash tanpa angka karangan', () => {
		const strategiNull: LeaderboardStrategy = {
			rank: 1,
			id: 'strat-null',
			nama: 'Strategi Pengujian Murni',
			venue: 'Hyperliquid',
			pasar: 'crypto',
			tipe: 'RESEARCH',
			ekuitas: null,
			modal_awal: null,
			winrate_pct: null,
			total_r: null,
			expectancy_r: null,
			n_samples: 0,
			total_fee: null,
			status_operasional: 'AKTIF',
			setup_status: null,
			rekonsiliasi: {
				status: 'BELUM_DIVERIFIKASI',
				saldo: null,
				modal_awal: null,
				realized_pnl: null,
				total_fee: null,
				selisih: null
			}
		};

		render(StrategyLeaderboard, { props: { strategies: [strategiNull] } });
		const teks = screen.getByTestId('strategy-leaderboard').textContent ?? '';
		expect(teks).toContain('BELUM DIVERIFIKASI');
		expect(teks).toContain('—');
	});

	it('dapat membuka rincian buku rekonsiliasi dan detail setup', async () => {
		render(StrategyLeaderboard, { props: { payload: payloadUji } });
		const tombolRincian = screen.getAllByText('Rincian');
		expect(tombolRincian.length).toBeGreaterThan(0);

		await fireEvent.click(tombolRincian[0]);
		const teks = screen.getByTestId('strategy-leaderboard').textContent ?? '';
		expect(teks).toContain('Buku Rekonsiliasi');
		expect(teks).toContain('Daur Hidup Setup');
		expect(teks).toContain('Modal Awal:');
		expect(teks).toContain('$20,00');
		expect(teks).toContain('Realized PnL:');
		expect(teks).toContain('+$4,58');
		expect(teks).toContain('Total Fee (0.1%/sisi):');
		expect(teks).toContain('$0,08');
	});

	it('memfilter baris strategi berdasarkan pasar', async () => {
		render(StrategyLeaderboard, { props: { payload: payloadUji } });
		expect(screen.getByText('Crypto SMC Trend')).toBeInTheDocument();
		expect(screen.getByText('Polymarket Favorit B')).toBeInTheDocument();

		const tombolCrypto = screen.getByRole('button', { name: 'crypto' });
		await fireEvent.click(tombolCrypto);

		expect(screen.getByText('Crypto SMC Trend')).toBeInTheDocument();
		expect(screen.queryByText('Polymarket Favorit B')).toBeNull();
	});

	it('memfilter baris strategi berdasarkan status operasional', async () => {
		render(StrategyLeaderboard, { props: { payload: payloadUji } });
		const tombolBenched = screen.getByRole('button', { name: 'benched' });
		await fireEvent.click(tombolBenched);

		expect(screen.queryByText('Crypto SMC Trend')).toBeNull();
		expect(screen.getByText('Polymarket Favorit B')).toBeInTheDocument();
	});

	it('menampilkan galat secara jujur lewat ErrorState', () => {
		render(StrategyLeaderboard, {
			props: { strategies: [], galat: 'HTTP 404: Endpoint /api/v1/leaderboard tidak ditemukan' }
		});
		expect(screen.getByTestId('error-state')).toBeInTheDocument();
		expect(screen.getByText('HTTP 404: Endpoint /api/v1/leaderboard tidak ditemukan')).toBeInTheDocument();
	});
});
