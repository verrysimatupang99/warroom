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
	await expect(page.getByRole('heading', { name: 'Masuk War Room' })).toBeVisible();
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
	await page.getByLabel('username').fill(KREDENSIAL.user);
	await page.getByLabel('sandi').fill(KREDENSIAL.pass);
	await page.getByRole('button', { name: 'masuk' }).click();
	await expect(page).toHaveURL(/\/$/);
	// Home tidak lagi berjudul "Ringkas" — h1-nya "WarRoom" (merek). Yang dijaga: sudah keluar
	// dari /masuk dan halaman utama benar-benar render.
	await expect(page.getByRole('heading', { name: /WarRoom/ }).first()).toBeVisible();
	await ctx.close();
});
