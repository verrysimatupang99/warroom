/**
 * Penjaga STATUS VISUAL UTAMA (audit QA putaran 3, prioritas 1):
 * "Jadikan PAPER / HISTORIS / BRUTO / LIVE SNAPSHOT sebagai status visual utama."
 *
 * Sebelumnya status ini tersebar di catatan kaki. Sekarang ia duduk di headline verdict
 * (badge), sebelum angka apa pun dibaca.
 */
import { expect, test } from '@playwright/test';

test('headline pasar: badge mode + BRUTO terlihat', async ({ page }) => {
	// Forex = BRUTO (spread/komisi broker belum ada di jurnal)
	await page.goto('/forex');
	const kepala = page.locator('section[aria-live="polite"]').first();
	await expect(kepala).toBeVisible({ timeout: 25000 });
	const t = await kepala.innerText();
	console.log('--- FOREX ---\n' + t.slice(0, 260));
	expect(t).toMatch(/PAPER/);
	expect(t).toMatch(/BRUTO/);

	// IDX = HISTORIS (mesin dibekukan). Banner MODEL BREACH hanya muncul bila ada
	// pelanggaran 1R; ledger IDX kini belum ada, jadi yang dijaga adalah badge mode
	// HISTORIS-nya — bukan keberadaan banner (lihat cek_invariant_idx.spec.ts).
	await page.goto('/idx');
	const kepalaIdx = page.locator('section[aria-live="polite"]').first();
	await expect(kepalaIdx).toBeVisible({ timeout: 25000 });
	const ti = await kepalaIdx.innerText();
	console.log('--- IDX ---\n' + ti.slice(0, 260));
	expect(ti).toMatch(/HISTORIS/);
});
