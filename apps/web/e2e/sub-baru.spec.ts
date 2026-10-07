import { expect, test } from '@playwright/test';
import { KREDENSIAL, PESAN_SKIP, loginLewat } from './util';

/**
 * E2E sub baru (P4-T3/P5-T4): sub "dataset" di /polymarket menampilkan DatasetExplorer,
 * sub "kebijakan" di /sistem menampilkan daftar usulan parameter (ProposalCard).
 * Tanpa kredensial → skip dengan alasan.
 */
test.describe('sub dataset & kebijakan', () => {
	test.skip(!KREDENSIAL.user || !KREDENSIAL.pass, PESAN_SKIP);

	test.beforeEach(async ({ page }) => {
		expect(await loginLewat(page)).toBe(true);
	});

	test('polymarket → dataset menampilkan katalog dari fakta', async ({ page }) => {
		await page.goto('/polymarket');
		await page.getByRole('button', { name: 'Dataset', exact: true }).click();
		const isi = await page.locator('body').innerText();
		expect(isi).not.toContain('GAGAL MEMUAT');
		// DatasetExplorer punya data nyata (paired) — atau minimal EmptyState jujur, bukan galat.
		await expect(page.locator('[data-testid="dataset-explorer"]')).toBeVisible();
	});

	test('sistem → kebijakan menampilkan usulan parameter', async ({ page }) => {
		await page.goto('/sistem');
		// Tunggu tombol tab SIAP diklik: dulu klik dilakukan sebelum halaman interaktif
		// (dan sempat tertutup shell pra-hydration) → tes flaky, bukan fitur rusak.
		const tab = page.getByRole('button', { name: 'Kebijakan', exact: true });
		await expect(tab).toBeVisible({ timeout: 20000 });
		await tab.click();
		await expect(page.locator('[data-testid="proposal-list"], [data-testid="empty-state"]').first()).toBeVisible({ timeout: 20000 });
		const isi = await page.locator('body').innerText();
		expect(isi.toLowerCase()).toContain('usulan parameter');
		expect(isi).not.toContain('GAGAL MEMUAT');
	});
});
