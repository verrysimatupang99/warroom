/**
 * 10 Okt: halaman /sistem?sub=mesin — sumber data pihak ketiga (LP Agent).
 *
 * Yang dijaga test ini adalah KEJUJURAN, bukan sekadar "halaman ada":
 *  - Tanpa kunci, halaman WAJIB bilang "menunggu kunci" + sebabnya,
 *    bukan menampilkan 0 pool yang menyamar sebagai "tidak ada peluang".
 *  - Base URL yang ditampilkan harus yang BENAR dari spec resmi
 *    (open-api/v1), bukan yang salah di dokumen riset (api.lpagent.io/v1).
 *  - Jalur uang harus jelas terkunci (armed=false) — ini telemetri, bukan sinyal beli.
 */
import { test, expect } from '@playwright/test';
import { KREDENSIAL, PESAN_SKIP, loginLewat, tungguSiap } from './util';

test.describe('/sistem?sub=mesin — LP Agent (pihak ketiga)', () => {
	test.skip(!KREDENSIAL.user || !KREDENSIAL.pass, PESAN_SKIP);

	test('LP Agent tampil jujur: menunggu kunci + base url benar + jalur uang terkunci', async ({
		page
	}) => {
		expect(await loginLewat(page)).toBe(true);
		await page.goto('/sistem?sub=mesin');
		await tungguSiap(page);

		// 1. Kartu LP Agent ada (judul menyebut Solana/Meteora).
		await expect(page.getByText(/LP Agent · likuiditas Solana/i).first()).toBeVisible({
			timeout: 15000
		});

		// 2. Kejujuran: tanpa kunci → "menunggu kunci" + sebab yang menyebut env var.
		await expect(page.getByText(/menunggu kunci/i).first()).toBeVisible();
		await expect(page.getByText(/LPAGENT_API_KEY belum ada/i).first()).toBeVisible();
		// Halaman tidak boleh mengarang daftar pool.
		await expect(page.getByText(/Belum ada data pool/i).first()).toBeVisible();

		// 3. Base URL harus yang BENAR (temuan: dokumen riset salah tulis /v1).
		await expect(page.getByText(/api\.lpagent\.io\/open-api\/v1/i).first()).toBeVisible();

		// 4. Jalur uang jelas terkunci — bukti gerbang live tak disentuh.
		await expect(page.getByText(/armed=false/i).first()).toBeVisible();
	});
});
