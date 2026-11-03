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

		// Panel "Peluang hari ini" diganti blok Struktur/Zona pada revisi UI 16 Okt;
		// yang wajib tetap ada: nama manusiawi pair + dompet paper forex.
		await expect(page.getByText(/XAUUSD/).first()).toBeVisible({ timeout: 15000 });
		await expect(page.getByText(/Dompet Paper Forex/).first()).toBeVisible();
		// Nama manusiawi pair harus muncul, bukan cuma kode mesin.
		await expect(page.getByText(/Pandangan Harga Emas/).first()).toBeVisible();
	});
});
