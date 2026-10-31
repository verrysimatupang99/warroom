/**
 * Verifikasi menyeluruh situs produksi — 31 Okt 2026.
 * Cek rute, API baru, panel baru, error console/request, dan overflow.
 * Screenshot disimpan ke artifacts/verifikasi-web-20261031/ (di luar repo build).
 */
import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { KREDENSIAL, PESAN_SKIP, loginLewat, tungguSiap } from './util';

test.skip(!KREDENSIAL.user || !KREDENSIAL.pass, PESAN_SKIP);

const BUKTI = path.resolve('../../artifacts/verifikasi-web-20261031');
fs.mkdirSync(BUKTI, { recursive: true });

const RUTE = [
	{ jalur: '/', teks: [] },
	{ jalur: '/forex', teks: [] },
	{ jalur: '/forex?sub=sinyal', teks: ['Status mesin Reaper', 'Riwayat evaluasi EA'] },
	{ jalur: '/jurnal?market=forex', teks: ['Kinerja ekuitas', 'Drawdown maks'] },
	{ jalur: '/jurnal?market=crypto', teks: ['Kinerja ekuitas'] },
	{ jalur: '/crypto?sub=sinyal', teks: ['Jurnal sinyal terkirim', 'Bootstrap'] },
	{ jalur: '/sistem?sub=kebijakan', teks: ['Gate yang berlaku', 'Parameter aktif'] },
	{ jalur: '/idx', teks: [] },
	{ jalur: '/gmgn', teks: [] },
	{ jalur: '/polymarket', teks: ['ditangguhkan sementara'] }
];

test.describe('verifikasi website produksi', () => {
	test('rute utama 1440px: status, teks, error, overflow', async ({ page }) => {
		expect(await loginLewat(page)).toBe(true);
		await page.setViewportSize({ width: 1440, height: 1000 });
		const consoleErrors: string[] = [];
		const pageErrors: string[] = [];
		const failed: string[] = [];
		const badResponses: string[] = [];
		page.on('console', (m) => {
			if (m.type() === 'error' && !m.text().includes('status of 503')) {
				consoleErrors.push(m.text());
			}
		});
		page.on('response', (r) => {
			if (r.status() >= 400) badResponses.push(`${r.status()} ${r.url()}`);
		});
		page.on('pageerror', (e) => pageErrors.push(e.message));
		page.on('requestfailed', (r) => {
			const url = r.url();
			if (url.includes('/api/v1/stream')) return; // SSE ditutup saat navigasi
			failed.push(`${url} :: ${r.failure()?.errorText ?? '?'}`);
		});

		for (const { jalur, teks } of RUTE) {
			const resp = await page.goto(jalur);
			await tungguSiap(page);
			await page.waitForTimeout(600);
			expect(resp?.status(), `${jalur} HTTP ${resp?.status()}`).toBeLessThan(400);
			const isi = await page.locator('body').innerText();
			expect(isi, `${jalur} GAGAL MEMUAT`).not.toContain('GAGAL MEMUAT');
			expect(isi, `${jalur} Application error`).not.toContain('Application error');
			for (const t of teks) expect(isi, `${jalur} tidak memuat "${t}"`).toContain(t);
			const overflow = await page.evaluate(
				() => document.documentElement.scrollWidth - window.innerWidth
			);
			expect(overflow, `${jalur} overflow ${overflow}px`).toBeLessThanOrEqual(1);
			if (['/forex?sub=sinyal', '/crypto?sub=sinyal', '/jurnal?market=forex'].includes(jalur)) {
				await page.screenshot({
					path: path.join(BUKTI, `1440-${jalur.replace(/[/?=&]/g, '_')}.png`),
					fullPage: true
				});
			}
		}
		// 503 dari edge/performance adalah state kosong yang ditangani UI (fills kosong,
		// crypto belum punya deret waktu) — bukan kegagalan halaman.
		const takTerduga = badResponses.filter(
			(x) => !(x.startsWith('503 ') && /\/api\/v1\/(journal\/(edge|performance)\?market=|idx\/)/.test(x))
		);
		expect(takTerduga, takTerduga.join('\n')).toEqual([]);
		expect(pageErrors, pageErrors.join('\n')).toEqual([]);
		expect(consoleErrors, consoleErrors.join('\n')).toEqual([]);
		expect(failed, failed.join('\n')).toEqual([]);
	});

	test('mobile 390px: tidak overflow, semua rute utama terbuka', async ({ page }) => {
		expect(await loginLewat(page)).toBe(true);
		await page.setViewportSize({ width: 390, height: 844 });
		for (const { jalur } of RUTE) {
			const resp = await page.goto(jalur);
			await tungguSiap(page);
			await page.waitForTimeout(400);
			expect(resp?.status(), `${jalur} HTTP`).toBeLessThan(400);
			const overflow = await page.evaluate(
				() => document.documentElement.scrollWidth - window.innerWidth
			);
			expect(overflow, `${jalur} overflow ${overflow}px`).toBeLessThanOrEqual(1);
		}
		await expect(page.locator('.mobile-header')).toBeVisible();
		await page.goto('/crypto?sub=sinyal');
		await tungguSiap(page);
		await expect(page.getByText('Jurnal sinyal terkirim')).toBeVisible();
		await page.waitForTimeout(1200);
		await page.screenshot({ path: path.join(BUKTI, '390-crypto-sinyal.png'), fullPage: true });
	});

	test('API baru menjawab dengan bentuk yang benar', async ({ page }) => {
		expect(await loginLewat(page)).toBe(true);
		const signals = await page.request.get('/api/v1/journal/signals');
		expect(signals.status()).toBe(200);
		const s = await signals.json();
		expect(s.ringkas.n_terkirim).toBeGreaterThan(0);
		expect(s.montecarlo.n_simulasi).toBe(10000);
		expect(s.ringkas.per_versi).toBeTruthy();

		const forex = await page.request.get('/api/v1/journal/scanlog?market=forex');
		expect(forex.status()).toBe(200);
		const f = await forex.json();
		expect(f.market).toBe('forex');
		expect(Array.isArray(f.terakhir)).toBe(true);

		const crypto = await page.request.get('/api/v1/journal/scanlog?market=crypto');
		expect(crypto.status()).toBe(200);
		expect((await crypto.json()).market).toBe('crypto');

		const perf = await page.request.get('/api/v1/journal/performance?market=forex');
		expect(perf.status()).toBe(200);
		const p = await perf.json();
		expect(p.n_titik).toBeGreaterThan(0);
		expect(p).toHaveProperty('markers');
		expect(p).toHaveProperty('drawdown_max_pct');

		const params = await page.request.get('/api/v1/params');
		expect(params.status()).toBe(200);
	});
});
