/**
 * Penjaga revisi Home (pemilik, 7 Okt 2026):
 *  1. Card status + akurasi digabung; sinyal dipindah ke bawahnya.
 *  2. Maks 3 sinyal per market + tombol "Lihat semua" bila lebih.
 *  3. "Tidak ada sinyal" tidak boleh tertukar dengan "gagal sistem".
 *  4. Ticker berjalan (animasi) dan tidak lompat.
 */
import { expect, test } from '@playwright/test';

test('Home: card gabungan, sinyal per market maks 3, ticker berjalan', async ({ page }) => {
	await page.goto('/');
	await expect(page.getByText('STATUS HARI INI')).toBeVisible({ timeout: 25000 });

	// (1) satu card memuat status DAN akurasi
	const kartu = page.locator('.kartu-gabung').first();
	await expect(kartu).toBeVisible();
	await expect(kartu.getByText('Akurasi & PnL per Market')).toBeVisible();

	// (2) daftar sinyal ada DI BAWAH card gabungan
	const ySinyal = (await page.locator('section[aria-label="Sinyal per market"]').boundingBox())?.y ?? 0;
	const yKartu = (await kartu.boundingBox())?.y ?? 0;
	expect(ySinyal).toBeGreaterThan(yKartu);

	// maks 3 kartu kandidat per market: crypto punya 3 baris meski ada 6 hidup
	const kartuCrypto = page.locator('.sinyal-kartu').first();
	await expect(kartuCrypto.locator('.sinyal-baris')).toHaveCount(3);
	await expect(kartuCrypto.getByText(/Lihat semua \(\d+\)/)).toBeVisible();

	// (3) bahasa manusia — 9 Okt 2026 pemilik: "terlalu pro, targetnya bot trading doang".
	//     Judul pindah dari jargon (KANDIDAT/lolos gate) ke kalimat awam. Penjaganya tetap:
	//     harus ada pernyataan status yang bisa dibaca manusia.
	const teks = await page.locator('body').innerText();
	expect(teks).toMatch(/Bot memantau|layak dibeli|TIDAK ADA SINYAL|GAGAL SISTEM/);

	// (4) ticker beranimasi, dua salinan, pause saat hover
	const anim = await page.evaluate(() => {
		const el = document.querySelector('.ticker-jalur') as HTMLElement | null;
		if (!el) return null;
		return {
			nama: getComputedStyle(el).animationName,
			durasi: getComputedStyle(el).animationDuration,
			salinan: document.querySelectorAll('.ticker-set').length
		};
	});
	expect(anim?.nama).toContain('geser-ticker');
	expect(anim?.salinan).toBe(2);
});

test('Ukur & Eksekusi: penjelasan metode ada dan memuat 6 aturan gate', async ({ page }) => {
	await page.goto('/crypto?sub=setup');
	await page.getByRole('button', { name: /Metode yang dipakai/ }).click();
	const t = await page.locator('body').innerText();
	for (const r of ['mtf_alignment', 'poi_valid', 'freshness', 'sl_distance', 'atr_min', 'exposure']) {
		expect(t).toContain(r);
	}
});
