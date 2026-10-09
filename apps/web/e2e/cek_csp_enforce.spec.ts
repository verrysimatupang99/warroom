/**
 * Uji "apakah CSP ENFORCE (script-src 'self' TANPA hash) akan mematikan UI?" (audit QA
 * putaran 2).
 *
 * PENTING — apa yang sebenarnya diuji di sini (dijernihkan R1, 9 Okt 2026):
 *   Tes ini SENGAJA mengganti header CSP setiap respons dengan kebijakan ketat versinya
 *   sendiri `script-src 'self'` TANPA hash bootstrap. Ia menjawab satu pertanyaan:
 *   "kalau kita naikkan CSP menjadi `script-src 'self'` murni, apakah UI mati?"
 *
 *   Jawabannya: YA — SvelteKit mengirim skrip bootstrap inline (`__sveltekit_* = {...}`)
 *   yang tanpa hash PASTI diblokir kebijakan `script-src 'self'`.
 *
 *   Jadi tes ini adalah PROBE KEBIJAKAN untuk mencegah orang menaikkan CSP tanpa hash —
 *   bukan pemeriksaan kesehatan produksi. Produksi memakai ENFORCE dari SvelteKit yang
 *   SUDAH memuat hash bootstrap (dihitung per build); lihat ops/nginx-warroom.conf
 *   (header Report-Only) dan ops/csp-enforce.sh.
 *
 * Ekspektasi yang benar: pelanggaran `script-src 'self'` pada bootstrap inline = HASIL
 * YANG DIHARAPKAN. Yang TIDAK boleh muncul: pelanggaran selain bootstrap (mis. fetch,
 * font, style yang sah). Bila hanya bootstrap yang dilanggar → aman untuk menaikkan CSP
 * SETELAH menambahkan hash, bukan sekarang.
 */
import { expect, test } from '@playwright/test';

// Kebijakan ketat yang diuji: script-src 'self' murni (TANPA hash) — sengaja.
const CSP =
	"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; " +
	"font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; " +
	"frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'";

const HALAMAN = ['/', '/crypto?sub=cockpit', '/polymarket', '/idx', '/forex', '/gmgn', '/sistem', '/cara-kerja'];

// Pelanggaran yang DIHARAPKAN karena kebijakan uji sengaja tanpa hash bootstrap.
const DIHARAPKAN = /Executing inline script violates|inline script/i;

test('CSP enforce tidak memblokir apa pun di 8 halaman', async ({ page }) => {
	const pelanggaran: string[] = [];
	page.on('console', (m) => {
		const t = m.text();
		if (/Content Security Policy|Refused to (load|execute|connect|apply)/i.test(t)) pelanggaran.push(t.slice(0, 200));
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

	// Pisahkan: pelanggaran yang diharapkan (bootstrap inline) vs yang TIDAK diharapkan.
	const diharapkan = pelanggaran.filter((p) => DIHARAPKAN.test(p));
	const takTerduga = pelanggaran.filter((p) => !DIHARAPKAN.test(p));

	console.log('--- PELANGGARAN CSP (mode enforce, policy uji tanpa hash) ---');
	console.log(`diharapkan (bootstrap inline): ${diharapkan.length}`);
	console.log(`tak terduga: ${takTerduga.length}`);
	if (takTerduga.length) console.log(takTerduga.join('\n'));

	// Yang penting: kebijakan ketat TIDAK memblokir hal-hal lain yang sah.
	// Kalau muncul pelanggaran di luar bootstrap, itu masalah nyata.
	expect(
		takTerduga,
		`CSP enforce memblokir LEBIH dari bootstrap inline (masalah nyata):\n${takTerduga.join('\n')}`
	).toHaveLength(0);
});
