/**
 * Uji "apakah CSP ENFORCE akan mematikan UI?" (audit QA putaran 2).
 *
 * CSP Report-Only di produksi tidak pernah mengumpulkan laporan (tanpa report-uri), jadi
 * "log bersih" tidak bisa dibuktikan dari server. Cara yang jujur: jalankan browser dengan
 * kebijakan yang SAMA dalam mode ENFORCE, buka halaman-halaman utama, dan kumpulkan
 * pelanggaran dari console. Kalau nol pelanggaran → enforce aman. Kalau ada → jangan naikkan.
 */
import { expect, test } from '@playwright/test';

const CSP =
	"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; " +
	"font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; " +
	"frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'";

const HALAMAN = ['/', '/crypto?sub=cockpit', '/polymarket', '/idx', '/forex', '/gmgn', '/sistem', '/cara-kerja'];

test('CSP enforce tidak memblokir apa pun di 8 halaman', async ({ page }) => {
	const pelanggaran: string[] = [];
	page.on('console', (m) => {
		const t = m.text();
		if (/Content Security Policy|Refused to (load|execute|connect|apply)/i.test(t)) pelanggaran.push(t.slice(0, 160));
	});
	await page.route('**/*', async (route) => {
		const r = await route.fetch();
		const h = { ...r.headers(), 'content-security-policy': CSP };
		await route.fulfill({ response: r, headers: h });
	});

	for (const rute of HALAMAN) {
		await page.goto(rute);
		await page.waitForTimeout(2200);
	}
	console.log('--- PELANGGARAN CSP (mode enforce) ---\n' + (pelanggaran.join('\n') || '(nol)'));
	expect(pelanggaran, `CSP enforce akan memblokir:\n${pelanggaran.join('\n')}`).toHaveLength(0);
});
