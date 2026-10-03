import { expect, test } from '@playwright/test';
import { KREDENSIAL, PESAN_SKIP } from './util';

/** Guard sesi + alur masuk (W7/W8). */
test('tanpa sesi → diarahkan ke /masuk', async ({ page }) => {
	await page.goto('/crypto');
	await expect(page).toHaveURL(/\/masuk/);
	await expect(page.getByTestId('masuk')).toBeVisible();
	await expect(page.getByRole('heading', { name: 'Masuk War Room' })).toBeVisible();
});

test('kredensial salah → pesan galat dari API, bukan diam', async ({ page }) => {
	await page.goto('/masuk');
	await page.getByLabel('username').fill('tidak-ada-user');
	await page.getByLabel('sandi').fill('salah-sekali');
	await page.getByRole('button', { name: 'masuk' }).click();
	await expect(page.getByRole('alert')).toContainText(/tidak sah|gagal|kredensial/i);
});

test('kredensial benar → masuk ke Ringkas', async ({ page }) => {
	test.skip(!KREDENSIAL.user || !KREDENSIAL.pass, PESAN_SKIP);
	await page.goto('/masuk');
	await page.getByLabel('username').fill(KREDENSIAL.user);
	await page.getByLabel('sandi').fill(KREDENSIAL.pass);
	await page.getByRole('button', { name: 'masuk' }).click();
	await expect(page).toHaveURL(/\/$/);
	await expect(page.getByRole('heading', { name: 'Ringkas' })).toBeVisible();
});
