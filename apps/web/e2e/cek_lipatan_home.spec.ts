/**
 * Penjaga pengurangan density Home (audit QA putaran 4, prioritas 4).
 *
 * Home punya tiga lapisan: keputusan → bukti ringkas → audit. Lapisan bukti (tabel
 * akurasi) dan audit (catatan per pasar) sekarang TERLIPAT: yang memindai cukup melihat
 * judul + kesimpulan; yang mau menelusuri membuka sendiri.
 *
 * Yang dijaga:
 *  1. Kedua lapisan itu TERTUTUP saat halaman dibuka (density turun).
 *  2. Kepalanya tetap terlihat (pembaca tahu ada apa) dan bisa dibuka.
 *  3. Setelah dibuka, isinya benar-benar ada (bukan lipatan kosong).
 */
import { expect, test } from '@playwright/test';

test('Home: tabel akurasi & catatan per pasar terlipat, bisa dibuka', async ({ page }) => {
	await page.goto('/');
	await expect(page.getByText('STATUS HARI INI')).toBeVisible({ timeout: 25000 });
	await expect(page.getByText(/KANDIDAT|TIDAK ADA SINYAL|GAGAL SISTEM/).first()).toBeVisible({ timeout: 25000 });

	// (1) kedua <details> tertutup
	const jumlah = await page.locator('details').count();
	expect(jumlah, 'harus ada lipatan di Home').toBeGreaterThanOrEqual(2);
	const terbuka = await page.locator('details[open]').count();
	expect(terbuka, 'lipatan harus TERTUTUP saat halaman dibuka').toBe(0);

	// (2) kepala terlihat
	const kepalaAkurasi = page.getByText('Akurasi & PnL per Market').first();
	await expect(kepalaAkurasi).toBeVisible();
	const kepalaCatatan = page.getByText('Catatan & skor per pasar').first();
	await expect(kepalaCatatan).toBeVisible();

	// (3) setelah dibuka, isinya ada
	await kepalaAkurasi.click();
	await expect(page.getByText('Tuntas', { exact: false }).first()).toBeVisible({ timeout: 10000 });
	await kepalaCatatan.click();
	const t = await page.locator('body').innerText();
	expect(t).toMatch(/pakem|INSUFFICIENT/i);
	console.log('--- HOME LIPATAN OK ---');
});
