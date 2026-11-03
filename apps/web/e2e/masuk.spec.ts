import { expect, test } from '@playwright/test';
import { KREDENSIAL, PESAN_SKIP } from './util';

/** Guard sesi + alur masuk (W7/W8). */
// Tes "tanpa sesi" HARUS tanpa cookie tersimpan — config global memasang storageState
// (login sekali per suite), jadi tanpa override ini halaman TIDAK diarahkan ke /masuk.
test('tanpa sesi → diarahkan ke /masuk', async ({ browser }) => {
	const ctx = await browser.newContext({ storageState: { cookies: [], origins: [] } });
	const page = await ctx.newPage();
	await page.goto('/crypto');
	await expect(page).toHaveURL(/\/masuk/);
	await expect(page.getByTestId('masuk')).toBeVisible();
	await expect(page.getByRole('heading', { name: 'WarRoom' })).toBeVisible();
	await ctx.close();
});

test('kredensial salah → pesan galat dari API, bukan diam', async ({ browser }) => {
	const ctx = await browser.newContext({ storageState: { cookies: [], origins: [] } });
	const page = await ctx.newPage();
	await page.goto('/masuk');
	await page.getByLabel('username').fill('tidak-ada-user');
	await page.getByLabel('sandi').fill('salah-sekali');
	await page.getByRole('button', { name: 'masuk' }).click();
	await expect(page.getByRole('alert')).toContainText(/tidak sah|gagal|kredensial/i);
	await ctx.close();
});

test('kredensial benar → masuk ke Ringkas', async ({ browser }) => {
	test.skip(!KREDENSIAL.user || !KREDENSIAL.pass, PESAN_SKIP);
	const ctx = await browser.newContext({ storageState: { cookies: [], origins: [] } });
	const page = await ctx.newPage();
	await page.goto('/masuk');
	await page.waitForSelector('form input[name="username"]', { timeout: 20_000 });

	// Login dari IP yang sama berulang kali kena limiter (429) — form tampak tidak jalan.
	// Ulangi beberapa kali dengan jeda; yang diuji perilaku login, bukan ketahanan limiter.
	let masuk = false;
	for (let i = 0; i < 5 && !masuk; i++) {
		await page.getByLabel('username').fill(KREDENSIAL.user);
		await page.getByLabel('sandi').fill(KREDENSIAL.pass);
		await page.getByRole('button', { name: 'masuk' }).click();
		try {
			await page.waitForURL(/\/(\?.*)?$/, { timeout: 12_000 });
			masuk = true;
		} catch {
			await page.waitForTimeout(4000 * (i + 1));
		}
	}
	expect(masuk, 'login harus berhasil (cek kredensial / limiter 429)').toBe(true);
	// Yang dijaga: sudah keluar dari /masuk dan halaman utama benar-benar render.
	// Judul h1 Home berganti lagi 22–23 Okt: dulu "WarRoom" (merek), kini PageHeader
	// dengan title="Ringkasan hari ini" dan eyebrow "War Room · Beranda". Assert
	// mengikuti UI yang ADA, bukan yang lama — maksud test tidak berubah.
	await expect(page.getByRole('heading', { name: /Ringkasan hari ini/i }).first()).toBeVisible();
	await ctx.close();
});
