/**
 * Penjaga Skor Bandarmologi (6 Okt): adopsi pola ihsgscreener. Wajib tampil di tab
 * Bandarmologi IDX dengan (1) skor angka, (2) kelas, (3) komponen yang bisa diaudit,
 * dan (4) peringatan bahwa ini alat baca — bukan bukti akumulasi/ajakan beli.
 */
import { expect, test } from '@playwright/test';

test('skor bandarmologi tampil dengan komponen + peringatan', async ({ page }) => {
  // Sesi sudah dibuat global-setup (login sekali per suite) — lihat playwright.config.ts.
  await page.goto('/idx?sub=bandarmologi');
  await expect(page.getByText('Skor Bandarmologi (0–100)').first()).toBeVisible({ timeout: 25000 });
  const t = await page.locator('body').innerText();
  const i = t.indexOf('Skor Bandarmologi (0–100)');
  const potongan = t.slice(i, i + 900);
  console.log('--- BANDAR ---\n' + potongan);
  expect(potongan).toMatch(/rasio_ats/);
  expect(potongan).toMatch(/bukan bukti akumulasi/i);
});
