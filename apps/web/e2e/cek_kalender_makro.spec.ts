/**
 * 10 Okt: kalender makro di /riset?sub=kalender harus JUJUR membedakan
 * "tidak ada agenda" dari "data minggu berjalan sudah habis".
 *
 * Latar (temuan nyata): sumber `ff_calendar_thisweek.json` hanya memuat minggu
 * berjalan. Saat minggu itu habis (mis. Sabtu), `berikutnya` kosong walau `jumlah`
 * besar. Sebelumnya halaman hanya menulis "AGENDA KOSONG" — pembaca bisa menyimpulkan
 * keliru bahwa benar-benar tak ada agenda, padahal datanya minggu lalu.
 *
 * Test ini menjaga agar rentang tanggal + pesan jujur itu tidak hilang lagi.
 */
import { test, expect } from '@playwright/test';
import { KREDENSIAL, PESAN_SKIP, loginLewat, tungguSiap } from './util';

test.describe('/riset?sub=kalender — kejujuran rentang agenda', () => {
	test.skip(!KREDENSIAL.user || !KREDENSIAL.pass, PESAN_SKIP);

	test('agenda makro menyebut rentang tanggal, bukan sekadar "kosong"', async ({ page }) => {
		expect(await loginLewat(page)).toBe(true);
		await page.goto('/riset?sub=kalender');
		await tungguSiap(page);

		// 1. Kartu agenda ada.
		await expect(page.getByText('Agenda makro').first()).toBeVisible({ timeout: 15000 });

		// 2. Rentang tanggal WAJIB tampil (pola "04 Okt 2026 – 10 Okt 2026").
		//    Inilah yang membedakan "kosong" dari "minggu ini sudah lewat".
		await expect(page.getByText(/\d{2} \w{3} \d{4}\s*[–-]\s*\d{2} \w{3} \d{4}/).first()).toBeVisible();

		// 3. Saat semua event sudah lewat, pesannya harus jelas & menyebut sebabnya
		//    (sumber "thisweek" belum menerbitkan minggu depan) — bukan "AGENDA KOSONG"
		//    yang ambigu. Judul di-render uppercase oleh CSS; dicocokkan tanpa peduli
		//    besar-kecil huruf. Bila kelak ada agenda baru, cek ini dilewati wajar.
		const lewat = await page.getByText(/minggu ini sudah selesai/i).count();
		if (lewat > 0) {
			// Pesan memakai tanda kutip melengkung (“ ”) — dicocokkan lewat kata kunci,
			// bukan kutip lurus, supaya tidak rapuh terhadap tipografi.
			await expect(page.getByText(/tidak ada agenda/i).first()).toBeVisible();
		}
	});
});
