/**
 * Penjaga MODEL BREACH (temuan QA eksternal 7 Okt, P0).
 * Keluhan: "saldo negatif & rugi -13,84R tanpa status khusus".
 * Sekarang: banner wajib tampil di kartu dompet IDX — jumlah pelanggaran, trade terburuk,
 * dan klasifikasi loss (gap/dalam/ekstrem) — plus sinyal CREATED dibedakan dari posisi berjalan.
 */
import { expect, test } from '@playwright/test';

test('IDX: banner MODEL BREACH + sinyal yatim terlihat', async ({ page }) => {
	await page.goto('/idx');
	await expect(page.getByText('MODEL BREACH').first()).toBeVisible({ timeout: 25000 });
	const t = await page.locator('body').innerText();
	// Ada DUA blok "MODEL BREACH" (banner invariant + peringatan saldo negatif).
	// Ambil blok PERTAMA yang memuat klasifikasi (≤1R/gap/dalam/ekstrem).
	const i = t.indexOf('≤1R:');
	const seg = t.slice(Math.max(0, i - 700), i + 700);
	console.log('--- MODEL BREACH ---\n' + seg.slice(0, 420));
	expect(seg).toMatch(/melebihi 1R/);
	expect(seg).toMatch(/≤1R:\s*\d+/);
	expect(seg).toMatch(/ekstrem >5R:\s*\d+/);
	expect(seg).toMatch(/CREATED/);
	expect(seg).toMatch(/bukan\s+posisi berjalan/);
	// QA putaran 2: saldo negatif wajib membawa konteks menonjol, bukan angka telanjang.
	expect(t).toMatch(/SALDO NEGATIF/);
	expect(t).toMatch(/modal habis/);
	// dan klasifikasi breach per setup terbit di tabel
	expect(t).toMatch(/ARA_HUNTER/);
	expect(t).toMatch(/94\/198/);
});
