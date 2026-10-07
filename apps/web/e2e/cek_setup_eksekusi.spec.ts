/**
 * Penjaga temuan 7 Okt (dari screenshot pemilik):
 *  1. Tab Setup: harga mikro tidak boleh tampil "0,00" (1000PEPE 0,00414775) — dulu
 *     seluruh kolom entry nol sehingga kartu tampak rusak.
 *  2. Tab Eksekusi: judulnya menjanjikan "posisi terbuka" — harus benar-benar menampilkannya.
 */
import { expect, test } from '@playwright/test';

test('Setup: kartu 1000PEPE tidak menampilkan entry 0,00', async ({ page }) => {
	await page.goto('/crypto?sub=setup');
	await expect(page.getByText('Kandidat Setup SMC Crypto')).toBeVisible({ timeout: 25000 });
	const t = await page.locator('body').innerText();
	const i = t.indexOf('1000PEPE');
	const seg = t.slice(i, i + 260);
	expect(seg).not.toMatch(/0,00(\s|$)/);
	expect(seg).toMatch(/0,0041/);
});

test('Eksekusi: menampilkan posisi terbuka', async ({ page }) => {
	await page.goto('/crypto?sub=eksekusi');
	await expect(page.getByText('Posisi Terbuka').first()).toBeVisible({ timeout: 25000 });
	const t = await page.locator('body').innerText();
	const i = t.indexOf('Posisi Terbuka');
	const seg = t.slice(i, i + 700);
	// jumlah n/maks muncul, dan bila ada posisi, pair-nya terlihat
	expect(seg).toMatch(/\d+\s*\/\s*\d+/);
	expect(seg).toMatch(/USDT/);
});
