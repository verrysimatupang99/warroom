/**
 * Penjaga langkah IDX (7 Okt, permintaan pemilik: "bagian langkah-langkah IDX bisa
 * dijelaskan ulang ga?"). Dua hal yang diuji:
 * 1. Tab Sinyal menampilkan 6 langkah BERURUTAN (1..6) — penomoran tidak boleh melompat;
 * 2. Tab lain (Aliran/Bandarmologi/BSJP) TIDAK menampilkan nomor langkah (konteks beda).
 */
import { expect, test } from '@playwright/test';

test('IDX: enam langkah berurutan di tab Sinyal', async ({ page }) => {
  await page.goto('/idx?sub=sinyal');
  await expect(page.getByText('LANGKAH 1').first()).toBeVisible({ timeout: 25000 });
  const t = await page.locator('body').innerText();
  const urut = ['LANGKAH 1', 'LANGKAH 2', 'LANGKAH 3', 'LANGKAH 4', 'LANGKAH 5', 'LANGKAH 6'];
  let posisi = -1;
  for (const l of urut) {
    const i = t.indexOf(l);
    expect(i, `${l} harus ada`).toBeGreaterThan(-1);
    expect(i, `${l} harus setelah langkah sebelumnya`).toBeGreaterThan(posisi);
    posisi = i;
  }
  // penjelasan arti tiap langkah ikut tampil
  expect(t).toContain('bahan mentah');
  expect(t).toContain('Layak dipercaya');
  console.log('--- LANGKAH IDX ---');
  console.log(t.slice(t.indexOf('Halaman ini dibaca'), t.indexOf('Halaman ini dibaca') + 900));
});

for (const sub of ['aliran', 'bandarmologi', 'bsjp']) {
  test(`IDX: tab ${sub} tanpa nomor langkah`, async ({ page }) => {
    await page.goto(`/idx?sub=${sub}`);
    await page.waitForTimeout(1200);
    const t = await page.locator('body').innerText();
    expect(t).not.toContain('LANGKAH 1');
  });
}
