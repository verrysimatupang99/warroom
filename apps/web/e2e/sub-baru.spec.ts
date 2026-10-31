import { expect, test } from '@playwright/test';
import { KREDENSIAL, PESAN_SKIP, loginLewat, tungguSiap } from './util';

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

	test('polymarket menampilkan status standby, bukan galat', async ({ page }) => {
		await page.goto('/polymarket');
		await tungguSiap(page);
		await expect(page.getByText('Polymarket', { exact: false }).first()).toBeVisible();
		await expect(page.getByText(/ditangguhkan sementara/)).toBeVisible();
		expect(await page.locator('body').innerText()).not.toContain('GAGAL MEMUAT');
	});

	test('sistem → kebijakan menampilkan gate dan parameter aktif', async ({ page }) => {
		await page.goto('/sistem');
		await tungguSiap(page);
		await page.getByRole('tab', { name: 'Kebijakan', exact: true }).click();
		await expect(page.getByText('Gate yang berlaku')).toBeVisible({ timeout: 20000 });
		await expect(page.getByText('Parameter aktif')).toBeVisible();
		expect(await page.locator('body').innerText()).not.toContain('GAGAL MEMUAT');
	});

});
