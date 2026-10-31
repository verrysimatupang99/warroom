/**
 * US2.4 — kurva ekuitas forex menampilkan drawdown dan penanda trade.
 * Data dari `/journal/performance?market=forex`; marker kosong sampai ada deal nyata.
 */
import { test, expect } from '@playwright/test';
import { KREDENSIAL, PESAN_SKIP, loginLewat, tungguSiap } from './util';

test.describe('/jurnal — kurva ekuitas forex', () => {
	test.skip(!KREDENSIAL.user || !KREDENSIAL.pass, PESAN_SKIP);

	test('menampilkan kurva, drawdown, dan area penanda', async ({ page }) => {
		expect(await loginLewat(page)).toBe(true);
		await page.goto('/jurnal?market=forex');
		await tungguSiap(page);

		await expect(page.getByText('Kinerja ekuitas')).toBeVisible({ timeout: 15_000 });
		await expect(page.getByText('Drawdown maks', { exact: true }).first()).toBeVisible();
		await expect(page.getByTestId('kurva-ekuitas').locator('svg')).toBeVisible();
		// Tanpa deal tertutup, penanda boleh nol — tetapi area legenda harus jujur.
		await expect(page.getByText(/penanda/).first()).toBeVisible();
	});
});
