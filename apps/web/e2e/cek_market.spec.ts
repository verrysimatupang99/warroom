/**
 * Penjaga UI per-market (6 Okt): setiap market WAJIB menampilkan
 * (1) sinyal & entry setup, (2) akurasi per strategi — dari fakta snapshot
 * yang sama. Tes ini menangkap regresi kelas "data ada tapi blok tak dirender"
 * (kejadian nyata: blok IDX hanya muncul di tab screener, hilang di tab BSJP).
 */
import { expect, test } from '@playwright/test';

async function login(page) {
  const r = await page.request.post('/api/v1/auth/login', {
    data: { username: process.env.WARROOM_E2E_USER, password: process.env.WARROOM_E2E_PASS }
  });
  return r.ok();
}

const target = [
  ['/crypto?sub=setup', /Sinyal & Entry Setup \(Crypto\)/, /Akurasi per Strategi \(Crypto\)/],
  ['/forex?sub=struktur', /Sinyal & Entry Setup \(Forex\)/, /Akurasi per Strategi \(Forex\)/],
  ['/idx?sub=bsjp', /Sinyal & Entry Setup \(IDX\)/, /Akurasi Signal per Setup/],
  ['/polymarket?sub=arm', /Akurasi & PnL per Arm \(Polymarket\)/, /B kandidat/],
  ['/gmgn?sub=lp', /Akurasi & PnL LP Terukur/, /LP Terukur/]
];

test('semua market menampilkan sinyal + akurasi', async ({ page }) => {
  expect(await login(page)).toBe(true);
  for (const [url, a, b] of target as [string, RegExp, RegExp][]) {
    await page.goto(url);
    await expect(page.getByText(a).first()).toBeVisible({ timeout: 25000 });
    await expect(page.getByText(b).first()).toBeVisible({ timeout: 25000 });
    console.log('OK', url);
  }
});

test('cetak cuplikan crypto setup', async ({ page }) => {
  expect(await login(page)).toBe(true);
  await page.goto('/crypto?sub=setup');
  await expect(page.getByText(/Sinyal & Entry Setup \(Crypto\)/).first()).toBeVisible({ timeout: 25000 });
  const t = await page.locator('body').innerText();
  const i = t.indexOf('Sinyal & Entry Setup (Crypto)');
  console.log('--- CUP S1 ---');
  console.log(t.slice(i, i + 700));
});
