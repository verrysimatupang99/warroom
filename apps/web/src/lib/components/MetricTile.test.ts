import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import MetricTile from './MetricTile.svelte';

describe('MetricTile', () => {
	it('memformat angka gaya id-ID (koma desimal, titik ribuan)', () => {
		render(MetricTile, { props: { label: 'total R', nilai: 1234.5, sumber: 'state/snapshot.json' } });
		const t = screen.getByTestId('metric-tile').textContent ?? '';
		expect(t).toContain('1.234,50');
		expect(t).toContain('state/snapshot.json');
	});

	it('nilai hilang → `—` + alasan, BUKAN 0', () => {
		render(MetricTile, { props: { label: 'posisi', nilai: null, alasanKosong: 'sumber belum mengirim nilai ini' } });
		const t = screen.getByTestId('metric-tile').textContent ?? '';
		expect(t).toContain('—');
		expect(t).not.toContain('0,00');
		expect(t).toContain('sumber belum mengirim nilai ini');
	});

	it('menampilkan satuan dan umur', () => {
		render(MetricTile, { props: { label: 'equity', nilai: 3.84, satuan: 'R', age_s: 600 } });
		const t = screen.getByTestId('metric-tile').textContent ?? '';
		expect(t).toContain('3,84');
		expect(t).toContain('R');
		expect(t).toContain('10m');
	});

	it('menampilkan sparkline hanya saat ada seri', () => {
		const { unmount } = render(MetricTile, { props: { label: 'kurva', nilai: 1, seri: [1, 2, 3] } });
		expect(screen.getByTestId('sparkline')).toBeInTheDocument();
		unmount();
		render(MetricTile, { props: { label: 'kurva', nilai: 1, seri: [] } });
		expect(screen.queryByTestId('sparkline')).toBeNull();
	});
});