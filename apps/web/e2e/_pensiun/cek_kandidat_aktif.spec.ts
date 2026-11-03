/**
 * Penjaga panel "Kandidat Aktif" (audit 7 Okt).
 *
 * Latar: daftar AREA_KEYS memuat kunci "signal", tetapi kind `signal` TIDAK pernah
 * sampai ke UI — AREA_EXTRA hanya menerima pasangan (kind, key) tetap, sedangkan
 * kandidat punya kunci per pair (`signal/AAVEUSDT`, …). Akibatnya dashboard tidak
 * pernah menampilkan kandidat yang sedang hidup.
 *
 * Sekarang: fakta signal disajikan (hanya yang TTL-nya belum lewat) dan dirender
 * sebagai kartu. Tes ini mengunci dua hal: panelnya ada, dan harga mikro tidak
 * dibulatkan jadi "0,00" (bug yang ikut ditemukan).
 */
import { expect, test } from '@playwright/test';

test('crypto Setup: panel Kandidat Aktif tampil dengan harga benar', async ({ page }) => {
  await page.goto('/crypto?sub=setup');
  await expect(page.getByText('Kandidat Aktif (ledger gate)').first()).toBeVisible({ timeout: 25000 });
  const t = await page.locator('body').innerText();
  const i = t.indexOf('Kandidat Aktif');
  const panel = t.slice(i, i + 900);
  expect(panel).toContain('hidup');
  expect(panel).toMatch(/ENTRY/);
  // tidak boleh ada harga yang dibulatkan jadi nol
  expect(panel).not.toMatch(/ENTRY\s*\n?\s*0,00(\s|$)/);
  console.log('--- KANDIDAT ---\n' + panel.slice(0, 420));
});
