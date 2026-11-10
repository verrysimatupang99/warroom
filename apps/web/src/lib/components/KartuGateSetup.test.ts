import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import KartuGateSetup from './KartuGateSetup.svelte';

describe('KartuGateSetup', () => {
	it('render judul default', () => {
		render(KartuGateSetup, { props: { blok: null } });
		expect(screen.getByText(/Gate live-trading/)).toBeTruthy();
	});

	it('render judul kustom bila diset', () => {
		render(KartuGateSetup, { props: { blok: null, judul: 'Gate Crypto' } });
		expect(screen.getByText(/Gate Crypto/)).toBeTruthy();
	});

	it('blok dengan per_setup → render tanpa crash', () => {
		render(KartuGateSetup, {
			props: {
				blok: {
					per_setup: { momentum: { n: 40, winrate_pct: 60 } },
					tuntas: 40,
					belum_tuntas: 5,
					sumber: 'ledger'
				},
				judul: 'Gate Crypto'
			}
		});
		expect(screen.getByText(/Gate Crypto/)).toBeTruthy();
	});
});
