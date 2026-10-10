/**
 * Penjaga badge mode per kartu market (QA eksternal 7 Okt):
 * "user harus membaca jauh ke bawah untuk memahami apakah angka masih live, stale,
 *  paper, atau historical". Sekarang tiap kartu menyebut mode + sumber + umur.
 */
import { expect, test } from '@playwright/test';

test('Home: tiap kartu market punya mode + sumber', async ({ page }) => {
	await page.goto('/');
	await expect(page.getByRole('heading', { name: 'Sinyal per Market' })).toBeVisible({ timeout: 25000 });
	await expect(page.getByText(/sumber: OKX/).first()).toBeVisible({ timeout: 20000 });
	const t = await page.locator('body').innerText();
	const i = t.indexOf('Sinyal per Market');
	const seg = t.slice(i, i + 2400);
	console.log('--- KARTU ---\n' + seg.slice(0, 900));
	expect(seg).toMatch(/PAPER/);
	expect(seg).toMatch(/HISTORIS/);
	expect(seg).toMatch(/sumber: OKX/);
	expect(seg).toMatch(/sumber: Stock Arjum/);
	expect(seg).toMatch(/lalu/);
});
