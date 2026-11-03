/**
 * Penjaga halaman Kinerja & Bukti (audit QA putaran 3).
 * Tujuh jawaban wajib terlihat berdampingan untuk semua pasar:
 * trade tuntas · win rate · total R · PnL · drawdown · biaya · periode + denominator.
 */
import { expect, test } from '@playwright/test';

test('Riset → Bukti: tabel tujuh kolom + denominator + label BRUTO', async ({ page }) => {
	await page.goto('/riset?sub=bukti');
	const tabel = page.locator('table').first();
	await expect(tabel).toBeVisible({ timeout: 25000 });

	for (const kolom of ['Trade tuntas', 'Win rate', 'Total R', 'PnL', 'Drawdown', 'Biaya', 'Periode']) {
		await expect(tabel.getByText(kolom, { exact: false }).first()).toBeVisible();
	}

	const t = await page.locator('body').innerText();
	console.log('--- BUKTI ---\n' + t.slice(t.indexOf('Trade tuntas') - 120, t.indexOf('Trade tuntas') + 700));

	// denominator wajib disebut
	expect(t).toMatch(/Denominator/i);
	expect(t).toMatch(/trade TUNTAS/i);
	// label biaya wajib ada untuk pasar yang brutto
	expect(t).toMatch(/BRUTO|net biaya/);
	// dan penjelasan populasi/pakem
	expect(t).toMatch(/INSUFFICIENT/);
});

test('rute lama /bukti dialihkan ke sub Bukti', async ({ page }) => {
	await page.goto('/bukti');
	await expect(page).toHaveURL(/riset\?sub=bukti/, { timeout: 15000 });
});
