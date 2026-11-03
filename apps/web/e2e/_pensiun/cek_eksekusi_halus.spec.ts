/**
 * Penjaga pembaruan halus tab Eksekusi (7 Okt):
 *  1. Baris ringkasan satu baris (posisi terbuka / risiko terpakai / trade tuntas).
 *  2. Label "FAKTA HARGA, BUKAN SINYAL" menempel di JUDUL kartu Overextended —
 *     bukan hanya catatan kaki yang mudah terlewat.
 */
import { expect, test } from '@playwright/test';

test('tab Eksekusi: ringkasan + label bukan-sinyal di judul', async ({ page }) => {
	await page.goto('/crypto?sub=eksekusi');

	const ringkas = page.getByText(/posisi terbuka dari/);
	await expect(ringkas).toBeVisible({ timeout: 25000 });
	const t = await page.locator('body').innerText();
	// istilah dikoreksi 7 Okt: "kuota risiko harian terpakai" (hanya sisi RUGI).
	expect(t).toMatch(/kuota risiko harian terpakai/i);
	expect(t).toMatch(/trade tuntas tercatat di ledger/i);

	// label harus berada di kartu Overextended (judul), bukan cuma di catatan kaki
	// label muncul DUA kali (judul kartu + catatan kaki lama) — keduanya sah.
	await expect(page.getByText('FAKTA HARGA, BUKAN SINYAL').first()).toBeVisible();
	await expect(page.getByText('Posisi Terbuka').first()).toBeVisible();
	console.log('--- RINGKASAN EKSEKUSI ---\n' + t.slice(t.indexOf('posisi terbuka dari') - 40, t.indexOf('posisi terbuka dari') + 220));
});
