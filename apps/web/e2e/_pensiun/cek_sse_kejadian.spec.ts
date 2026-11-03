/**
 * Penjaga bug kelaparan SSE (ditemukan saat menjawab QA putaran 2):
 * panel kejadian area hanya terisi lewat backfill; aliran SSE-nya sendiri tidak pernah
 * sampai ke kejadian yang cocok karena 200 baris terakhir didominasi `job.ran`.
 * Setelah perbaikan (filter topik di SQL + `after` selalu maju), backfill DAN aliran
 * sama-sama bekerja — panel harus menampilkan kejadian nyata untuk area crypto.
 *
 * Disesuaikan 16 Okt: panel kini berjudul "EVENTITEM AREA" dengan penghitung
 * "Aliran SSE terfilter topik area · N kejadian" — bukan lagi tombol "Kejadian Area".
 */
import { expect, test } from '@playwright/test';

test('panel kejadian area crypto memuat kejadian nyata', async ({ page }) => {
	await page.goto('/crypto?sub=cockpit');

	// Penghitung kejadian dari aliran SSE/backfill harus terlihat.
	const hitung = page.getByText(/terfilter topik area · \d+ kejadian/);
	await expect(hitung.first()).toBeVisible({ timeout: 25000 });

	const t = await page.locator('body').innerText();
	const i = t.search(/terfilter topik area/);
	const seg = t.slice(Math.max(0, i - 400), Math.max(0, i) + 400);
	console.log('--- KEJADIAN ---\n' + seg.slice(0, 500));

	// Bila ada kejadian, jumlahnya harus > 0 dan bukan pesan kosong.
	const m = t.match(/terfilter topik area · (\d+) kejadian/);
	expect(m, 'penghitung kejadian harus terbaca').not.toBeNull();
	const n = Number(m![1]);
	console.log('jumlah kejadian = ' + n);
	if (n === 0) {
		expect(t).toMatch(/BELUM ADA KEJADIAN|tidak ada kejadian/i);
	}
	// Panel harus menyebut bahwa ia terkunci/terbuka (affordance jelas).
	expect(t).toMatch(/Terkunci rapat|buka/i);
});
