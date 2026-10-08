import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import SignalCard from './SignalCard.svelte';

describe('SignalCard', () => {
	it('merender SHORT saat field direction="SHORT" (meskipun tanpa field arah)', () => {
		render(SignalCard, {
			props: {
				setup: {
					pair: 'ORDIUSDT',
					direction: 'SHORT',
					entry: 4.587,
					sl: 4.661,
					tp1: 4.513
				}
			}
		});

		const text = screen.getByText('SHORT');
		expect(text).toBeTruthy();
		// Memastikan badge berkelas text-neg (merah), bukan text-pos
		expect(text.className).toContain('text-neg');
		// Tidak boleh ada warning anomali karena TP 4.513 < Entry 4.587 adalah valid SHORT
		expect(screen.queryByText(/Sisi TP Tidak Sesuai Arah/)).toBeNull();
	});

	it('merender LONG saat field arah="LONG" dan mendeteksi anomali jika TP < Entry', () => {
		render(SignalCard, {
			props: {
				setup: {
					pair: 'ORDIUSDT',
					arah: 'LONG',
					entry: 4.587,
					sl: 4.661,
					tp1: 4.513 // TP lebih rendah dari entry padahal LONG -> Anomali!
				}
			}
		});

		const text = screen.getByText('LONG');
		expect(text).toBeTruthy();
		expect(text.className).toContain('text-pos');
		// Menampilkan warning badge anomali
		expect(screen.getByText(/Sisi TP Tidak Sesuai Arah/)).toBeTruthy();
	});

	it('merender rasio R:R dan jarak Stop Loss dengan benar', () => {
		render(SignalCard, {
			props: {
				setup: {
					pair: 'BTCUSDT',
					direction: 'LONG',
					entry: 100,
					sl: 90,
					tp1: 120
				}
			}
		});

		// Risk = 10, Reward = 20 -> 1:2.0 R:R
		expect(screen.getByText('1:2.0 R:R')).toBeTruthy();
		// SL distance = (10 / 100) * 100 = 10.00%
		expect(screen.getByText('(10.00%)')).toBeTruthy();
	});

	it('menampilkan mode dan strategi tanpa mengklaim live', () => {
		render(SignalCard, {
			props: {
				setup: {
					pair: 'BTCUSDT', direction: 'LONG', entry: 100, sl: 90, tp1: 120,
					mode: 'PAPER', strategy: 'smc-fibonacci-smart-golden-pullback-v1'
				}
			}
		});
		expect(screen.getByText(/PAPER · smc-fibonacci-smart-golden-pullback-v1/)).toBeTruthy();
	});
});
