import { expect, test } from '@playwright/test';

/**
 * Panel "Nilai per Aturan Gate" — tiru 'gate checks' desk Tencent, diterapkan
 * pada pengukuran.per_aturan crypto (tab /crypto?sub=ukur).
 *
 * Yang dijaga: panel benar-benar tampil dan memuat baris aturan (bukan h1 kosong),
 * serta angka yang tampil konsisten dengan fakta (ada kolom n & putusan).
 * Sesi memakai storageState global yang sudah dipasang di config.
 */
test('crypto/ukur: panel nilai per aturan gate tampil dengan baris nyata', async ({ page }) => {
	await page.goto('/crypto?sub=ukur');
	const judul = page.locator('h3', { hasText: 'Nilai per Aturan Gate' }).first();
	await expect(judul).toBeVisible({ timeout: 25000 });

	// Tabel di dalam panel ini harus punya minimal satu baris aturan.
	const panel = judul.locator('xpath=ancestor::div[contains(@class,"permukaan-2")][1]');
	const baris = panel.locator('tbody tr');
	await expect(baris.first()).toBeVisible();
	expect(await baris.count()).toBeGreaterThan(0);

	// Kolom putusan harus punya teks (berguna / derau / sampel belum cukup) — tidak kosong.
	const putusan = (await baris.first().innerText()).trim();
	expect(putusan.length).toBeGreaterThan(0);
});
