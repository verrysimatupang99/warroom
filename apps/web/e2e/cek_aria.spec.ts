/**
 * Pemindai nama aksesibel (temuan QA eksternal 7 Okt):
 * "Ikon-only controls perlu accessible name … setiap tombol harus memiliki aria-label
 *  yang menjelaskan fungsi, bukan hanya simbol visual."
 *
 * Tes ini TIDAK menebak dari kode — ia memeriksa DOM yang benar-benar dirender dan
 * melaporkan elemen interaktif yang tidak punya nama aksesibel (teks/aria-label/title).
 */
import { expect, test } from '@playwright/test';

const HALAMAN = [
	'/',
	'/crypto?sub=cockpit',
	'/crypto?sub=setup',
	'/crypto?sub=ukur',
	'/crypto?sub=eksekusi',
	'/polymarket?sub=setup-b',
	'/polymarket?sub=riset',
	'/idx?sub=sinyal',
	'/idx?sub=bsjp',
	'/forex?sub=struktur',
	'/gmgn?sub=radar',
	'/gmgn?sub=lp',
	'/gmgn?sub=memecoin',
	'/sistem',
	'/sistem?sub=event',
	'/sistem?sub=dataset',
	'/riset',
	'/cara-kerja',
	'/bantuan',
	'/info'
];

test('tidak ada kontrol tanpa nama aksesibel', async ({ page }) => {
	const temuan: string[] = [];
	for (const rute of HALAMAN) {
		await page.goto(rute);
		await page.waitForTimeout(1800);
		const daftar = await page.evaluate(() => {
			const keluar: { tag: string; teks: string; kelas: string }[] = [];
			for (const el of Array.from(
				document.querySelectorAll('button, a[href], input:not([type="hidden"]), select, textarea')
			)) {
				const e = el as HTMLElement;
				if (e.closest('[aria-hidden="true"]')) continue;
				const teks = (e.innerText || '').trim();
				// input/select/textarea: nama bisa datang dari placeholder atau label
				const ph = e.getAttribute('placeholder') || '';
				const id = e.getAttribute('id') || '';
				const label = id ? document.querySelector(`label[for="${id}"]`)?.textContent || '' : '';
				const aria = e.getAttribute('aria-label') || e.getAttribute('title') || '';
				const nama = (e.getAttribute('aria-labelledby') || '').trim();
				// nama aksesibel dianggap ada bila teks cukup informatif, atau ada aria/title
				const informatif = teks.replace(/[\s·•⋯⚠🔔↕▲▼]+/g, '').length >= 2;
				if (!aria && !nama && !informatif && !ph.trim() && !label.trim()) {
					keluar.push({ tag: e.tagName.toLowerCase(), teks, kelas: e.className.toString().slice(0, 60) });
				}
			}
			return keluar;
		});
		for (const d of daftar) temuan.push(`${rute} :: <${d.tag}> "${d.teks}" .${d.kelas}`);
	}
	console.log('--- TANPA NAMA AKSESIBEL ---\n' + (temuan.join('\n') || '(bersih)'));
	expect(temuan, `kontrol tanpa nama aksesibel:\n${temuan.join('\n')}`).toHaveLength(0);
});
