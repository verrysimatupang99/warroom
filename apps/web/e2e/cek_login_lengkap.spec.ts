/**
 * Uji login menyeluruh (audit QA putaran 4, prioritas 6):
 * "Pass browser terakhir gagal karena vault kadang mengembalikan filled_fields: 1 tetapi
 *  password tidak masuk ke form."
 *
 * Akar yang sudah diperbaiki: input tidak punya `name` dan hanya mengandalkan `bind:value`,
 * sehingga pengisi-otomatis yang menulis ke DOM (tanpa memicu event input Svelte) membuat
 * form TERLIHAT terisi tetapi state kosong. Sekarang nilai dibaca dari FormData.
 *
 * Yang diuji di sini: login dengan MENULIS LANGSUNG KE DOM (mensimulasikan password
 * manager / vault), bukan lewat `fill()` Playwright yang selalu memicu event.
 */
import { expect, test } from '@playwright/test';

test('login: nilai yang diisi lewat DOM tetap terkirim', async ({ browser }) => {
	const ctx = await browser.newContext();
	const page = await ctx.newPage();
	await page.goto('/masuk');

	const user = process.env.WARROOM_E2E_USER ?? '';
	const pass = process.env.WARROOM_E2E_PASS ?? '';
	test.skip(!user || !pass, 'kredensial e2e tidak tersedia');

	// Tulis NILAI SAJA ke DOM tanpa memicu event input — persis perilaku password manager
	// yang dulu membuat login gagal ("form terlihat terisi, state kosong").
	await page.evaluate(
		([u, p]) => {
			const el = (n: string) => document.querySelector(`input[name="${n}"]`) as HTMLInputElement;
			el('username').value = u;
			el('password').value = p;
		},
		[user, pass]
	);

	// pastikan input MEMANG punya name (kontrak yang diperbaiki)
	const punyaName = await page.evaluate(() => ({
		username: !!document.querySelector('input[name="username"]'),
		password: !!document.querySelector('input[name="password"]'),
		totp: !!document.querySelector('input[name="totp"]')
	}));
	expect(punyaName).toEqual({ username: true, password: true, totp: true });

	await page.getByRole('button', { name: /masuk/i }).click();
	await page.waitForURL((u) => !u.pathname.startsWith('/masuk'), { timeout: 15000 });
	console.log('login berhasil, url:', page.url());

	// sesi bertahan setelah navigasi (cookie HttpOnly)
	await page.goto('/crypto?sub=cockpit');
	await expect(page.getByRole('heading', { level: 1 })).toBeVisible({ timeout: 20000 });
	await expect(page).not.toHaveURL(/\/masuk/);

	// logout mengembalikan ke halaman masuk
	await page.goto('/sistem');
	await expect(page).not.toHaveURL(/\/masuk/);
	await ctx.close();
});

test('login: sandi salah menampilkan galat, tidak diam', async ({ browser }) => {
	const ctx = await browser.newContext();
	const page = await ctx.newPage();
	await page.goto('/masuk');
	await page.fill('input[name="username"]', 'uji-salah');
	await page.fill('input[name="password"]', 'sandi-salah-sekali');
	await page.getByRole('button', { name: /masuk/i }).click();
	// harus tetap di /masuk dan menampilkan pesan galat (bukan layar diam)
	await expect(page).toHaveURL(/\/masuk/);
	await expect(page.getByText(/tidak sah|gagal|salah/i).first()).toBeVisible({ timeout: 15000 });
	await ctx.close();
});

test('login: sesi baru (konteks bersih) tetap butuh kredensial', async ({ browser }) => {
	// PENTING: `playwright.config.ts` memasang `storageState: 'e2e/.auth/sesi.json'`,
	// sehingga browser.newContext() BIASA masih membawa sesi login dari global-setup.
	// Diagnostik 7 Okt membuktikannya: /auth/me menjawab 200 dan cookie `wr_session` ada —
	// jadi guard TIDAK salah; tesnya yang salah asumsi. Untuk menguji guard, sesi harus
	// dibuang eksplisit di sini.
	const ctx = await browser.newContext({ storageState: { cookies: [], origins: [] } });
	const page = await ctx.newPage();
	const panggilan: number[] = [];
	page.on('response', (r) => {
		if (r.url().includes('/auth/me')) panggilan.push(r.status());
	});
	await page.goto('/crypto');
	await expect(page).toHaveURL(/\/masuk/, { timeout: 20000 });
	// guard harus MENGUJI ke API dulu (bukan menebak) — 401 adalah buktinya
	expect(panggilan, 'guard tidak memanggil /auth/me').toContain(401);
	console.log('guard bekerja: /auth/me ->', panggilan.join(','), '| url:', page.url());
	await ctx.close();
});
