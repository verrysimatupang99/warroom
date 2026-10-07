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
	const i = t.indexOf('MODEL BREACH');
	const seg = t.slice(i, i + 1200);
	console.log('--- MODEL BREACH ---\n' + seg.slice(0, 420));
	expect(seg).toMatch(/melebihi 1R/);
	expect(seg).toMatch(/≤1R:\s*\d+/);
	expect(seg).toMatch(/ekstrem >5R:\s*\d+/);
	expect(seg).toMatch(/CREATED/);
	expect(seg).toMatch(/bukan\s+posisi berjalan/);
});
