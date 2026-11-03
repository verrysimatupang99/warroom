/**
 * Penjaga rombakan 7 Okt (permintaan owner), diperbarui 16 Okt setelah revisi total UI:
 * 1. Dompet Rp 10 juta tampil di tiap market;
 * 2. GMGN menjelaskan Robinhood vs Meteora + verifikasi harga live;
 * 3. IDX: tab "Sinyal" ada (= bandarmologi + BSJP), screener tidak lagi jadi tab utama;
 * 4. Polymarket: "Setup B" jadi tab utama, arm lain di Arsip (beku);
 * 5. Forex: zona & sinyal mesin + dompet paper forex.
 */
import { expect, test } from '@playwright/test';

async function login(_page: import('@playwright/test').Page) {
  // Sesi sudah dibuat global-setup (login sekali per suite) — lihat playwright.config.ts.
  return true;
}

const target: [string, RegExp, string][] = [
  ['/crypto?sub=cockpit', /Dompet Paper Crypto/, 'crypto-dompet'],
  ['/idx?sub=sinyal', /Dompet Paper IDX/, 'idx-dompet'],
  ['/idx?sub=sinyal', /Bandarmologi/i, 'idx-bandarmologi'],
  ['/idx?sub=bsjp', /Beli Sore Jual Pagi|BSJP/, 'idx-bsjp'],
  ['/forex?sub=struktur', /Zona & Sinyal Mesin/, 'forex-zona'],
  ['/forex?sub=struktur', /Dompet Paper Forex/, 'forex-dompet'],
  ['/gmgn?sub=radar', /Robinhood Chain" vs Meteora/, 'gmgn-robinhood'],
  ['/gmgn?sub=radar', /Verifikasi Harga vs API Publik/, 'gmgn-verifikasi'],
  ['/polymarket?sub=setup-b', /Dompet Paper \$20/, 'poly-setupb'],
  ['/polymarket?sub=setup-b', /Favorit 0,70–0,95/, 'poly-fokus'],
  ['/polymarket?sub=arsip', /Arm beku \(bukti disimpan\)/, 'poly-arsip']
];

for (const [url, pola, nama] of target) {
  test(`rombakan: ${nama}`, async ({ page }) => {
    expect(await login(page)).toBe(true);
    await page.goto(url);
    await expect(page.getByText(pola).first()).toBeVisible({ timeout: 25000 });
  });
}

test('cuplikan dompet IDX + forex pair', async ({ page }) => {
  expect(await login(page)).toBe(true);
  await page.goto('/idx?sub=sinyal');
  await expect(page.getByText(/Dompet Paper IDX/).first()).toBeVisible({ timeout: 25000 });
  const t = await page.locator('body').innerText();
  const i = t.indexOf('Dompet Paper IDX');
  console.log('--- DOMPET IDX ---');
  console.log(t.slice(i, i + 900));
});
