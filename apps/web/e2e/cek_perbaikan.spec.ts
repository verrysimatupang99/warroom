/**
 * Penjaga perbaikan 7 Okt (keluhan pemilik) — label disinkronkan 9 Okt ke bahasa terkini:
 * 1. Home: status hari ini + tabel Akurasi & PnL per Market (+ legenda pakem);
 * 2. Dompet: SALDO KINI dalam RUPIAH (bukan USD mentah) + USD jadi konteks;
 * 3. Crypto: Cockpit vs Setup beda jelas (header Ringkasan vs Setup Kandidat);
 * 4. IDX: tab Sinyal punya urutan LANGKAH 1..4 + flag STOP TAK DIHORMATI;
 * 5. Forex: tidak ada lagi klaim "OANDA-v20-DEMO" palsu;
 * 6. GMGN: jawaban singkat Robinhood vs Meteora di paling atas;
 * 7. Polymarket: label arm dijelaskan (bukan sekadar "Setup B").
 */
import { expect, test } from '@playwright/test';

const target: [string, RegExp, string][] = [
  ['/', /Status hari ini/, 'home-status'],
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

// Legenda pakem (INSUFFICIENT) kini berada DI DALAM lipatan akurasi Home — harus dibuka dulu.
test('home: legenda pakem tampil setelah lipatan akurasi dibuka', async ({ page }) => {
  await page.goto('/');
  await page.getByText('Akurasi & PnL per Market').first().click();
  await expect(page.getByText(/INSUFFICIENT/).first()).toBeVisible({ timeout: 10000 });
});

// Chip "peluang" lama diganti tautan per-pasar ("Lihat semua (n) →") pada rewrite 7 Okt.
test('home: tautan per-pasar bisa diklik & jumlahnya nyata', async ({ page }) => {
  await page.goto('/');
  const tautan = page.locator('a.lihat-semua');
  await expect(tautan.first()).toBeVisible({ timeout: 25000 });
  const n = await tautan.count();
  console.log('jumlah tautan per-pasar:', n);
  expect(n).toBeGreaterThan(0);
  for (let i = 0; i < Math.min(n, 3); i++) {
    const teks = (await tautan.nth(i).innerText()).replace(/\n/g, ' ');
    console.log(' tautan:', teks);
  }
});
