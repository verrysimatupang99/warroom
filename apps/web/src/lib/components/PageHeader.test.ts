import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import PageHeader from './PageHeader.svelte';

describe('PageHeader', () => {
	it('merender eyebrow, judul, tag, dan deskripsi dengan tepat', () => {
		render(PageHeader, {
			props: {
				eyebrow: 'OPERASI / SISTEM',
				title: 'Sistem & AI',
				tag: 'sistem',
				description: 'Unit lintas host, kesegaran, dan audit fakta.',
				terverifikasi: true,
				sumber: '/api/v1/health'
			}
		});

		const header = screen.getByTestId('page-header');
		expect(header.textContent).toContain('OPERASI / SISTEM');
		expect(header.textContent).toContain('Sistem & AI');
		expect(header.textContent).toContain('sistem');
		expect(header.textContent).toContain('Unit lintas host, kesegaran, dan audit fakta.');
		expect(header.textContent).toContain('TERUKUR');
	});

	it('merender status kejujuran belum terverifikasi secara eksplisit', () => {
		render(PageHeader, {
			props: {
				eyebrow: 'ANALITIK / LEADERBOARD',
				title: 'Leaderboard Strategi',
				terverifikasi: false,
				alasan: 'agregasi fakta mentah'
			}
		});

		const header = screen.getByTestId('page-header');
		expect(header.textContent).toContain('BELUM TERVERIFIKASI');
	});

	it('dapat merender tanpa tag opsional atau deskripsi', () => {
		render(PageHeader, {
			props: {
				eyebrow: 'INFORMASI / BERITA',
				title: 'Berita Pasar'
			}
		});

		const header = screen.getByTestId('page-header');
		expect(header.textContent).toContain('INFORMASI / BERITA');
		expect(header.textContent).toContain('Berita Pasar');
	});
});
