import type { Page } from '@playwright/test';

/** Kredensial e2e dari env (diisi playwright.config.ts dari ~/.config/warroom/e2e.env). */
export const KREDENSIAL = {
	user: process.env.WARROOM_E2E_USER ?? '',
	pass: process.env.WARROOM_E2E_PASS ?? ''
};

export const PESAN_SKIP =
	'WARROOM_E2E_USER/WARROOM_E2E_PASS belum diisi (lihat ~/.config/warroom/e2e.env)';

/**
 * Login lewat API memakai `page.request` — cookie jar-nya SAMA dengan halaman, jadi sesi
 * ikut di semua navigasi berikutnya. (Memakai `request` fixture bisa beda jar karena
 * konteks browser dibuat lazily; itu pernah membuat tes ini gagal 401 padahal login ok.)
 */
export async function loginLewat(page: Page): Promise<boolean> {
	const r = await page.request.post('/api/v1/auth/login', {
		data: { username: KREDENSIAL.user, password: KREDENSIAL.pass }
	});
	return r.ok();
}

export const RUTE = ['/', '/crypto', '/idx', '/forex', '/polymarket', '/gmgn', '/sistem'] as const;
