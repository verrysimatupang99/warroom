/**
 * 10 Okt: panel vonis LP di sub-tab /gmgn?sub=lp (pola Peluang + Hipotesis + Hati-hati,
 * sama spt /idx & /forex, TAPI ini kabar buruk). Angka MURNI dari sim_ledger.jsonl via
 * fact `lp_paper`; tak ada ambang baru (cukup = n>=30, pakem gate yang sudah ada).
 *
 * Yang dijaga test ini BUKAN sekadar "panel ada", melainkan bahwa kejujuran yang keras
 * tetap terjaga: vonis "jangan taruh uang" + bukti "sinyal lebih buruk dari acak" harus
 * benar-benar tampil. Kalau suatu hari angka ini membaik, test akan gagal dan memaksa
 * kita membacanya — bukan diam-diam berubah.
 */
import { test, expect } from '@playwright/test';
import { KREDENSIAL, PESAN_SKIP, loginLewat, tungguSiap } from './util';

test.describe('/gmgn?sub=lp — vonis mesin LP', () => {
	test.skip(!KREDENSIAL.user || !KREDENSIAL.pass, PESAN_SKIP);

	test('LP menampilkan vonis jujur: merugi, lebih buruk dari acak, jangan pakai uang', async ({ page }) => {
		expect(await loginLewat(page)).toBe(true);
		await page.goto('/gmgn?sub=lp');
		await tungguSiap(page);

		// 1. Panel vonis benar-benar tampil.
		await expect(page.getByText('Peluang hari ini').first()).toBeVisible({ timeout: 15000 });
		await expect(page.getByText('Hati-hati').first()).toBeVisible();

		// 2. Vonisnya keras & jelas — bukan "netral".
		await expect(page.getByText(/jangan taruh uang di sini/i).first()).toBeVisible();

		// 3. Bukti terkuat: sinyal lebih buruk dari pilihan acak.
		await expect(page.getByText(/Sinyal lebih buruk dari acak/i).first()).toBeVisible();

		// 4. Kejujuran "bukan cuma biaya" (GROSS pun rugi) — ini yang membedakan
		//    diagnosis benar dari diagnosis malas.
		await expect(page.getByText(/Bukan cuma biaya/i).first()).toBeVisible();

		// 5. Angka murni terlihat, bukan "—": n=283 posisi tuntas, median negatif.
		await expect(page.getByText(/283 posisi tuntas/i).first()).toBeVisible();
		await expect(page.getByText(/median -21,76%/i).first()).toBeVisible();
	});
});
