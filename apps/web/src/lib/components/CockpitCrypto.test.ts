import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import CockpitCrypto from './CockpitCrypto.svelte';

const risikoPenuh = {
	mode: 'PAPER',
	venue: 'OKX',
	equity_usd: 53945.46,
	hari_ini_r: 1.2,
	batas_rugi_r: 6,
	sisa_ruang_r: 4.8,
	posisi_terbuka: 3,
	maks_posisi: 5,
	total_trade: 128
};

describe('CockpitCrypto', () => {
	it('render judul ringkasan', () => {
		render(CockpitCrypto, { props: { sinyal: null, risiko: risikoPenuh } });
		expect(screen.getByText(/Ringkasan Crypto/)).toBeTruthy();
	});

	it('risiko penuh → tampilkan mode·venue, equity, posisi', () => {
		render(CockpitCrypto, { props: { sinyal: null, risiko: risikoPenuh } });
		const teks = document.body.textContent ?? '';
		expect(teks).toContain('PAPER');
		expect(teks).toContain('OKX');
		expect(teks).toContain('trade tuntas');
		expect(teks).toContain('128');
		// posisi terbuka / maks posisi
		expect(teks).toContain('3');
		expect(teks).toContain('/5');
	});

	it('sinyal null → pesan belum tersedia', () => {
		render(CockpitCrypto, { props: { sinyal: null, risiko: risikoPenuh } });
		expect(screen.getByText(/Sinyal crypto belum tersedia/)).toBeTruthy();
	});

	it('sinyal aktif → tampilkan jumlah sinyal aktif', () => {
		const sinyal = {
			tersedia: true,
			aktif: [{ pair: 'BTCUSDT' }, { pair: 'ETHUSDT' }],
			jumlah_lolos: 2,
			jumlah_verdict: 10,
			alasan: null
		};
		render(CockpitCrypto, { props: { sinyal, risiko: risikoPenuh } });
		expect(screen.getByText(/Sinyal aktif \(2\)/)).toBeTruthy();
		expect(document.body.textContent).toContain('2 lolos');
		expect(document.body.textContent).toContain('10 dinilai');
	});
});
