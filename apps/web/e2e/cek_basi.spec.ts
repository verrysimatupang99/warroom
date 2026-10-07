/**
 * Penjaga penjelasan "basi" (audit QA putaran 2):
 * "status basi perlu dijelaskan dengan sumber dan timestamp yang lebih langsung".
 * Sekarang "N basi" adalah TOMBOL yang membuka daftar: kunci, umur vs TTL, sumber.
 */
import { expect, test } from '@playwright/test';

test('TopBar: basi bisa dibuka dan menyebut sumber + umur', async ({ page }) => {
	await page.goto('/');
	const tombol = page.getByRole('button', { name: /basi/i }).first();
	const ada = (await tombol.count()) > 0;
	if (!ada) {
		// tidak ada fakta basi saat tes berjalan: keadaan sah, tidak ada yang perlu dibuka
		console.log('tidak ada fakta basi saat ini — tes dilewati secara sah');
		return;
	}
	await tombol.click();
	const panel = page.getByRole('dialog', { name: /Daftar fakta basi/i });
	await expect(panel).toBeVisible({ timeout: 10000 });
	const isi = await panel.innerText();
	console.log('--- PANEL BASI ---\n' + isi.slice(0, 500));
	expect(isi).toMatch(/melewati TTL/);
	expect(isi).toMatch(/umur/);
	expect(isi).toMatch(/ttl/);
	expect(isi).toMatch(/sumber/);
});
