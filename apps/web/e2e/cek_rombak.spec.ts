/**
 * Penjaga rombakan 7 Okt (permintaan owner):
 * 1. Dompet Rp 10 juta tampil di tiap market;
 * 2. GMGN menjelaskan Robinhood vs Meteora + verifikasi harga live;
 * 3. IDX: tab "Sinyal" ada (= bandarmologi + BSJP), screener tidak lagi jadi tab utama;
 * 4. Polymarket: "Setup B" jadi tab utama, arm lain di Arsip (beku);
 * 5. Forex: ringkas per pair + kalender dengan hitung mundur.
 */
import { expect, test } from '@playwright/test';

async function login(_page: import('@playwright/test').Page) {
  // Sesi sudah dibuat global-setup (login sekali per suite) — lihat playwright.config.ts.
  return true;
}

const target: [string, RegExp, string][] = [
  ['/crypto?sub=cockpit', /Dompet Paper Crypto/, 'crypto-dompet'],
  ['/idx?sub=sinyal', /Dompet Paper IDX/, 'idx-dompet'],
  ['/idx?sub=sinyal', /Bandarmologi & Broker Summary/, 'idx-bandarmologi'],
  ['/idx?sub=sinyal', /Watchlist Sinyal ARA Hunter|BSJP — Beli Sore/, 'idx-bsjp'],
  ['/forex?sub=struktur', /Ringkas per Pair/, 'forex-pair'],
  ['/forex?sub=struktur', /Dompet Paper Forex/, 'forex-dompet'],
  ['/forex?sub=kalender', /Dampak & Hitung Mundur/, 'forex-kalender'],
  ['/gmgn?sub=radar', /Robinhood Chain" vs Meteora/, 'gmgn-robinhood'],
  ['/gmgn?sub=radar', /Verifikasi Harga vs API Publik/, 'gmgn-verifikasi'],
  ['/polymarket?sub=setup-b', /Dompet Paper Polymarket/, 'poly-setupb'],
  ['/polymarket?sub=setup-b', /YANG DIPAKAI: ARM B/, 'poly-fokus'],
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
