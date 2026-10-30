/**
 * US1.3 — panel "Status mesin Reaper" di /forex (tab Sinyal).
 * Memastikan keputusan EA bisa dibaca tanpa membuka terminal: sesi, indikator terakhir,
 * alasan evaluasi, dan umur data. Angka berasal dari telemetri EA; tes ini hanya membaca.
 */
import { test, expect } from '@playwright/test';
import { KREDENSIAL, PESAN_SKIP, loginLewat, tungguSiap } from './util';

test.describe('/forex — status mesin Reaper', () => {
	test.skip(!KREDENSIAL.user || !KREDENSIAL.pass, PESAN_SKIP);

	test('panel menampilkan sesi, indikator, alasan, dan umur evaluasi', async ({ page }) => {
		expect(await loginLewat(page)).toBe(true);
		await page.goto('/forex?sub=sinyal');
		await tungguSiap(page);

		const panel = page.locator('section').filter({ hasText: 'Status mesin Reaper' });
		await expect(panel).toBeVisible({ timeout: 15_000 });

		await expect(panel.getByText(/sesi 08–09 aktif|di luar sesi 08–09/)).toBeVisible();
		for (const label of [
			'EVALUASI TERAKHIR',
			'ATR M5',
			'SPREAD',
			'RSI 14',
			'EMA 21',
			'EMA 55',
			'TREN M15'
		]) {
			await expect(panel.getByText(label, { exact: true })).toBeVisible();
		}

		// Umur data: "jam server HH:MM · N menit lalu" bila EA v3.1 sudah mengirim evaluasi.
		await expect(panel.getByText(/jam server \d{2}:\d{2}/)).toBeVisible();
		await expect(panel.getByText(/menit lalu/)).toBeVisible();
	});
});
