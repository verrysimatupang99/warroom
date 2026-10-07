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

	test('polymarket → riset menampilkan katalog dataset dari fakta', async ({ page }) => {
		await page.goto('/polymarket');
		await tungguSiap(page);
		// Sub "Dataset" DIGANTI menjadi "Riset" pada 7 Okt (keputusan owner: fokus setup B;
		// verdict→setup-b, dataset→riset). Tes lama masih mencari tab "Dataset" sehingga
		// menunggu selamanya — tes usang, bukan fitur rusak.
		const tab = page.getByRole('tab', { name: 'Riset', exact: true });
		await expect(tab).toBeVisible({ timeout: 20000 });
		await tab.click();
		const isi = await page.locator('body').innerText();
		expect(isi).not.toContain('GAGAL MEMUAT');
		// DatasetExplorer punya data nyata (paired) — atau minimal EmptyState jujur, bukan galat.
		await expect(page.locator('[data-testid="dataset-explorer"]')).toBeVisible({ timeout: 20000 });
	});

	test('sistem → kebijakan menampilkan usulan parameter', async ({ page }) => {
		await page.goto('/sistem');
		await tungguSiap(page);
		// Tunggu tombol tab SIAP diklik: dulu klik dilakukan sebelum halaman interaktif
		// (dan sempat tertutup shell pra-hydration) → tes flaky, bukan fitur rusak.
		// Role sebenarnya = 'tab' (SubNav merender role="tab"). Saya sempat mengubahnya ke
		// 'button' karena salah mendiagnosis flaky — akibatnya tes gagal konsisten. Yang
		// benar: role='tab' + tungguSiap (hydration selesai) sebelum klik.
		const tab = page.getByRole('tab', { name: 'Kebijakan', exact: true });
		await expect(tab).toBeVisible({ timeout: 20000 });
		await tab.click();
		await expect(page.locator('[data-testid="proposal-list"], [data-testid="empty-state"]').first()).toBeVisible({ timeout: 20000 });
		const isi = await page.locator('body').innerText();
		expect(isi.toLowerCase()).toContain('usulan parameter');
		expect(isi).not.toContain('GAGAL MEMUAT');
	});
});
