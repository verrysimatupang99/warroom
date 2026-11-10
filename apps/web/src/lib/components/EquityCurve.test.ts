import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import EquityCurve from './EquityCurve.svelte';

describe('EquityCurve', () => {
	it('render judul perkembangan hasil', () => {
		render(EquityCurve, { props: { points: [], stats: null } });
		expect(screen.getByText(/Perkembangan Hasil/)).toBeTruthy();
	});

	it('grafik punya aria-label kurva ekuitas (butuh cukup points)', () => {
		// SVG grafik hanya dirender bila points memenuhi syarat minimal (>=5).
		const points = Array.from({ length: 6 }, (_, i) => ({ i, r: i * 0.5 }));
		render(EquityCurve, { props: { points, stats: { total_r: 3.7, trades: 6 } } });
		expect(screen.getByLabelText(/Grafik kurva ekuitas/)).toBeTruthy();
	});

	it('points terisi → render tanpa crash', () => {
		render(EquityCurve, {
			props: {
				points: [
					{ i: 0, r: 0 },
					{ i: 1, r: 1.5 },
					{ i: 2, r: 2.2 }
				],
				stats: { total_r: 3.7, trades: 3 }
			}
		});
		expect(screen.getByText(/Perkembangan Hasil/)).toBeTruthy();
	});
});
