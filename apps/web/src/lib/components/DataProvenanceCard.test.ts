import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import DataProvenanceCard from './DataProvenanceCard.svelte';

describe('DataProvenanceCard', () => {
	it('render label sumber terverifikasi + pasar', () => {
		render(DataProvenanceCard, { props: { pasar: 'crypto', sumber: 'OKX' } });
		expect(screen.getByText(/SUMBER DATA TERVERIFIKASI · CRYPTO/)).toBeTruthy();
		expect(screen.getByText('OKX')).toBeTruthy();
	});

	it('render keterangan default', () => {
		render(DataProvenanceCard, { props: { pasar: 'forex', sumber: 'TVC' } });
		expect(screen.getByText(/Feed resmi terhubung langsung/)).toBeTruthy();
	});

	it('render frekuensi & metode bila diset', () => {
		render(
			DataProvenanceCard,
			{
				props: {
					pasar: 'idx',
					sumber: 'Stock Arjum',
					frekuensi: 'Harian',
					metode: 'REST snapshot'
				}
			}
		);
		const teks = document.body.textContent ?? '';
		expect(teks).toContain('Harian');
		expect(teks).toContain('REST snapshot');
	});

	it('tautan diset → tetap render kartu (tautan tidak dirender sebagai link)', () => {
		// DataProvenanceCard menerima prop tautan tetapi tidak merendernya sebagai <a>;
		// yang tampil adalah badge sumber + keterangan. Pastikan kartu tetap utuh.
		render(
			DataProvenanceCard,
			{ props: { pasar: 'polymarket', sumber: 'Dokumentasi PM', tautan: 'https://docs.pm' } }
		);
		expect(screen.getByText(/SUMBER DATA TERVERIFIKASI · POLYMARKET/)).toBeTruthy();
		expect(screen.getByText('Dokumentasi PM')).toBeTruthy();
	});
});
