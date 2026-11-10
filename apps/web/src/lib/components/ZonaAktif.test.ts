import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import ZonaAktif from './ZonaAktif.svelte';

describe('ZonaAktif', () => {
	it('render judul default', () => {
		render(ZonaAktif, { props: { blok: null } });
		expect(screen.getByText(/Zona & Sinyal Mesin \(Forex\)/)).toBeTruthy();
	});

	it('render judul kustom bila diset', () => {
		render(ZonaAktif, { props: { blok: null, judul: 'Zona Crypto' } });
		expect(screen.getByText(/Zona Crypto/)).toBeTruthy();
	});

	it('blok dengan entries → render tanpa crash', () => {
		render(ZonaAktif, {
			props: {
				blok: {
					entries: [{ pair: 'XAUUSD', arah: 'BUY' }],
					sumber: 'ledger',
					tersedia: true,
					alasan: null
				},
				judul: 'Zona Crypto'
			}
		});
		expect(screen.getByText(/Zona Crypto/)).toBeTruthy();
	});
});
