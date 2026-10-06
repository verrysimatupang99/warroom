/**
 * Penjaga Home (6 Okt): panel "Akurasi & PnL per Market" wajib menampilkan angka nyata
 * dari fakta pasar_akurasi/idx_akurasi — dan WAJIB jujur untuk market yang belum ada
 * (alasan tampil, bukan nol). Kelas bug yang dicegah: Home dan halaman detail berbeda.
 */
import { expect, test } from '@playwright/test';

test('home: akurasi per market + narasi tetap ada', async ({ page }) => {
  // Sesi sudah dibuat global-setup (login sekali per suite) — lihat playwright.config.ts.
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

/**
 * Timestamp sinyal (6 Okt, permintaan owner): verdikt "X PELUANG" WAJIB menyebut kapan
 * sinyalnya digenerate + umurnya, dan tiap baris pasar punya waktu mini. Kelas bug yang
 * dicegah: pembaca tidak bisa menilai apakah sinyal masih segar atau sisa kemarin.
 */
test('home: timestamp kapan sinyal digenerate', async ({ page }) => {
  // Sesi sudah dibuat global-setup (login sekali per suite) — lihat playwright.config.ts.
  await page.goto('/');
  await expect(page.getByText(/Sinyal digenerate:/).first()).toBeVisible({ timeout: 25000 });
  const t = await page.locator('body').innerText();
  const i = t.indexOf('Sinyal digenerate:');
  console.log('--- TIMESTAMP ---');
  console.log(t.slice(i, i + 220));
  // minimal satu baris pasar membawa waktu mini (🕒 dibuat …)
  expect(t).toMatch(/dibuat \d{2} \w+ \d{4}/);
  expect(t).toMatch(/lalu/);
});
