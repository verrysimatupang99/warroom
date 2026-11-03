import { expect, test } from '@playwright/test';

/**
 * Kejujuran waktu sinyal (permintaan owner): pembaca harus tahu KAPAN sinyal dibuat
 * dan berapa umurnya — supaya tidak mengira sinyal lama masih segar.
 *
 * Disesuaikan 16 Okt (audit): kolom "DIBUAT" sudah tidak dipakai; timestamp kini
 * berbentuk "dibuat <tgl> <jam> WIB" atau "N j lalu".
 *
 * PENTING: FOREX & IDX sekarang tidak punya sinyal sama sekali (jurnal mesinnya belum
 * ada — "0 baris / Belum ada data sinyal"). Menuntut timestamp di sana adalah tes palsu.
 * Yang benar diuji: bila ADA sinyal → wajib ada waktu; bila TIDAK ADA → wajib ada
 * penjelasan jujurnya. Keduanya lulus; yang gagal adalah "kosong tanpa keterangan".
 */
for (const [url, jangkar, label] of [
  ['/crypto?sub=setup', 'Sinyal & Entry Setup (Crypto)', 'CRYPTO'],
  ['/forex?sub=struktur', 'Sinyal & Entry Setup (Forex)', 'FOREX'],
  ['/idx?sub=bsjp', 'Sinyal & Entry Setup (IDX)', 'IDX']
] as [string, string, string][]) {
  test(`timestamp sinyal ${label}`, async ({ page }) => {
    // Sesi dari global-setup (login sekali per suite).
    await page.goto(url);
    const j = jangkar.replace(/[()&]/g, '\\$&');
    await expect(page.getByText(new RegExp(j)).first()).toBeVisible({ timeout: 25000 });
    const t = await page.locator('body').innerText();
    const i = t.indexOf(jangkar);
    console.log(`--- ${label} ---`);
    console.log(t.slice(Math.max(0, i), Math.max(0, i) + 500));

    const adaSinyal = !/Belum ada data sinyal/i.test(t);
    if (adaSinyal) {
      // Wajib ada jejak waktu yang bisa dibaca manusia.
      const adaWaktu = /dibuat \d{1,2} \w+ \d{4}|sinyal \d+[jhm] lalu|\d{2}\.\d{2} WIB|\d{4}, \d{2}\.\d{2} WIB/i.test(t);
      expect(adaWaktu, 'sinyal ada → wajib menyebut waktu').toBe(true);
    } else {
      // Tidak ada sinyal → wajib menjelaskan sebabnya, bukan diam.
      expect(t, 'tanpa sinyal → wajib ada alasan').toMatch(/Belum ada data sinyal|belum ada/i);
      console.log(`(${label}: tidak ada sinyal — alasan tercantum, benar)`);
    }
  });
}
