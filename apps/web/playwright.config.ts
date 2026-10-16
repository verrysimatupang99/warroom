import { defineConfig, devices } from '@playwright/test';
import fs from 'node:fs';

/**
 * Kredensial e2e dibaca dari env; bila kosong, dicoba dari `~/.config/warroom/e2e.env`
 * (mode 600, TIDAK masuk repo):
 *
 *   WARROOM_E2E_USER=uji-web
 *   WARROOM_E2E_PASS=...
 *
 * Tes yang butuh sesi akan di-skip dengan alasan jelas bila kredensial tidak ada —
 * bukan lulus diam-diam.
 */
function bacaEnvFile(): void {
	const berkas = `${process.env.HOME}/.config/warroom/e2e.env`;
	let isi: string;
	try {
		isi = fs.readFileSync(berkas, 'utf8');
	} catch {
		return;
	}
	for (const baris of isi.split('\n')) {
		const m = baris.match(/^([A-Z0-9_]+)=(.*)$/);
		if (m && !process.env[m[1]]) process.env[m[1]] = m[2].trim();
	}
}
bacaEnvFile();

export default defineConfig({
	testDir: 'e2e',
	// Keliling seluruh rute+sub (QA) memang panjang; 45 dtk terlalu ketat di host ini.
	timeout: 120_000,
	// Login SEKALI untuk seluruh suite (7 Okt): tiap tes yang login sendiri menghabiskan
	// jatah rate-limit API (10 login/menit) dan gejalanya menyesatkan — "8 tes lewat,
	// sisanya gagal", seperti server mati padahal limiter bekerja. Sesi dipakai ulang.
	globalSetup: './e2e/global-setup.ts',
	expect: { timeout: 10_000 },
	fullyParallel: false,
	// Batasi worker: tiap worker memanggil loginLewat() di beforeEach, dan API punya
	// limiter 10 login/menit. Dengan workers=8 hasilnya 401 masal -> puluhan tes gagal
	// palsu (temuan audit 16 Okt: 7 tes rute.spec + a11y + qa-lengkap gagal di
	// expect(loginLewat()).toBe(true), bukan di UI). 2 worker cukup & stabil.
	workers: 2,
	// Satu retry: host ini juga menjalankan worker yang menulis DB tiap 30 dtk, jadi sesekali
	// ada navigasi yang bertabrakan. Retry TIDAK menyembunyikan flake — laporan Playwright
	// menandainya "flaky", jadi tetap terlihat saat meninjau hasil.
	retries: 1,
	reporter: [['list']],
	use: {
		// Jalur PRODUKSI: https://0xgunsl1ng3r.xyz (nginx + Let's Encrypt → web :3100 + API :8800).
		// Alternatif lokal: WARROOM_E2E_BASE=http://127.0.0.1:8081 (perlu `sudo systemctl start caddy`;
		// Caddy terpasang tapi dinonaktifkan agar nginx menjadi satu-satunya proxy).
		// Prasyarat: warroom-api + warroom-worker + warroom-web aktif; kredensial di
		// ~/.config/warroom/e2e.env.
		baseURL: process.env.WARROOM_E2E_BASE ?? 'https://0xgunsl1ng3r.xyz',
		trace: 'retain-on-failure',
		storageState: 'e2e/.auth/sesi.json'
	},
	projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }]
});
