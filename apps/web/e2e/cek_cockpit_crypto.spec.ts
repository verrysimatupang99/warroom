/**
 * Tahap 3 (9 Okt): panel "Cockpit — Status Mesin & Ruang Risiko" di /crypto.
 * Tiru dari desk Crypto Tencent; angka dari fakta crypto_sinyal + risiko (bukan dihitung UI).
 * TANPA panel MEXC (kredensial tidak diambil). Verifikasi lewat ORIGIN PRODUKSI.
 */
import { test, expect } from '@playwright/test';
import { KREDENSIAL, PESAN_SKIP, loginLewat, tungguSiap } from './util';

test.describe('/crypto — cockpit mesin & risiko', () => {
	test.skip(!KREDENSIAL.user || !KREDENSIAL.pass, PESAN_SKIP);

	test('cockpit tampil dengan ruang risiko & dimensi gerbang', async ({ page }) => {
		expect(await loginLewat(page)).toBe(true);
		await page.goto('/crypto?sub=cockpit');
		await tungguSiap(page);

		await expect(page.getByText('Cockpit — Status Mesin & Ruang Risiko')).toBeVisible({ timeout: 15000 });
		await expect(page.getByText('Ruang sisa').first()).toBeVisible();
		await expect(page.getByText('Dimensi gerbang').first()).toBeVisible();

		// Panel MEXC TIDAK boleh ada (arahan owner: key tidak diambil).
		expect(await page.getByText('MEXC Live').count()).toBe(0);
	});
});
