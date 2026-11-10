import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import KepalaVerdict from './KepalaVerdict.svelte';
import type { MarketVerdict } from '$lib/api/types';

// Fixture hanya mengisi field yang dipakai komponen (headline + 5 state);
// sisanya dipenuhi lewat cast agar tidak menulis 15 field tak relevan di tes.
const verdictLengkap = {
	headline: 'Crypto menunggu konfirmasi 4H',
	signal_state: 'kandidat',
	evidence_state: 'cukup',
	risk_state: 'aman',
	execution_state: 'siap',
	promotion_state: 'belum'
} as unknown as MarketVerdict;

describe('KepalaVerdict', () => {
	it('render headline dari verdict', () => {
		render(KepalaVerdict, { props: { verdict: verdictLengkap } });
		expect(screen.getByText(/Crypto menunggu konfirmasi 4H/)).toBeTruthy();
	});

	it('render kelima label state (Sinyal/Bukti/Risiko/Eksekusi/Boleh dipakai)', () => {
		render(KepalaVerdict, { props: { verdict: verdictLengkap } });
		const teks = document.body.textContent ?? '';
		for (const k of ['Sinyal', 'Bukti', 'Risiko', 'Eksekusi', 'Boleh dipakai']) {
			expect(teks).toContain(k);
		}
	});

	it('verdict null → tidak render apa pun (guard)', () => {
		render(KepalaVerdict, { props: { verdict: null } });
		expect(screen.queryByText(/Crypto menunggu/)).toBeNull();
	});
});
