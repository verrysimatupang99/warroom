/**
 * Jurnal sinyal terkirim: panel di tab Sinyal crypto.
 * Angka berasal dari `/api/v1/journal/signals` (dihitung worker dari candle setelah kirim).
 */
import { test, expect } from '@playwright/test';
import { KREDENSIAL, PESAN_SKIP, loginLewat, tungguSiap } from './util';

test.describe('/crypto — jurnal sinyal', () => {
	test.skip(!KREDENSIAL.user || !KREDENSIAL.pass, PESAN_SKIP);

	test('menampilkan ringkasan dan baris hasil', async ({ page }) => {
		expect(await loginLewat(page)).toBe(true);
		await page.goto('/crypto?sub=sinyal');
		await tungguSiap(page);

		const panel = page.locator('section').filter({ hasText: 'Jurnal sinyal terkirim' });
		await expect(panel).toBeVisible({ timeout: 15_000 });
		await expect(panel.getByText('TERKIRIM', { exact: true })).toBeVisible();
		await expect(panel.getByText('WIN RATE TP1', { exact: true })).toBeVisible();
		await expect(panel.getByText(/hasil berbeda dari cache/)).toBeVisible();
	});
});
