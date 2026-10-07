/**
 * Penjaga pemisahan istilah (audit QA putaran 4, prioritas 3):
 * "Jangan memakai 'peluang' untuk semua kategori."
 *
 * Home dulu menulis "6 PELUANG" yang mencampur kandidat, posisi paper, dan hasil yang
 * belum lewat gate. Sekarang judul memisahkan KANDIDAT dari yang LOLOS GATE.
 */
import { expect, test } from '@playwright/test';

test('Home: judul memisahkan kandidat dari yang lolos gate', async ({ page }) => {
	await page.goto('/');
	await expect(page.getByText('STATUS HARI INI')).toBeVisible({ timeout: 25000 });
	// Tunggu DATA, bukan hanya judulnya: Home merender "BELUM ADA DATA" lebih dulu
	// sementara /sinyal/per-pasar masih dimuat (penyebab tes flaky yang sama seperti
	// insiden shell — "ada" belum berarti "sudah terisi").
	await expect(page.getByText(/KANDIDAT|TIDAK ADA SINYAL|GAGAL SISTEM/).first()).toBeVisible({
		timeout: 25000
	});
	const t = await page.locator('body').innerText();
	const i = t.indexOf('STATUS HARI INI');
	const seg = t.slice(i, i + 420);
	console.log('--- JUDUL ---\n' + seg.slice(0, 260));

	expect(seg).toMatch(/KANDIDAT/);
	expect(seg).toMatch(/lolos gate/i);
	// kata "peluang" tidak boleh lagi jadi judul tunggal
	expect(seg).not.toMatch(/\d+\s+PELUANG/);
});
