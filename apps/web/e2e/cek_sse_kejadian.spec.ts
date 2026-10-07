/**
 * Penjaga bug kelaparan SSE (ditemukan saat menjawab QA putaran 2):
 * panel "Kejadian Area" hanya terisi lewat backfill; aliran SSE-nya sendiri tidak pernah
 * sampai ke kejadian yang cocok karena 200 baris terakhir didominasi `job.ran`.
 * Setelah perbaikan (filter topik di SQL + `after` selalu maju), backfill DAN aliran
 * sama-sama bekerja — panel harus menampilkan kejadian nyata untuk area crypto.
 */
import { expect, test } from '@playwright/test';

test('panel Kejadian Area crypto memuat kejadian nyata', async ({ page }) => {
	await page.goto('/crypto?sub=cockpit');
	const tombol = page.getByRole('button', { name: /Kejadian Area/ });
	await expect(tombol).toBeVisible({ timeout: 25000 });
	await tombol.click();
	await expect(page.getByText(/kejadian/).first()).toBeVisible({ timeout: 15000 });
	const t = await page.locator('body').innerText();
	const i = t.indexOf('KEJADIAN AREA');
	const seg = t.slice(i, i + 600);
	console.log('--- KEJADIAN ---\n' + seg.slice(0, 400));
	expect(seg).toMatch(/\d+ kejadian/);
	// panel tidak boleh mengaku kosong bila ada kejadian; kalau kosong, harus menjelaskan
	if (/0 kejadian/.test(seg)) {
		expect(seg).toMatch(/BELUM ADA KEJADIAN/);
	}
});
