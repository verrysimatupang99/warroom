import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import InfraHealth from './InfraHealth.svelte';

const snapshotSehat = {
	tersedia: true,
	umur_s: 120,
	memoh_runtime: { active: 'active', outbound_conn: 1, restarts: 0 },
	mt5: { 'box-2aacb3': 'up', 'mt5-paper-1': 'up', 'mt5-paper-2': 'down' },
	instabox_watchdog: { timer: 'active', last_status: '0' },
	cyber1: { disk_pct: 61, mem_available_mb: 2790 },
	warroom: { root_http: '200', api_health_http: '401' }
};

describe('InfraHealth', () => {
	it('state memuat → tampilkan teks memuat', () => {
		render(InfraHealth, { props: { data: null, galat: null, memuat: true } });
		const el = screen.getByTestId('infra-health');
		expect(el.textContent).toContain('Memuat status infra');
	});

	it('belum ada snapshot → pesan jujur, bukan hijau palsu', () => {
		render(InfraHealth, { props: { data: null, galat: null, memuat: false } });
		const el = screen.getByTestId('infra-health');
		expect(el.textContent).toContain('Belum ada snapshot infra');
	});

	it('galat → tampilkan pesan galat', () => {
		render(InfraHealth, { props: { data: null, galat: 'Endpoint tidak menjawab', memuat: false } });
		const el = screen.getByTestId('infra-health');
		expect(el.textContent).toContain('Endpoint tidak menjawab');
	});

	it('ada data → tampilkan tiap MT5 dan statusnya', () => {
		render(InfraHealth, { props: { data: snapshotSehat, galat: null, memuat: false } });
		const el = screen.getByTestId('infra-health');
		expect(el.textContent).toContain('DAEMON MEMOH');
		expect(el.textContent).toContain('active');
		expect(el.textContent).toContain('box-2aacb3');
		expect(el.textContent).toContain('up');
		expect(el.textContent).toContain('mt5-paper-2');
		expect(el.textContent).toContain('down');
	});

	it('snapshot basi (>30 mnt) → tandai data basi', () => {
		const basi = { ...snapshotSehat, umur_s: 3600 };
		render(InfraHealth, { props: { data: basi, galat: null, memuat: false } });
		const el = screen.getByTestId('infra-health');
		expect(el.textContent).toContain('data basi');
	});
});
