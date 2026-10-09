/**
 * Tahap 1 (9 Okt): kartu "Gate live-trading — centang otomatis" di /idx.
 * Tiru dari desk IDX Tencent; angka dari fakta idx_akurasi (tidak dihitung di UI).
 * Verifikasi lewat ORIGIN PRODUKSI (baseURL playwright = 0xgunsl1ng3r.xyz).
 */
import { test, expect } from '@playwright/test';
import { KREDENSIAL, PESAN_SKIP, loginLewat, tungguSiap } from './util';

test.describe('/idx — kartu gate per setup', () => {
	test.skip(!KREDENSIAL.user || !KREDENSIAL.pass, PESAN_SKIP);

	test('kartu gate tampil dengan 4 syarat & label jujur', async ({ page }) => {
		expect(await loginLewat(page)).toBe(true);
		await page.goto('/idx?sub=sinyal');
		await tungguSiap(page);

		const kartu = page.getByText('Gate live-trading — centang otomatis');
		await expect(kartu).toBeVisible({ timeout: 15000 });

		// Keempat setup mesin IDX harus muncul di kartu.
		for (const nama of ['BSJP_STRONG', 'BSJP_ARA', 'ARA_HUNTER', 'INTRADAY']) {
			await expect(page.getByText(nama).first()).toBeVisible();
		}

		// Label kelayakan (salah satu dari dua) harus ada.
		const layak = page.getByText('LAYAK DINILAI');
		const belum = page.getByText('BELUM CUKUP — kumpulkan sampel');
		expect((await layak.count()) + (await belum.count())).toBeGreaterThan(0);

		// Syarat yang diperiksa harus tertulis apa adanya.
		await expect(page.getByText('Sampel tuntas (n≥30)').first()).toBeVisible();
		await expect(page.getByText('Ekspektasi bersih > 0').first()).toBeVisible();
	});
});
