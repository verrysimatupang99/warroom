import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import KurvaEkuitas from './KurvaEkuitas.svelte';

describe('KurvaEkuitas', () => {
	it('menggambar kurva dan menempelkan penanda trade', () => {
		render(KurvaEkuitas, {
			props: {
				deret: [
					{ t: '2026-10-30T08:00:00+00:00', equity: 1000 },
					{ t: '2026-10-30T08:05:00+00:00', equity: 1010 },
					{ t: '2026-10-30T08:10:00+00:00', equity: 1005 }
				],
				markers: [
					{ t: '2026-10-30 08:05:00', ticket: '9001', symbol: 'XAUUSDm', net_usd: 10 },
					{ t: '2026-10-30 08:10:00', ticket: '9002', symbol: 'XAUUSDm', net_usd: -5 }
				],
				drawdown_pct: 0.5
			}
		});
		expect(screen.getAllByTestId('marker-trade')).toHaveLength(2);
		expect(screen.getByText(/drawdown maks 0.50%/)).toBeInTheDocument();
		expect(screen.getByText(/2 penanda/)).toBeInTheDocument();
		expect(screen.getAllByText(/\+[$]10\.00/).length).toBeGreaterThan(0);
		expect(screen.getAllByText(/[$]-5\.00/).length).toBeGreaterThan(0);
	});

	it('menjelaskan saat titik belum cukup', () => {
		render(KurvaEkuitas, { props: { deret: [{ t: '2026-10-30T08:00:00Z', equity: 1000 }] } });
		expect(screen.getByText(/minimal 2 titik/)).toBeInTheDocument();
	});

	it('mengabaikan titik tanpa ekuitas', () => {
		render(KurvaEkuitas, {
			props: {
				deret: [
					{ t: 'a', equity: 1000 },
					{ t: 'b', equity: null },
					{ t: 'c', equity: 1010 }
				]
			}
		});
		expect(screen.getByRole('img')).toBeInTheDocument();
	});
});
