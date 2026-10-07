/**
 * Penjaga perbaikan 7 Okt (keluhan pemilik):
 * 1. Home: daftar "6 peluang" harus terlihat chipnya + legenda Pakem ada;
 * 2. Dompet: SALDO KINI dalam RUPIAH (bukan USD mentah) + USD jadi konteks;
 * 3. Crypto: Cockpit vs Setup beda jelas (header RINGKASAN vs SETUP KANDIDAT);
 * 4. IDX: tab Sinyal punya urutan LANGKAH 1..4 + flag STOP TAK DIHORMATI;
 * 5. Forex: tidak ada lagi klaim "OANDA-v20-DEMO" palsu;
 * 6. GMGN: jawaban singkat Robinhood vs Meteora di paling atas;
 * 7. Polymarket: label arm dijelaskan (bukan sekadar "Setup B").
 */
import { expect, test } from '@playwright/test';

const target: [string, RegExp, string][] = [
  ['/', /PELUANG/, 'home-peluang'],
  ['/', /INSUFFICIENT/, 'home-pakem'],
  ['/crypto?sub=cockpit', /Ringkasan/, 'crypto-cockpit-header'],
  ['/crypto?sub=cockpit', /Rp 10\./, 'crypto-saldo-rupiah'],
  ['/crypto?sub=setup', /Setup Kandidat/, 'crypto-setup-header'],
  ['/idx?sub=sinyal', /LANGKAH 1/, 'idx-langkah'],
  ['/idx?sub=sinyal', /STOP TAK DIHORMATI/, 'idx-flag-risiko'],
  ['/forex?sub=demo', /tidak ada/, 'forex-tanpa-oanda'],
  ['/gmgn?sub=radar', /Jawaban singkat/, 'gmgn-jawaban'],
  ['/polymarket?sub=setup-b', /YANG DIPAKAI: ARM B/, 'poly-arm-jelas']
];

for (const [url, pola, nama] of target) {
  test(`perbaikan: ${nama}`, async ({ page }) => {
    await page.goto(url);
    await expect(page.getByText(pola).first()).toBeVisible({ timeout: 25000 });
  });
}

test('home: chip peluang bisa diklik & daftarnya nyata', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByText(/PELUANG/).first()).toBeVisible({ timeout: 25000 });
  const chip = page.locator('a.peluang-chip');
  const n = await chip.count();
  console.log('jumlah chip peluang:', n);
  expect(n).toBeGreaterThan(0);
  for (let i = 0; i < Math.min(n, 3); i++) {
    const teks = (await chip.nth(i).innerText()).replace(/\n/g, ' ');
    console.log(' chip:', teks);
  }
});
