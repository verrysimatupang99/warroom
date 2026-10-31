/**
 * US4.4 — responsif 390/768/1280/1920: tidak boleh ada horizontal scroll tak sengaja,
 * dan bar mobile hanya tampil di bawah 768px.
 */
import { test, expect } from '@playwright/test';
import { KREDENSIAL, PESAN_SKIP, loginLewat, tungguSiap } from './util';

test.skip(!KREDENSIAL.user || !KREDENSIAL.pass, PESAN_SKIP);

const HALAMAN = ['/forex?sub=ringkas', '/jurnal', '/crypto?sub=sinyal'];

test.describe('responsif lintas breakpoint', () => {
	for (const lebar of [390, 768, 1280, 1920]) {
		test(`lebar ${lebar}px tidak overflow`, async ({ page }) => {
			expect(await loginLewat(page)).toBe(true);
			await page.setViewportSize({ width: lebar, height: 900 });
			for (const jalur of HALAMAN) {
				await page.goto(jalur);
				await tungguSiap(page);
				await page.waitForTimeout(400);
				const lebih = await page.evaluate(
					() => document.documentElement.scrollWidth - window.innerWidth
				);
				expect(lebih, `${jalur} overflow ${lebih}px pada ${lebar}px`).toBeLessThanOrEqual(1);
			}
			if (lebar < 768) {
				await expect(page.locator('.mobile-header')).toBeVisible();
			} else {
				await expect(page.locator('.mobile-header')).toBeHidden();
			}
		});
	}
});
