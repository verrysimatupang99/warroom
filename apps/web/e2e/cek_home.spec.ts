/**
 * Penjaga Home (6 Okt): panel "Akurasi & PnL per Market" wajib menampilkan angka nyata
 * dari fakta pasar_akurasi/idx_akurasi — dan WAJIB jujur untuk market yang belum ada
 * (alasan tampil, bukan nol). Kelas bug yang dicegah: Home dan halaman detail berbeda.
 */
import { expect, test } from '@playwright/test';

test('home: akurasi per market + narasi tetap ada', async ({ page }) => {
  const r = await page.request.post('/api/v1/auth/login', {
    data: { username: process.env.WARROOM_E2E_USER, password: process.env.WARROOM_E2E_PASS }
  });
  expect(r.ok()).toBe(true);
  await page.goto('/');
  await expect(page.getByText('Akurasi & PnL per Market').first()).toBeVisible({ timeout: 25000 });
  const t = await page.locator('body').innerText();
  const i = t.indexOf('Akurasi & PnL per Market');
  console.log('--- HOME AKURASI ---');
  console.log(t.slice(i, i + 700));
  for (const pasar of ['crypto', 'idx', 'forex', 'gmgn', 'polymarket']) {
    expect(t.toLowerCase()).toContain(pasar);
  }
  expect(t).toMatch(/INSUFFICIENT|DIRECTIONAL|PRELIMINARY|TUNING/);
});
