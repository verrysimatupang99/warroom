/**
 * Penjaga pemisahan istilah (audit QA putaran 4, prioritas 3; disinkronkan 9 Okt 2026).
 *
 * Riwayat: Home dulu menulis "6 PELUANG" — satu kata untuk kandidat + posisi paper +
 * hasil yang belum lewat gate. Lalu dipisah jadi "KANDIDAT · N lolos gate" (jargon).
 *
 * 9 Okt 2026 pemilik: "makin susah aja dilihat webnya, terlalu pro, targetnya bot trading
 * doang" → judul turun ke bahasa manusia. Penjaganya TETAP sama maknanya: judul tidak boleh
 * mencampur "ada dipantau" dengan "layak dibeli", dan tidak boleh memakai kata "peluang"
 * sebagai judul tunggal.
 */
import { expect, test } from '@playwright/test';

test('Home: judul memisahkan yang dipantau dari yang layak dibeli', async ({ page }) => {
	await page.goto('/');
	await expect(page.getByText('STATUS HARI INI')).toBeVisible({ timeout: 25000 });
	// Tunggu DATA, bukan hanya judulnya: Home merender "BELUM ADA DATA" lebih dulu
	// sementara /sinyal/per-pasar masih dimuat (penyebab tes flaky yang sama seperti
	// insiden shell — "ada" belum berarti "sudah terisi").
	await expect(
		page.getByText(/Bot memantau|pasar layak dibeli|TIDAK ADA SINYAL|GAGAL SISTEM/).first()
	).toBeVisible({ timeout: 25000 });
	const t = await page.locator('body').innerText();
	const i = t.indexOf('STATUS HARI INI');
	const seg = t.slice(i, i + 420);
	console.log('--- JUDUL ---\n' + seg.slice(0, 260));

	// Bahasa manusia: "Bot memantau N pasar · belum ada yang layak dibeli" ATAU
	// "N pasar layak dibeli". Dua-duanya memisahkan dipantau vs layak dibeli.
	expect(seg).toMatch(/Bot memantau|layak dibeli/);
	// Kata "peluang" tidak boleh lagi jadi judul tunggal.
	expect(seg).not.toMatch(/\d+\s+PELUANG/);
});
