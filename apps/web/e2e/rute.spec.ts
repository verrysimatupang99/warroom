import { expect, test } from '@playwright/test';
import { KREDENSIAL, PESAN_SKIP, RUTE, loginLewat } from './util';

/**
 * E2E 7 rute (W8): tiap halaman harus merender judulnya, tanpa "GAGAL MEMUAT", dan
 * tanpa error konsol. Tanpa kredensial → skip dengan alasan (bukan lulus diam-diam).
 */

/**
 * 503 dari endpoint yang bergantung upstream BUKAN galat render.
 *
 * War Room sengaja menjawab 503 `{"code":"not_available"}` ketika sebuah data
 * tidak punya padanan lokal — lihat routers/tencent.py: "jawab 503 dengan
 * alasannya, bukan angka karangan". Jadi kegagalan memuat sumber data yang
 * memang tidak tersedia (mis. jurnal edge butuh fill nyata dari Tencent) adalah
 * keadaan yang DIDOKUMENTASIKAN, bukan kerusakan halaman.
 *
 * Yang tetap dianggap galat: 500, exception JS, dan kegagalan non-503.
 */
function galatNyata(pesan: string): boolean {
	if (/Failed to load resource/i.test(pesan) && /\b503\b/.test(pesan)) return false;
	return true;
}

test.describe('7 rute dengan sesi', () => {
	test.skip(!KREDENSIAL.user || !KREDENSIAL.pass, PESAN_SKIP);

	test.beforeEach(async ({ page }) => {
		expect(await loginLewat(page)).toBe(true);
	});

	for (const rute of RUTE) {
		test(`rute ${rute} render tanpa galat`, async ({ page }) => {
			const galatKonsol: string[] = [];
			page.on('console', (msg) => {
				if (msg.type() === 'error') galatKonsol.push(msg.text());
			});
			await page.goto(rute);
			await expect(page.locator('h1').first()).toBeVisible();
			const isi = await page.locator('body').innerText();
			expect(isi).not.toContain('GAGAL MEMUAT');
			expect(galatKonsol.filter(galatNyata)).toEqual([]);
		});
	}

	test('SSE tersambung (badge live di TopBar)', async ({ page }) => {
		await page.goto('/');
		// Status live berubah dari "menyambung" ke "live"/"polling"; EventSource lewat
		// proxy harus benar-benar menerima frame awal.
		await expect(page.locator('text=/live|polling|n\\/a/i').first()).toBeVisible({ timeout: 20_000 });
	});
});
