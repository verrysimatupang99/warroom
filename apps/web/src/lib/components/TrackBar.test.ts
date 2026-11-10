import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import TrackBar from './TrackBar.svelte';

describe('TrackBar', () => {
	it('render label dan nilai/maks', () => {
		render(TrackBar, { props: { label: 'Posisi Terbuka', nilai: 3, maks: 5 } });
		const el = screen.getByTestId('track-bar');
		expect(el.textContent).toContain('Posisi Terbuka');
		expect(el.textContent).toContain('3');
		expect(el.textContent).toContain('/5');
	});

	it('nilai null → tampilkan tanda —', () => {
		render(TrackBar, { props: { label: 'Sinyal', nilai: null, maks: 5 } });
		const el = screen.getByTestId('track-bar');
		expect(el.textContent).toContain('Sinyal');
		expect(el.textContent).toContain('—');
	});

	it('tampilkan teks ambang bila diset', () => {
		render(TrackBar, {
			props: { label: 'Risiko', nilai: 2, maks: 6, ambang: 75, teksAmbang: 'AMBANG: 75' }
		});
		const el = screen.getByTestId('track-bar');
		expect(el.textContent).toContain('AMBANG: 75');
	});
});
