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
	// Sudah punya sesi dari global-setup (storageState)? Tidak perlu login baru — dan itu
	// lebih baik: limiter API hanya 10 login/menit per IP, sementara suite ini 115 tes.
	// Temuan audit 16 Okt: tes yang memaksa login ulang kalah lomba jatah dan gagal palsu
	// (expect(loginLewat()).toBe(true)) padahal sesinya sudah valid.
	const cek = await page.request.get('/api/v1/auth/me');
	if (cek.ok()) return true;

	// Belum ada sesi valid → login (dengan retry saat limiter 429 / 5xx).
	for (let i = 0; i < 5; i++) {
		const r = await page.request.post('/api/v1/auth/login', {
			data: { username: KREDENSIAL.user, password: KREDENSIAL.pass }
		});
		if (r.ok()) return true;
		// 401 = kredensial salah (jangan retry); 429/5xx = sementara (retry).
		if (r.status() === 401 || r.status() === 403) return false;
		// Limiter 10 login/menit -> satu slot ±6 dtk. Backoff 3s,6s,9s,12s cukup.
		await new Promise((res) => setTimeout(res, 3000 * (i + 1)));
	}
	return false;
}

export const RUTE = ['/', '/crypto', '/idx', '/forex', '/polymarket', '/gmgn', '/sistem'] as const;

/**
 * Tunggu aplikasi SIAP menerima interaksi.
 *
 * Pelajaran insiden 7 Okt ("web masih terus memuat"): elemen bisa sudah terlihat di DOM
 * tetapi listener Svelte belum terpasang (hydration belum selesai). Klik pada elemen
 * seperti itu hilang diam-diam → tes flaky yang sulit dilacak. Penanda `data-app-siap`
 * dipasang layout setelah aplikasi hidup, jadi menunggunya = menunggu hydration selesai.
 */
export async function tungguSiap(page: Page): Promise<void> {
	await page.waitForFunction(
		() =>
			!!document.querySelector('[data-app-siap]') ||
			// /masuk tidak memakai AppShell — di sana cukup menunggu form terlihat
			!!document.querySelector('form input[name="username"]'),
		undefined,
		{ timeout: 20000 }
	);
}
