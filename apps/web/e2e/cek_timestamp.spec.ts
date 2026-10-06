import { expect, test } from '@playwright/test';

for (const [url, jangkar, label] of [
  ['/crypto?sub=setup', 'Sinyal & Entry Setup (Crypto)', 'CRYPTO'],
  ['/forex?sub=struktur', 'Sinyal & Entry Setup (Forex)', 'FOREX'],
  ['/idx?sub=bsjp', 'Sinyal & Entry Setup (IDX)', 'IDX']
] as [string, string, string][]) {
  test(`kolom Dibuat ${label}`, async ({ page }) => {
    const r = await page.request.post('/api/v1/auth/login', {
      data: { username: process.env.WARROOM_E2E_USER, password: process.env.WARROOM_E2E_PASS }
    });
    expect(r.ok()).toBe(true);
    await page.goto(url);
    const j = jangkar.replace(/[()&]/g, '\\$&');
    await expect(page.getByText(new RegExp(j)).first()).toBeVisible({ timeout: 25000 });
    const t = await page.locator('body').innerText();
    const i = t.indexOf(jangkar);
    console.log(`--- ${label} ---`);
    console.log(t.slice(i, i + 420));
    expect(t).toContain('DIBUAT');
  });
}
