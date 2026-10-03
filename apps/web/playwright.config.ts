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
	timeout: 45_000,
	expect: { timeout: 10_000 },
	fullyParallel: false,
	reporter: [['list']],
	use: {
		// Jalur produksi lokal: Caddy :8081 → web :3100 + API :8800 (same-origin, SSE lewat
		// proxy yang sama dengan produksi). Prasyarat: `warroom-web` + `caddy` aktif.
		// Untuk lingkungan lain, set WARROOM_E2E_BASE (mis. http://127.0.0.1:4173 dengan
		// `npm run preview` dan proxy di vite.config.ts).
		baseURL: process.env.WARROOM_E2E_BASE ?? 'http://127.0.0.1:8081',
		trace: 'retain-on-failure'
	},
	projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }]
});
