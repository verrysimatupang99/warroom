import { expect, test } from '@playwright/test';

/**
 * Kolom VONIS di tabel akurasi IDX (perbaikan per-halaman 10 Okt).
 * Menjaga: tabel menampilkan vonis per setup (Layak/Belum terbukti/Merugikan)
 * sehingga mata tidak menebak mana setup yang layak dipercaya.
 */
test('idx: tabel akurasi menampilkan kolom VONIS per setup', async ({ page }) => {
	await page.goto('/idx?sub=sinyal');
	const tabel = page.locator('table', { hasText: 'PAKEM' }).first();
	await expect(tabel).toBeVisible({ timeout: 25000 });
	await expect(tabel.locator('th', { hasText: 'VONIS' })).toBeVisible();

	const baris = tabel.locator('tbody tr');
	expect(await baris.count()).toBeGreaterThan(0);

	// Minimal satu vonis harus muncul sebagai label nyata.
	const teks = await tabel.innerText();
	expect(/Layak|Belum terbukti|Merugikan|Diarsipkan/.test(teks)).toBe(true);
});
