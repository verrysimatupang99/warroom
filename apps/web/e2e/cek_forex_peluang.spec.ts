/**
 * 10 Okt: panel "Peluang hari ini" + "Hati-hati" di /forex (pola IDX/InvestSaham),
 * dengan satu jujur khas forex: sampel masih kecil → tanda "Sampel belum cukup".
 * Angka murni dari jurnal mesin (pasar_akurasi.forex); tanpa ambang baru.
 */
import { test, expect } from '@playwright/test';
import { KREDENSIAL, PESAN_SKIP, loginLewat, tungguSiap } from './util';

test.describe('/forex — peluang & hati-hati', () => {
	test.skip(!KREDENSIAL.user || !KREDENSIAL.pass, PESAN_SKIP);

	test('FOREX menampilkan peluang + kejujuran sampel kecil', async ({ page }) => {
		expect(await loginLewat(page)).toBe(true);
		await page.goto('/forex');
		await tungguSiap(page);

		await expect(page.getByText('Peluang hari ini').first()).toBeVisible({ timeout: 15000 });
		await expect(page.getByText('Hati-hati').first()).toBeVisible();
		// Kejujuran forex: bukan "Layak", tapi "sampel belum cukup".
		await expect(page.getByText(/Sampel belum cukup|Sampel cukup/).first()).toBeVisible();
		// Nama manusiawi pair harus muncul, bukan cuma kode mesin.
		await expect(page.getByText(/Gold \(XAUUSD\)/).first()).toBeVisible();
	});
});
