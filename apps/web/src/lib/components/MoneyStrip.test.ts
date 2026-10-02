import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import MoneyStrip from './MoneyStrip.svelte';

describe('MoneyStrip', () => {
	it('punya 3 segmen PERMANEN: Nyata, Paper, Warisan', () => {
		const { container } = render(MoneyStrip, { props: {} });
		expect(screen.getByText('Nyata')).toBeInTheDocument();
		expect(screen.getByText('Paper')).toBeInTheDocument();
		expect(screen.getByText('Warisan')).toBeInTheDocument();
		expect(container.querySelectorAll('[data-segmen]').length).toBe(3);
	});

	it('tanpa nilai → `—` + alasan, bukan 0', () => {
		const { container } = render(MoneyStrip, { props: {} });
		const nyata = container.querySelector('[data-segmen="nyata"]')?.textContent ?? '';
		expect(nyata).toContain('—');
		expect(nyata).toContain('belum ada dana terverifikasi on-chain');
	});

	it('menampilkan nilai paper apa adanya (id-ID)', () => {
		render(MoneyStrip, {
			props: { paper: { nilai: 3.84, satuan: 'R', sumber: 'state/snapshot.json', age_s: 600, status: 'segar' } }
		});
		const t = screen.getByTestId('money-strip').textContent ?? '';
		expect(t).toContain('3,84');
		expect(t).toContain('R');
		expect(t).toContain('state/snapshot.json');
	});

	it('tidak pernah mencampur segmen: tiap nilai punya segmen sendiri', () => {
		const { container } = render(MoneyStrip, {
			props: { nyata: { nilai: 100 }, paper: { nilai: 200 }, warisan: { nilai: 300 } }
		});
		expect(container.querySelector('[data-segmen="nyata"]')?.textContent).toContain('100,00');
		expect(container.querySelector('[data-segmen="paper"]')?.textContent).toContain('200,00');
		expect(container.querySelector('[data-segmen="warisan"]')?.textContent).toContain('300,00');
	});
});