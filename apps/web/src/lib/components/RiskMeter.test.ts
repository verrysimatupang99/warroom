import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import RiskMeter from './RiskMeter.svelte';

const risiko = {
	mode: 'PAPER',
	venue: 'OKX',
	equity_usd: 53945.46,
	hari_ini_r: 1.5,
	batas_rugi_r: 6,
	sisa_ruang_r: 4.5,
	posisi_terbuka: 3,
	maks_posisi: 5,
	total_trade: 128
};

describe('RiskMeter', () => {
	it('render judul batas risiko', () => {
		render(RiskMeter, { props: { risiko } });
		expect(screen.getByText(/Batas Risiko & Kapasitas/)).toBeTruthy();
	});

	it('tampilkan mode dan venue', () => {
		render(RiskMeter, { props: { risiko } });
		const teks = document.body.textContent ?? '';
		expect(teks).toContain('Mode: PAPER');
		// RiskMeter menampilkan mode; venue ditampilkan CockpitCrypto, bukan di sini.
	});

	it('tampilkan risiko terpakai hari ini (R / Max)', () => {
		render(RiskMeter, { props: { risiko } });
		const teks = document.body.textContent ?? '';
		expect(teks).toContain('Risiko Terpakai Hari Ini');
		expect(teks).toContain('R Max');
	});

	it('risiko null → tetap render dengan default Paper', () => {
		render(RiskMeter, { props: { risiko: null } });
		const teks = document.body.textContent ?? '';
		expect(teks).toContain('Batas Risiko & Kapasitas');
		expect(teks).toContain('Mode: Paper');
	});
});
