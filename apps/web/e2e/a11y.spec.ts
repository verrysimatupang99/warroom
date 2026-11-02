import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';
import { KREDENSIAL, PESAN_SKIP, RUTE, loginLewat } from './util';

/**
 * A11y (W8): jalankan axe pada /masuk (selalu) dan 7 rute (butuh sesi).
 * Ambang: **0 pelanggaran critical & serious** — pelanggaran lain (moderate/minor,
 * mis. kontras) dilaporkan di output tapi tidak menggagalkan (butuh penilaian manusia).
 */
async function periksa(page: Page): Promise<void> {
	const hasil = await new AxeBuilder({ page }).analyze();
	const serius = hasil.violations.filter((v) => v.impact === 'critical' || v.impact === 'serious');
	expect(serius.map((v) => `${v.id}: ${v.help}`)).toEqual([]);
}

test('a11y /masuk', async ({ page }) => {
	await page.goto('/masuk');
	await periksa(page);
});

test.describe('a11y 7 rute', () => {
	test.skip(!KREDENSIAL.user || !KREDENSIAL.pass, PESAN_SKIP);
	test.beforeEach(async ({ page }) => {
		expect(await loginLewat(page)).toBe(true);
	});
	for (const rute of RUTE) {
		test(`a11y ${rute}`, async ({ page }) => {
			await page.goto(rute);
			await expect(page.locator('h1').first()).toBeVisible();
			await periksa(page);
		});
	}
});
