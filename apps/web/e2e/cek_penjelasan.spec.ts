import { expect, test } from '@playwright/test';
for (const [sub, harap] of [
  ['setup', 'Enam aturan gate'],
  ['ukur', 'Pakem (satu standar bukti)'],
  ['eksekusi', 'Ledger & R']
] as const) {
  test(`penjelasan ${sub} ada & bisa dibuka`, async ({ page }) => {
    await page.goto('/crypto?sub=' + sub);
    const tombol = page.getByRole('button', { name: /Cara membaca|Metode yang dipakai|Apa yang dimaksud/ }).first();
    await expect(tombol).toBeVisible({ timeout: 25000 });
    await tombol.click();
    await expect(page.getByText(harap, { exact: false }).first()).toBeVisible({ timeout: 5000 });
  });
}
