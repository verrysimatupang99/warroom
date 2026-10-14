import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import DatasetExplorer from './DatasetExplorer.svelte';
import type { Fact } from '$lib/api/types';

function fakta(kind: string, key: string, value: unknown): Fact {
	return {
		fact_id: 1,
		kind,
		key,
		value,
		source: 'poly-sync',
		observed_at: '2026-10-03T12:40:53Z',
		ttl_s: 1800,
		age_s: 60,
		status: 'segar',
		hash: 'x'
	};
}

const recorder = fakta('poly.dataset', 'recorder', {
	paired: { path: '/var/lib/poly-research/paired', bytes: 6302064154, files: 2571, status: 'ok' },
	dataset: { path: '/var/lib/poly-research/dataset', bytes: 95001255, files: 6, status: 'ok' }
});

const cakupan = fakta('poly.akses', 'cakupan', {
	arm_jsonl: 'ok',
	agen_summary: 'tidak-izin',
	agen_lessons_n: 197
});

describe('DatasetExplorer', () => {
	it('menampilkan direktori, berkas, ukuran, dan status apa adanya', () => {
		render(DatasetExplorer, { props: { recorder, cakupan } });
		const t = screen.getByTestId('dataset-explorer').textContent ?? '';
		expect(t).toContain('paired');
		expect(t).toContain('2.571');
		expect(t).toContain('5,87 GB');
		expect(t).toContain('ok');
	});

	it('cakupan tidak-izin tampil sebagai label, bukan nol', () => {
		render(DatasetExplorer, { props: { recorder, cakupan } });
		const t = screen.getByTestId('dataset-explorer').textContent ?? '';
		expect(t).toContain('tidak-izin');
	});

	it('tanpa fakta → EmptyState', () => {
		render(DatasetExplorer, { props: { recorder: null, cakupan: null } });
		expect(screen.getByTestId('empty-state')).toBeTruthy();
	});
});
