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

		// Pembaruan 10 Okt: rombakan UI/UX meniru dashboard Tencent — judul kartu jadi
		// "Ringkasan Crypto — Uang, Risiko, Sinyal" dan KPI ditulis huruf besar lewat CSS.
		await expect(page.getByText('Ringkasan Crypto — Uang, Risiko, Sinyal')).toBeVisible({ timeout: 15000 });
		await expect(page.getByText(/Modal paper/i).first()).toBeVisible();
		await expect(page.getByText(/Ruang risiko sisa/i).first()).toBeVisible();
		await expect(page.getByText(/Dimensi gerbang/i).first()).toBeVisible();

		// Panel MEXC TIDAK boleh ada (arahan owner: key tidak diambil).
		expect(await page.getByText('MEXC Live').count()).toBe(0);
	});
});
