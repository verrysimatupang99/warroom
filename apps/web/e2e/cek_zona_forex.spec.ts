/**
 * Tahap 2 (9 Okt): panel "Zona & Sinyal Mesin (Forex)" di /forex.
 * Tiru dari /xau/api/activesignals desk Tencent; angka dari fakta forex_sinyal (bukan dihitung UI).
 * Verifikasi lewat ORIGIN PRODUKSI (baseURL playwright = 0xgunsl1ng3r.xyz).
 */
import { test, expect } from '@playwright/test';
import { KREDENSIAL, PESAN_SKIP, loginLewat, tungguSiap } from './util';

test.describe('/forex — zona & sinyal mesin', () => {
	test.skip(!KREDENSIAL.user || !KREDENSIAL.pass, PESAN_SKIP);

	test('panel zona tampil dengan pair & kolom yang benar', async ({ page }) => {
		expect(await loginLewat(page)).toBe(true);
		await page.goto('/forex?sub=struktur');
		await tungguSiap(page);

		await expect(page.getByText('Zona & Sinyal Mesin (Forex)')).toBeVisible({ timeout: 15000 });

		// Pair mesin forex harus muncul (dari fakta forex_sinyal.entries).
		for (const p of ['XAUUSD', 'NAS100']) {
			await expect(page.getByText(p).first()).toBeVisible();
		}

		// Kolom kunci.
		await expect(page.getByText('Arah').first()).toBeVisible();
		await expect(page.getByText('Entry').first()).toBeVisible();
	});
});
