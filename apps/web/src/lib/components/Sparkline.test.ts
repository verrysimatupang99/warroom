import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import Sparkline from './Sparkline.svelte';

describe('Sparkline', () => {
	it('TIDAK dirender bila tidak ada seri', () => {
		render(Sparkline, { props: { seri: null } });
		expect(screen.queryByTestId('sparkline')).toBeNull();
	});

	it('TIDAK dirender bila seri hanya 1 titik', () => {
		render(Sparkline, { props: { seri: [5] } });
		expect(screen.queryByTestId('sparkline')).toBeNull();
	});

	it('merender path SVG bila seri >= 2 titik', () => {
		const { container } = render(Sparkline, { props: { seri: [1, 2, 3], isi: true } });
		expect(screen.getByTestId('sparkline')).toBeInTheDocument();
		const d = container.querySelector('path')?.getAttribute('d') ?? '';
		expect(d.startsWith('M')).toBe(true);
	});

	it('seri yang seluruhnya non-finit → tidak dirender', () => {
		render(Sparkline, { props: { seri: [Number.NaN, Number.POSITIVE_INFINITY] } });
		expect(screen.queryByTestId('sparkline')).toBeNull();
	});

	it('titik non-finit dibuang dari lintasan (3 nilai → 2 titik)', () => {
		const { container } = render(Sparkline, { props: { seri: [1, Number.NaN, 3] } });
		expect(screen.getByTestId('sparkline')).toBeInTheDocument();
		const d = container.querySelector('path')?.getAttribute('d') ?? '';
		// 2 titik = satu segmen `L`
		expect((d.match(/L/g) ?? []).length).toBe(1);
	});
});