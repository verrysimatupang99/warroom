import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import GateMeter from './GateMeter.svelte';
import type { GateResult } from '$lib/api/types';

const hasil: GateResult = {
	verdict: 'gagal',
	reason: 'batas bawah CI (76,96%) belum melewati BE (77,00%)',
	ci_low: 0.7696,
	ci_high: 0.83,
	win_rate: 0.79,
	be: 0.77,
	n: 1175,
	required_n: 1219,
	policy_version: 'gate-1',
	notes: []
};

describe('GateMeter', () => {
	it('menampilkan verdict, n ATAU n dibutuhkan, dan sisa', () => {
		render(GateMeter, { props: { hasil } });
		const t = screen.getByTestId('gate-meter').textContent ?? '';
		expect(t).toContain('gagal');
		expect(t).toContain('1.219');
		expect(t).toContain('butuh 44 lagi');
		expect(t).toContain('gate-1');
	});

	it('menampilkan pita CI dan garis BE sebagai persen', () => {
		render(GateMeter, { props: { hasil } });
		const t = screen.getByTestId('gate-meter').textContent ?? '';
		expect(t).toContain('76,96%');
		expect(t).toContain('77,00%');
	});

	it('required_n null → n/a (bukan angka karangan)', () => {
		render(GateMeter, { props: { hasil: { ...hasil, required_n: null } } });
		const t = screen.getByTestId('gate-meter').textContent ?? '';
		expect(t).toContain('n/a');
	});

	it('tanpa hasil → EmptyState', () => {
		render(GateMeter, { props: { hasil: null } });
		expect(screen.getByTestId('empty-state')).toBeInTheDocument();
	});

	it('galat ditampilkan + tombol ulang', () => {
		render(GateMeter, { props: { hasil: null, galat: 'HTTP 503', onulang: () => {} } });
		expect(screen.getByTestId('error-state').textContent).toContain('HTTP 503');
		expect(screen.getByText('Coba lagi')).toBeInTheDocument();
	});
});