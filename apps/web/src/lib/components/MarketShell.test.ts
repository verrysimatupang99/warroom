import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import { createRawSnippet } from 'svelte';
import MarketShell from './MarketShell.svelte';
import type { Area } from '$lib/nav';

// MarketShell memakai goto() dari $app/navigation (alias SvelteKit) yang tak
// tersedia di lingkungan vitest — mock agar komponen bisa dirender mandiri.
vi.mock('$app/navigation', () => ({ goto: () => {} }));

const area: Area = {
	kunci: 'crypto',
	label: 'Crypto',
	rute: '/crypto',
	ikon: 'chart',
	kategori: 'pasar',
	status: 'PAPER',
	anak: [
		{ slug: 'ringkas', label: 'Ringkas', kunci: ['bagian'], catatan: 'Status' },
		{ slug: 'sinyal', label: 'Sinyal', kunci: ['sinyal'], catatan: 'Sinyal aktif' }
	]
};

const anak = createRawSnippet(() => ({
	render: () => '<p data-testid="isi-anak">Konten isi pasar</p>',
	setup: () => {}
}));

describe('MarketShell', () => {
	it('render kepala (judul) + sub-nav + children', () => {
		render(MarketShell, {
			props: { area, aktif: 'ringkas', judul: 'Crypto', children: anak }
		});
		// Kepala halaman tampil dengan judul
		expect(screen.getByTestId('page-header').textContent).toContain('Crypto');
		// Sub-nav tampil karena area.anak.length > 0
		expect(screen.getByRole('navigation').getAttribute('aria-label')).toContain('Crypto');
		// Children dirender
		expect(screen.getByTestId('isi-anak').textContent).toContain('Konten isi pasar');
	});

	it('tanpaKepala → kepala tidak dirender, children tetap tampil', () => {
		render(MarketShell, {
			props: { area, aktif: 'ringkas', judul: 'Crypto', tanpaKepala: true, children: anak }
		});
		expect(screen.queryByTestId('page-header')).toBeNull();
		// Children tetap dirender meski kepala disembunyikan
		expect(screen.getByTestId('isi-anak')).toBeTruthy();
	});

	it('area tanpa anak → sub-nav tidak dirender', () => {
		const areaKosong: Area = { ...area, anak: [] };
		render(MarketShell, {
			props: { area: areaKosong, aktif: 'ringkas', judul: 'Crypto', children: anak }
		});
		expect(screen.getByTestId('page-header')).toBeTruthy();
		expect(screen.queryByRole('navigation')).toBeNull();
		expect(screen.getByTestId('isi-anak')).toBeTruthy();
	});
});
