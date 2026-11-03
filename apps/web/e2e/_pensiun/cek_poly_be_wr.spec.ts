import { expect, test } from '@playwright/test';

/**
 * Kolom BE-WR di tabel Akurasi & PnL per Arm (Polymarket) — perbaikan per-halaman 10 Okt.
 * Menjaga: tabel menampilkan ambang impas di samping win-rate, sehingga "menang 80%"
 * tidak lagi terlihat bagus padahal rugi (arm B: WR 80,6% < BE-WR 82,5%).
 */
test('polymarket: tabel per-arm menampilkan kolom BE-WR', async ({ page }) => {
	const resp = await page.goto('/polymarket?sub=arsip');
	expect(resp?.status()).toBeLessThan(400);
	const tabel = page.locator('table', { hasText: 'Setup' }).filter({ hasText: 'Tuntas' }).first();
	await expect(tabel).toBeVisible({ timeout: 25000 });
	await expect(tabel.locator('th', { hasText: 'BE-WR' })).toBeVisible();

	const teks = await tabel.innerText();
	// Minimal satu ambang impas nyata harus muncul (mis. 82,5% atau 20,0%).
	expect(/\d+[.,]\d+\s*%/.test(teks)).toBe(true);
});
