/**
 * Penjaga SEMANTIK risiko (bug nyata 7 Okt, ditemukan saat mengerjakan tab Eksekusi):
 *
 * `hari_ini_r` adalah PnL HARI INI dalam R — NEGATIF = rugi. Versi lama memakai
 * Math.abs() di RiskMeter dan statusRisikoDari, sehingga hari yang PROFIT (+4R)
 * ditampilkan sebagai "LIMIT TERCAPAI" dan "risiko terpakai 4R / 3R Max" — pembaca
 * menyimpulkan pelanggaran batas risiko padahal itu keuntungan.
 *
 * Kelas bug ini persis yang dikritik audit QA: angka benar, LABEL salah → kesimpulan salah.
 */
import { expect, test } from '@playwright/test';

test('RiskMeter: profit harian TIDAK dihitung sebagai risiko terpakai', async ({ page }) => {
	await page.goto('/crypto?sub=cockpit');
	await expect(page.getByText('Batas Risiko & Kapasitas').first()).toBeVisible({ timeout: 25000 });
	const t = await page.locator('body').innerText();

	const i = t.indexOf('Risiko Terpakai Hari Ini');
	expect(i).toBeGreaterThan(-1);
	const seg = t.slice(i, i + 260);
	console.log('--- RISIKO ---\n' + seg.slice(0, 200));

	// Bila hari ini profit (angka positif muncul sebagai "profit"), kuota terpakai
	// HARUS 0 R — bukan angka profitnya.
	if (/\(\+\d.*R profit, tidak memakai kuota\)/.test(seg)) {
		expect(seg).toMatch(/0,00 R \/ 3,00 R Max/);
		expect(seg).not.toMatch(/LIMIT TERCAPAI/);
	}
});
