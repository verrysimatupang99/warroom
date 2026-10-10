import { expect, test } from '@playwright/test';

/**
 * Status apa adanya di kartu Memecoin GMGN (perbaikan per-halaman 10 Okt).
 * Kartu "PAPER JALAN" hijau dulu berdiri sendiri tanpa hasil di dekatnya, sehingga
 * terlihat lebih baik dari kenyataan. Fakta snapshot/gmgn memang tidak punya vonis
 * gate dan statnya masih posisi terbuka — itu yang harus tampil apa adanya.
 */
test('gmgn: kartu memecoin menampilkan status hasil apa adanya', async ({ page }) => {
	const resp = await page.goto('/gmgn?sub=radar');
	expect(resp?.status()).toBeLessThan(400);
	const kartu = page.locator('div', { hasText: 'Memecoin' }).filter({ hasText: 'GMGN / FOMO' }).last();
	await expect(kartu).toBeVisible({ timeout: 25000 });
	// Status jujur harus muncul: "belum ada hasil tuntas" + hitungan posisi.
	await expect(kartu.getByText(/Belum ada hasil tuntas/i)).toBeVisible();
	// Hitungan posisi tuntas harus terbaca (mis. "0 tuntas"), bukan cuma judulnya.
	await expect(kartu.getByText(/\d+\s*tuntas/).first()).toBeVisible();
});
