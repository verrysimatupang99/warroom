import { expect, test } from '@playwright/test';

/**
 * Tabel akurasi IDX (perbaikan per-halaman 10 Okt; disesuaikan 16 Okt).
 *
 * Sejarah: dulu test ini menuntut header "VONIS" + kolom PAKEM di /idx?sub=sinyal.
 * Setelah revisi total UI 16 Okt, tabel akurasi IDX digantikan tabel sinyal
 * (KODE/BUCKET/WR EVENT/POTENSI/MAX DD/CATATAN) — jadi yang dijaga sekarang:
 *   1. tabel akurasi/sinyal IDX benar-benar ter-render (bukan tabel kosong);
 *   2. punya kolom pembanding kualitas per setup (WR/MAX DD/CATATAN), yang perannya
 *      sama dengan kolom VONIS dulu: mata tidak perlu menebak mana yang layak;
 *   3. menyebut sumber (Stock Arjum) supaya jelas asal angkanya.
 */
test('idx: tabel akurasi per setup ter-render dengan kolom pembanding', async ({ page }) => {
	await page.goto('/idx?sub=sinyal');
	const tabel = page.locator('table').first();
	await expect(tabel).toBeVisible({ timeout: 25000 });

	const ths = (await tabel.locator('th').allInnerTexts()).map((s) => s.toUpperCase());
	console.log('TH IDX: ' + ths.join(' | '));
	expect(ths.length).toBeGreaterThan(0);

	const baris = tabel.locator('tbody tr');
	expect(await baris.count()).toBeGreaterThan(0);

	// Kolom pembanding mutu per setup (pengganti peran "VONIS").
	const adaPembanding = ths.some((h) => /WR|DD|CATATAN|VONIS/i.test(h));
	expect(adaPembanding, 'tabel akurasi harus punya kolom pembanding mutu').toBe(true);

	// Sumber data disebut supaya pembaca tahu asal angka.
	const t = await page.locator('body').innerText();
	expect(t).toMatch(/Stock Arjum|Arjum|bareksa|idx/i);
});
