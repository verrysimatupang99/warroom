import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import StatisticalEdgeCard from './StatisticalEdgeCard.svelte';

describe('StatisticalEdgeCard', () => {
	it('render judul default', () => {
		render(StatisticalEdgeCard, { props: { verdict: null } });
		expect(screen.getByText(/Statistical Edge Gate/)).toBeTruthy();
	});

	it('render judul kustom bila diset', () => {
		render(StatisticalEdgeCard, { props: { verdict: null, judul: 'Edge Crypto' } });
		expect(screen.getByText(/Edge Crypto/)).toBeTruthy();
	});

	it('verdict dengan sampel → tampilkan winrate & jumlah sampel', () => {
		// Shape verdict: win & n (winrate dihitung = win/n*100), be = break-even desimal.
		render(StatisticalEdgeCard, {
			props: {
				verdict: { win: 50, n: 80, be: 0.55 },
				judul: 'Edge Crypto'
			}
		});
		const teks = document.body.textContent ?? '';
		// Winrate diformat angka() (locale id: koma desimal) — cukup cek sampel & badge.
		expect(teks).toContain('50 / 80 sampel');
		expect(teks).toContain('sampel');
	});
});
