import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import KartuSinyalPasar from './KartuSinyalPasar.svelte';
import type { SinyalPasar } from '$lib/api/types';

function sinyal(ubah: Partial<SinyalPasar> = {}): SinyalPasar {
	return {
		pasar: 'crypto',
		label: 'Crypto (SMC)',
		ada: true,
		arah: 'LONG',
		subjek: 'SUIUSDT',
		skor: 100,
		tier: 'PREMIUM',
		alasan: '6/6 aturan lolos',
		terverifikasi: false,
		catatan_kejujuran: 'Skor = aturan yang lolos, BUKAN edge terbukti.',
		umur_s: 60,
		sumber_fakta: 'snapshot/kandidat',
		detail: { entry: 1.2088, sl: 1.18525, tp1: 1.23235, rr: 2.0 },
		...ubah
	};
}

describe('KartuSinyalPasar', () => {
	it('menampilkan skor dan arah untuk pasar yang ada', () => {
		render(KartuSinyalPasar, { props: { s: sinyal() } });
		expect(screen.getByText('SUIUSDT')).toBeTruthy();
		expect(screen.getByText('LONG')).toBeTruthy();
		expect(screen.getByText('100')).toBeTruthy();
	});

	it('WAJIB menampilkan catatan kejujuran selama belum terverifikasi', () => {
		// Ini aturan inti: klaim eksplorasi tidak boleh terlihat seperti edge terbukti.
		render(KartuSinyalPasar, { props: { s: sinyal({ terverifikasi: false }) } });
		expect(screen.getByText(/BUKAN edge terbukti/)).toBeTruthy();
	});

	it('menampilkan tanda terverifikasi saat split beku sudah ada', () => {
		render(KartuSinyalPasar, {
			props: {
				s: sinyal({
					terverifikasi: true,
					catatan_kejujuran: 'Split beku: frozen:poly-paired-abc'
				})
			}
		});
		expect(screen.getByText(/frozen:poly-paired-abc/)).toBeTruthy();
	});

	it('skor kosong ditampilkan "—", BUKAN 0', () => {
		// 0 adalah angka; "tidak ada" bukan. Ini pernah jadi kelas bug di repo.
		render(KartuSinyalPasar, { props: { s: sinyal({ skor: null }) } });
		expect(screen.getByText('—')).toBeTruthy();
		expect(screen.queryByText('0')).toBeNull();
	});

	it('pasar tanpa sinyal tetap tampil dengan alasannya', () => {
		render(KartuSinyalPasar, {
			props: {
				s: sinyal({
					pasar: 'idx',
					label: 'IDX (bandarmologi/BSJP)',
					ada: false,
					arah: null,
					subjek: null,
					skor: null,
					alasan: 'Belum ada posisi/sinyal IDX.'
				})
			}
		});
		expect(screen.getByText(/Belum ada posisi\/sinyal IDX/)).toBeTruthy();
	});

	it('tidak menampilkan metrik yang tidak ada di detail', () => {
		render(KartuSinyalPasar, { props: { s: sinyal({ detail: {} }) } });
		expect(screen.queryByText('Entry')).toBeNull();
	});
});
