import { expect, test } from '@playwright/test';
test('info: catatan riset terbaru terbaca', async ({ page }) => {
  await page.goto('/catatan?sub=catatan');
  await expect(page.getByText(/lp-robinhood|Catatan/i).first()).toBeVisible({ timeout: 25000 });
  const t = await page.locator('body').innerText();
  const i = t.indexOf('Catatan');
  console.log('--- INFO ---');
  console.log(t.slice(i, i + 700));
});

test('info: dokumen riset LP Robinhood terbaca di UI', async ({ page }) => {
  await page.goto('/catatan?sub=catatan');
  await expect(page.getByText(/Robinhood Chain.* vs Meteora|Riset LP/).first()).toBeVisible({ timeout: 25000 });
});
