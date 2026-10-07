/**
 * Penjaga: shell pra-hydration WAJIB hilang setelah aplikasi hidup.
 *
 * Kenapa tes ini ada: 7 Okt 2026 pemilik melaporkan "web masih terus memuat, ga bisa
 * kebuka". Penyebabnya shell skeleton di app.html TIDAK PERNAH dihapus sehingga menutupi
 * aplikasi — padahal aplikasi sudah jalan (judul benar, DOM lengkap). Seluruh tes lama
 * lolos karena memakai `body.innerText`/textContent yang TETAP memuat konten aplikasi
 * walau tertutup lapisan lain. Pelajaran: tes harus mengukur yang TERLIHAT.
 */
import { expect, test } from '@playwright/test';

const HALAMAN = ['/', '/crypto?sub=cockpit', '/idx', '/masuk'];

for (const rute of HALAMAN) {
	test(`shell pra-hydration hilang & konten terlihat di ${rute}`, async ({ page }) => {
		await page.goto(rute);
		await page.waitForTimeout(2500);

		// 1) elemen shell TIDAK boleh ada / TIDAK boleh tampil
		const shell = await page.evaluate(() => {
			const el = document.getElementById('shell-muat');
			if (!el) return { ada: false, tampil: false };
			const cs = getComputedStyle(el);
			return { ada: true, tampil: cs.display !== 'none' && cs.visibility !== 'hidden' };
		});
		expect(shell.tampil, 'shell masih MENUTUPI halaman').toBe(false);

		// 2) yang TERLIHAT harus isi aplikasi, bukan skeleton.
		//    Diukur dari elemen teratas di titik tengah layar — inilah yang benar-benar
		//    dilihat mata, bukan textContent.
		if (rute !== '/masuk') {
			const atas = await page.evaluate(() => {
				const el = document.elementFromPoint(window.innerWidth / 2, window.innerHeight / 3);
				return el ? (el.closest('#shell-muat') ? 'shell' : 'aplikasi') : 'kosong';
			});
			expect(atas, `titik tengah layar ditempati: ${atas}`).toBe('aplikasi');
		}

		// 3) konten aplikasi punya tinggi nyata (bukan 0 karena tertutup)
		if (rute !== '/masuk') {
			const tinggi = await page.evaluate(() => {
				const k = document.getElementById('konten');
				return k ? k.getBoundingClientRect().height : 0;
			});
			expect(tinggi).toBeGreaterThan(200);
		}
	});
}
