import type { Page } from '@playwright/test';

/** Kredensial e2e dari env (diisi playwright.config.ts dari ~/.config/warroom/e2e.env). */
export const KREDENSIAL = {
	user: process.env.WARROOM_E2E_USER ?? '',
	pass: process.env.WARROOM_E2E_PASS ?? ''
};

export const PESAN_SKIP =
	'WARROOM_E2E_USER/WARROOM_E2E_PASS belum diisi (lihat ~/.config/warroom/e2e.env)';

/**
 * Login lalu pastikan sesinya BENAR-BENAR dipakai halaman.
 *
 * Sejarah salah kaprah (diperbaiki 3 Nov): dulu diasumsikan `page.request` berbagi
 * cookie jar dengan halaman. Tidak. Cookie disimpan di konteks, tetapi browser
 * hanya mengirimnya bila atributnya mengizinkan — dan API menyetel `Secure=true`.
 * Di http://127.0.0.1 browser MENOLAK mengirim cookie Secure, jadi login 200 tapi
 * semua request sesi 401. Gejalanya menyesatkan ("verdict is not iterable").
 *
 * Perbaikannya di sisi konfigurasi: API uji dijalankan dengan
 * `WARROOM_COOKIE_SECURE=0` (lihat ci.yml). Fungsi ini tetap memeriksa ulang
 * dengan request BER-COOKIE sungguhan supaya kegagalan sesi muncul sebagai
 * pesan jelas, bukan sebagai galat acak di dalam spec.
 */
export async function loginLewat(page: Page): Promise<boolean> {
	// Sudah punya sesi dari global-setup (storageState)? Tidak perlu login baru — dan itu
	// lebih baik: limiter API hanya 10 login/menit per IP, sementara suite ini puluhan tes.
	// Temuan audit 16 Okt: tes yang memaksa login ulang kalah lomba jatah dan gagal palsu
	// (expect(loginLewat()).toBe(true)) padahal sesinya sudah valid.
	//
	// `page.request` TIDAK membawa cookie konteks, jadi jangan dipakai untuk memeriksa
	// sesi. Pakai `page.goto` — navigasi browser mengirim cookie sesuai aturannya.
	const cek = await page.request.get('/api/v1/auth/me');
	if (cek.ok()) return true;

	// Belum ada sesi valid → login (dengan retry saat limiter 429 / 5xx).
	for (let i = 0; i < 5; i++) {
		const r = await page.request.post('/api/v1/auth/login', {
			data: { username: KREDENSIAL.user, password: KREDENSIAL.pass }
		});
		if (r.ok()) {
			// Login 200 belum berarti sesi terpakai: bila cookie-nya Secure dan
			// halaman di HTTP, browser membuangnya. Buktikan lewat navigasi nyata.
			await page.goto('/');
			const hidup = await page.evaluate(async () => {
				const res = await fetch('/api/v1/auth/me', { credentials: 'same-origin' });
				return res.ok;
			});
			if (!hidup) {
				throw new Error(
					'login 200 tetapi sesi tidak terpakai oleh browser. Penyebab tersering: ' +
						'cookie wr_session ber-atribut Secure dikirim lewat HTTP. Jalankan API uji ' +
						'dengan WARROOM_COOKIE_SECURE=0 (lihat ci.yml).'
				);
			}
			return true;
		}
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
