import { expect, test } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { KREDENSIAL, PESAN_SKIP, RUTE, loginLewat, tungguSiap } from './util';

/**
 * Screenshot bukti (W8): 7 rute + /masuk, desktop 1440 dan mobile 390, full-page.
 * Disimpan ke `docs/bukti-p2/` supaya bisa ditinjau tanpa menjalankan app.
 */
const BUKTI_DIR = process.cwd().endsWith('apps/web')
	? path.resolve(process.cwd(), '../../docs/bukti-p2')
	: path.resolve(process.cwd(), 'docs/bukti-p2');

if (!fs.existsSync(BUKTI_DIR)) {
	fs.mkdirSync(BUKTI_DIR, { recursive: true });
}

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
			await page.screenshot({ path: `${BUKTI_DIR}/desktop-${nama}.png`, fullPage: true });

			await page.setViewportSize({ width: 390, height: 844 });
			await page.waitForTimeout(500);
			await page.screenshot({ path: `${BUKTI_DIR}/mobile-${nama}.png`, fullPage: true });
		});
	}

	// Sub P4-T3/P5-T4: riset (polymarket) & kebijakan (sistem).
	// 7 Okt: sub "Dataset" berganti nama menjadi "Riset" (keputusan owner) — dan SubNav
	// merender role="tab", bukan "button". Dua hal itu membuat tes lama gagal.
	const SUB: { rute: string; tombol: string; nama: string }[] = [
		{ rute: '/polymarket', tombol: 'Riset', nama: 'polymarket-riset' },
		{ rute: '/sistem', tombol: 'Kebijakan', nama: 'sistem-kebijakan' }
	];
	for (const s of SUB) {
		test(`screenshot ${s.nama}`, async ({ page }) => {
			await page.setViewportSize({ width: 1440, height: 900 });
			await page.goto(s.rute);
			await tungguSiap(page);
			const tab = page.getByRole('tab', { name: s.tombol, exact: true });
			await expect(tab).toBeVisible({ timeout: 20000 });
			await tab.click();
			await page.waitForTimeout(1200);
			await page.screenshot({ path: `${BUKTI_DIR}/desktop-${s.nama}.png`, fullPage: true });

			await page.setViewportSize({ width: 390, height: 844 });
			await page.waitForTimeout(500);
			await page.screenshot({ path: `${BUKTI_DIR}/mobile-${s.nama}.png`, fullPage: true });
		});
	}
});

test('screenshot /masuk', async ({ page }) => {
	await page.setViewportSize({ width: 1440, height: 900 });
	await page.goto('/masuk');
	await page.waitForTimeout(500);
	await page.screenshot({ path: `${BUKTI_DIR}/desktop-masuk.png`, fullPage: true });
	await page.setViewportSize({ width: 390, height: 844 });
	await page.screenshot({ path: `${BUKTI_DIR}/mobile-masuk.png`, fullPage: true });
});
