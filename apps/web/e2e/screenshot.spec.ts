import { test } from '@playwright/test';
import { KREDENSIAL, PESAN_SKIP, RUTE, loginLewat } from './util';

/**
 * Screenshot bukti (W8): 7 rute + /masuk, desktop 1440 dan mobile 390, full-page.
 * Disimpan ke `docs/bukti-p2/` supaya bisa ditinjau tanpa menjalankan app.
 */
const NAMA: Record<string, string> = {
	'/': 'ringkas',
	'/crypto': 'crypto',
	'/idx': 'idx',
	'/forex': 'forex',
	'/polymarket': 'polymarket',
	'/gmgn': 'gmgn',
	'/sistem': 'sistem'
};

test.describe('screenshot bukti', () => {
	test.skip(!KREDENSIAL.user || !KREDENSIAL.pass, PESAN_SKIP);

	test.beforeEach(async ({ page }) => {
		await loginLewat(page);
	});

	for (const rute of RUTE) {
		test(`screenshot ${rute}`, async ({ page }) => {
			const nama = NAMA[rute] ?? rute.replaceAll('/', '-');
			await page.setViewportSize({ width: 1440, height: 900 });
			await page.goto(rute);
			await page.waitForTimeout(1500); // biar fakta & SSE tampil
			await page.screenshot({ path: `../../docs/bukti-p2/desktop-${nama}.png`, fullPage: true });

			await page.setViewportSize({ width: 390, height: 844 });
			await page.waitForTimeout(500);
			await page.screenshot({ path: `../../docs/bukti-p2/mobile-${nama}.png`, fullPage: true });
		});
	}
});

test('screenshot /masuk', async ({ page }) => {
	await page.setViewportSize({ width: 1440, height: 900 });
	await page.goto('/masuk');
	await page.waitForTimeout(500);
	await page.screenshot({ path: '../../docs/bukti-p2/desktop-masuk.png', fullPage: true });
	await page.setViewportSize({ width: 390, height: 844 });
	await page.screenshot({ path: '../../docs/bukti-p2/mobile-masuk.png', fullPage: true });
});
