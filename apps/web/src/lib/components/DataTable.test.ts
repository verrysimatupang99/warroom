import { describe, expect, it } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/svelte';
import DataTable from './DataTable.svelte';

const kolom = [
	{ kunci: 'pair', label: 'pair' },
	{ kunci: 'r', label: 'r', numerik: true }
];
const baris = [
	{ pair: 'B', r: 2 },
	{ pair: 'A', r: 1 }
];

describe('DataTable', () => {
	it('merender baris + hitungan', () => {
		render(DataTable, { props: { kolom, baris } });
		expect(screen.getByText('B')).toBeInTheDocument();
		expect(screen.getByText('A')).toBeInTheDocument();
		expect(screen.getByText('2/2 baris')).toBeInTheDocument();
	});

	it('sort lewat header mengubah urutan', async () => {
		const { container } = render(DataTable, { props: { kolom, baris } });
		await fireEvent.click(screen.getByRole('button', { name: /pair/ }));
		const pertama = container.querySelector('tbody tr td')?.textContent?.trim();
		expect(pertama).toBe('A');
	});

	it('filter menyaring baris', async () => {
		render(DataTable, { props: { kolom, baris } });
		const cari = screen.getByRole('searchbox');
		await fireEvent.input(cari, { target: { value: 'B' } });
		expect(screen.queryByText('A')).toBeNull();
		expect(screen.getByText('B')).toBeInTheDocument();
	});

	it('tabel kosong → EmptyState', () => {
		render(DataTable, { props: { kolom, baris: [] } });
		expect(screen.getByTestId('empty-state')).toBeInTheDocument();
	});

	it('menampilkan tombol ekspor bila diminta', () => {
		render(DataTable, { props: { kolom, baris, ekspor: 'uji.csv' } });
		expect(screen.getByText('Ekspor CSV')).toBeInTheDocument();
	});
});