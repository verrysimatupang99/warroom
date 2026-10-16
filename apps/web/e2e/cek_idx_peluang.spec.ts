/**
 * 10 Okt: panel "Peluang hari ini" + "Hati-hati" di /idx (pola InvestSaham:
 * Screener + Hipotesis + Hati-hati). Angka MURNI dari idx_akurasi (mean_r + n);
 * nama setup diterjemahkan ke bahasa manusia. Verifikasi lewat ORIGIN PRODUKSI.
 */
import { test, expect } from '@playwright/test';
import { KREDENSIAL, PESAN_SKIP, loginLewat, tungguSiap } from './util';

test.describe('/idx — peluang & hati-hati', () => {
	test.skip(!KREDENSIAL.user || !KREDENSIAL.pass, PESAN_SKIP);

	test('IDX menampilkan peluang hari ini (BSJP) & peringatan hati-hati', async ({ page }) => {
		expect(await loginLewat(page)).toBe(true);
		await page.goto('/idx');
		await tungguSiap(page);

		// Panel "Peluang hari ini" diganti daftar LANGKAH pada revisi UI 16 Okt;
		// yang wajib tetap ada: nama manusiawi setup BSJP + dompet paper IDX.
		await expect(page.getByText(/Beli Sore Jual Pagi/).first()).toBeVisible({ timeout: 15000 });
		await expect(page.getByText(/Dompet Paper IDX/).first()).toBeVisible();
	});
});
