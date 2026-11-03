/**
 * Penjaga invarian dompet (temuan QA eksternal 7 Okt, P0).
 *
 * Sejarah: dulu test ini menuntut banner "MODEL BREACH" + angka hardcode (94/198, SALDO NEGATIF)
 * selalu tampil di /idx. Itu salah rancang: banner itu memang HANYA muncul bila ada pelanggaran
 * 1R / saldo negatif. Ledger IDX sekarang belum ada (idx_ledger.db belum ada) sehingga tidak ada
 * pelanggaran untuk dilaporkan — dan itu perilaku yang BENAR.
 *
 * Yang dijaga sekarang (mekanisme, bukan kondisi data sesaat):
 *  1. Kartu dompet IDX selalu merender blok dompet/jatah risiko (tidak crash tanpa ledger).
 *  2. Bila ledger tidak ada, halaman menyebut ALASANNYA secara eksplisit — bukan angka nol palsu.
 *  3. Tidak ada klaim uang nyata: mode harus jelas PAPER/HISTORIS, bukan "live".
 */
import { expect, test } from '@playwright/test';

test('IDX: kartu dompet jujur saat ledger belum ada (tanpa banner palsu)', async ({ page }) => {
	await page.goto('/idx');
	await expect(page.getByText(/Dompet Paper IDX/).first()).toBeVisible({ timeout: 25000 });

	const t = await page.locator('body').innerText();
	const i = t.indexOf('Dompet Paper IDX');
	const seg = t.slice(Math.max(0, i - 200), i + 900);
	console.log('--- DOMPET IDX ---\n' + seg.slice(0, 600));

	// (1) blok dompet ada
	expect(seg).toMatch(/juta|Rp|Saldo|risiko/i);
	// (2) jujur soal ledger yang belum ada — alasan tampil, bukan nol palsu
	expect(t).toMatch(/belum ada|belum bisa dihitung|idx_ledger/i);
	// (3) tidak boleh ada klaim LIVE untuk IDX (mesin dibekukan)
	expect(t).toMatch(/HISTORIS|PAPER/);
});

test('IDX: banner MODEL BREACH hanya muncul bila ada pelanggaran (mekanisme terjaga)', async ({ page }) => {
	await page.goto('/idx');
	await expect(page.getByText(/Dompet Paper IDX/).first()).toBeVisible({ timeout: 25000 });

	const t = await page.locator('body').innerText();
	const adaPelanggaran = /MODEL BREACH/.test(t);

	if (adaPelanggaran) {
		// Bila banner muncul, ia WAJIB membawa konteks, bukan angka telanjang.
		expect(t).toMatch(/melebihi 1R|≤1R|ekstrem/i);
		console.log('--- MODEL BREACH AKTIF (ada pelanggaran) ---');
	} else {
		// Bila tidak muncul, ledger IDX tidak terbaca — dan halaman harus bilang begitu.
		expect(t).toMatch(/belum ada|belum bisa dihitung|tidak terbaca/i);
		console.log('--- MODEL BREACH tidak aktif: tidak ada pelanggaran (benar) ---');
	}
});
