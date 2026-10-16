/**
 * Tahap 1 (9 Okt): kartu "Gate live-trading — centang otomatis" di /idx.
 * Disesuaikan 16 Okt: dengan ledger idx_akurasi belum tersedia, kartu tetap
 * WAJIB render dan bilang terus terang "tidak ada setup di ledger akurasi" —
 * bukan diam, dan bukan menampilkan angka palsu.
 */
import { test, expect } from '@playwright/test';
import { KREDENSIAL, PESAN_SKIP, loginLewat, tungguSiap } from './util';

test.describe('/idx — kartu gate per setup', () => {
	test.skip(!KREDENSIAL.user || !KREDENSIAL.pass, PESAN_SKIP);

	test('kartu gate tampil & jujur soal ledger kosong', async ({ page }) => {
		expect(await loginLewat(page)).toBe(true);
		await page.goto('/idx?sub=sinyal');
		await tungguSiap(page);

		const kartu = page.getByText('Gate live-trading — centang otomatis');
		await expect(kartu).toBeVisible({ timeout: 15000 });

		// Kartu wajib menjelaskan bahwa ini bukan izin live.
		await expect(page.getByText(/bukan izin live|NO-GO/i).first()).toBeVisible();

		const t = await page.locator('body').innerText();
		const adaSetup = /BSJP|ARA/i.test(t);
		const adaKosong = /Tidak ada setup di ledger|ledger tidak terbaca|belum tersedia/i.test(t);

		// Salah satu dari dua kondisi HARUS benar dan disebut eksplisit.
		expect(adaSetup || adaKosong, 'kartu gate harus bilang ada setup atau jelaskan ledger kosong').toBe(true);
		console.log('--- KARTU GATE: setup=' + adaSetup + ' kosong=' + adaKosong);

		// Setup mesin IDX yang dikenal harus disebut namanya (meski dihentikan).
		expect(t).toMatch(/ARA Hunter|BSJP/);
	});
});
