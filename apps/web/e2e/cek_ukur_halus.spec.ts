/**
 * Penjaga pembaruan halus tab Ukur (7 Okt, arah desain "Serene Capital"):
 *  1. Baris ringkasan bahasa manusia di atas (kalimat, bukan angka telanjang).
 *  2. Tiga angka BESAR per kartu (trade/total R/win rate) di Lolos vs Ditolak.
 *  3. Tabel Akurasi per Strategi dalam mode RINGKAS (4 kolom) — dan benar-benar TAMPIL
 *     di tab Ukur (sebelumnya kode mati: kondisi sub==='ukur' ada di grid cockpit/setup).
 */
import { expect, test } from '@playwright/test';

test('tab Ukur: ringkasan, angka besar, akurasi ringkas', async ({ page }) => {
	await page.goto('/crypto?sub=ukur');

	// 1) ringkasan satu baris
	const ringkas = page.getByText(/kandidat yang dinilai/);
	await expect(ringkas).toBeVisible({ timeout: 25000 });
	const t = await page.locator('body').innerText();
	expect(t).toMatch(/lolos gate dan/);
	expect(t).toMatch(/selisih ekspektasi/);

	// 2) angka besar: kartu Lolos Gate punya label TRADE dan TOTAL R
	const kartu = page.getByText('Setup Lolos Gate').first();
	await expect(kartu).toBeVisible();
	expect(t).toMatch(/TRADE/i);
	expect(t).toMatch(/TOTAL R/i);
	expect(t).toMatch(/WIN RATE/i);

	// 3) akurasi ringkas: kolom "Ekspektasi R" ada, kolom padat (CI90/PnL) TIDAK ada di tab ini
	await expect(page.getByText('Akurasi per Strategi')).toBeVisible({ timeout: 15000 });
	expect(t).toMatch(/EKSPEKTASI R/i);
	expect(t).not.toMatch(/CI90/i);
	console.log('--- RINGKASAN ---\n' + t.slice(t.indexOf('kandidat yang dinilai') - 40, t.indexOf('kandidat yang dinilai') + 260));
});
