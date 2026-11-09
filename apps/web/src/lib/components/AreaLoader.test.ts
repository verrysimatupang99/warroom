import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import { createRawSnippet } from 'svelte';
import AreaLoader from './AreaLoader.svelte';
import type { AreaPayload } from '$lib/api/types';

// Mock getArea: AreaLoader memanggil endpoint area lewat modul ini. Kita kendalikan
// balikannya per-test (sukses / galat / area tak dikenal) tanpa jaringan sungguhan.
const getAreaMock = vi.fn();
vi.mock('$lib/api/client', () => ({ getArea: (area: string) => getAreaMock(area) }));

// Children snippet menerima payload dari AreaLoader; render penandanya.
// Svelte 5 meneruskan arg snippet sebagai getter, jadi akses via payload().
const children = createRawSnippet<[AreaPayload]>((payload) => ({
	render: () => {
		const p = payload();
		return `<p data-testid="isi">${p.dikenal ? 'dikenal' : 'tak-dikenal'}:${p.area}</p>`;
	},
	setup: () => {}
}));

const payloadDikenal: AreaPayload = {
	area: 'crypto',
	dikenal: true,
	facts: [],
	data: {}
};

beforeEach(() => {
	getAreaMock.mockReset();
});

describe('AreaLoader', () => {
	it('area dikenal → render children dengan payload', async () => {
		getAreaMock.mockResolvedValue(payloadDikenal);
		render(AreaLoader, { props: { area: 'crypto', children } });
		// Children dirender saat payload dikenal (cukup pastikan elemennya ada).
		const el = await screen.findByTestId('isi');
		expect(el).toBeTruthy();
	});

	it('area tidak dikenal → EmptyState "Area tidak dikenal"', async () => {
		getAreaMock.mockResolvedValue({ ...payloadDikenal, dikenal: false, areas: ['crypto', 'forex'] });
		render(AreaLoader, { props: { area: 'areaaneh', children } });
		const el = await screen.findByText(/Area tidak dikenal/);
		expect(el).toBeTruthy();
		// Saran area yang ada ikut ditampilkan (lewat langkah EmptyState)
		expect(await screen.findByText(/crypto, forex/)).toBeTruthy();
	});

	it('getArea melempar → ErrorState dengan pesan', async () => {
		getAreaMock.mockRejectedValue(new Error('jaringan putus'));
		render(AreaLoader, { props: { area: 'crypto', children } });
		const el = await screen.findByText(/jaringan putus/);
		expect(el).toBeTruthy();
	});

	it('sukses lalu refresh gagal → tetap tampil data terakhir + peringatan', async () => {
		getAreaMock.mockResolvedValueOnce(payloadDikenal).mockRejectedValueOnce(new Error('refresh gagal'));
		render(AreaLoader, { props: { area: 'crypto', intervalMs: 50, children } });
		// Tunggu load pertama sukses, lalu polling kedua gagal.
		await screen.findByTestId('isi');
		const peringatan = await screen.findByText(/refresh terakhir gagal/);
		expect(peringatan.textContent).toContain('refresh gagal');
		// Data terakhir tetap dirender, bukan kosong.
		expect(screen.getByTestId('isi')).toBeTruthy();
	});
});
