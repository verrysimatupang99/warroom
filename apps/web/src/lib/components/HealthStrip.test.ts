// HealthStrip: bedakan "pasar sepi" dari "worker mati".
//
// Tanpa strip ini, Home menampilkan kekosongan yang sama untuk dua keadaan yang
// sangat berbeda. Tes ini mengunci kontraknya: setiap nada berasal dari jawaban
// /api/v1/ready, dan kegagalan membaca status ditampilkan sebagai "tidak
// terbaca", bukan hijau.
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import HealthStrip from './HealthStrip.svelte';

const sehat = {
	status: 'ready',
	db: true,
	checks: { worker_heartbeats: { status: 'ok' }, stale_facts: { status: 'ok', count: 0 } },
	freshness: { status: 'ok', count: 0 },
	time: '2026-11-05T09:00:00Z',
	user: 'uji'
} as const;

const basi = {
	status: 'not_ready',
	db: true,
	checks: { worker_heartbeats: { status: 'stale' }, stale_facts: { status: 'stale', count: 25 } },
	freshness: { status: 'stale', count: 25 },
	time: '2026-11-05T09:00:00Z',
	user: 'uji'
} as const;

describe('HealthStrip', () => {
	it('semua sehat → db ok, worker ok, 0 data basi', () => {
		render(HealthStrip, { props: { kesiapan: sehat } });
		const el = screen.getByTestId('health-strip');
		expect(el.textContent).toContain('db ok');
		expect(el.textContent).toContain('worker ok');
		expect(el.textContent).toContain('0 data basi');
	});

	it('worker basi & ada data basi → dua penanda gagal', () => {
		render(HealthStrip, { props: { kesiapan: basi } });
		const el = screen.getByTestId('health-strip');
		expect(el.textContent).toContain('worker basi');
		expect(el.textContent).toContain('25 data basi');
		const nada = Array.from(el.querySelectorAll('[data-nada]')).map((n) => n.getAttribute('data-nada'));
		expect(nada.filter((n) => n === 'gagal').length).toBeGreaterThanOrEqual(2);
	});

	it('belum terbaca → n/a, bukan angka karangan', () => {
		render(HealthStrip, { props: {} });
		const el = screen.getByTestId('health-strip');
		expect(el.textContent).toContain('db n/a');
		expect(el.textContent).toContain('worker n/a');
		expect(el.textContent).toContain('data basi n/a');
	});

	it('permintaan gagal → dinyatakan terbuka, bukan hijau', () => {
		render(HealthStrip, { props: { gagal: true } });
		const el = screen.getByTestId('health-strip');
		expect(el.textContent).toContain('status sistem tidak terbaca');
		expect(el.textContent).toContain('data basi n/a');
	});
});
