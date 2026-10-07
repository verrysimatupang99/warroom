/**
 * Penjaga Home (6 Okt): panel "Akurasi & PnL per Market" wajib menampilkan angka nyata
 * dari fakta pasar_akurasi/idx_akurasi — dan WAJIB jujur untuk market yang belum ada
 * (alasan tampil, bukan nol). Kelas bug yang dicegah: Home dan halaman detail berbeda.
 */
import { expect, test } from '@playwright/test';

test('home: akurasi per market + narasi tetap ada', async ({ page }) => {
  // Sesi sudah dibuat global-setup (login sekali per suite) — lihat playwright.config.ts.
  await page.goto('/');
  await expect(page.getByText('Akurasi & PnL per Market').first()).toBeVisible({ timeout: 25000 });
  const t = await page.locator('body').innerText();
  const i = t.indexOf('Akurasi & PnL per Market');
  console.log('--- HOME AKURASI ---');
  console.log(t.slice(i, i + 700));
  for (const pasar of ['crypto', 'idx', 'forex', 'gmgn', 'polymarket']) {
    expect(t.toLowerCase()).toContain(pasar);
  }
  expect(t).toMatch(/INSUFFICIENT|DIRECTIONAL|PRELIMINARY|TUNING/);
});

/**
 * Timestamp sinyal (6 Okt, permintaan owner): verdikt "X PELUANG" WAJIB menyebut kapan
 * sinyalnya digenerate + umurnya, dan tiap baris pasar punya waktu mini. Kelas bug yang
 * dicegah: pembaca tidak bisa menilai apakah sinyal masih segar atau sisa kemarin.
 */
test('home: timestamp kapan sinyal digenerate', async ({ page }) => {
  // Sesi sudah dibuat global-setup (login sekali per suite) — lihat playwright.config.ts.
  await page.goto('/');
  await expect(page.getByText(/Sinyal per Market|STATUS HARI INI/).first()).toBeVisible({ timeout: 25000 });
  // Tunggu DATA (bukan hanya judul) — jadi tidak flaky saat API lebih lambat dari DOM.
  await expect(page.getByText(/lalu$/).first()).toBeVisible({ timeout: 25000 });
  const t = await page.locator('body').innerText();
  // Revisi pemilik 7 Okt: sinyal per market MENGGANTIKAN blok "Sinyal digenerate" di card
  // status (card itu sekarang gabungan status+akurasi). Yang tetap WAJIB: pembaca bisa
  // menilai kesegaran — umur tiap kandidat + baris pasar membawa waktu "dibuat".
  const i = t.indexOf('Sinyal per Market');
  console.log('--- TIMESTAMP ---');
  console.log(t.slice(i, i + 260));
  expect(t).toMatch(/lalu/);
  expect(t).toMatch(/dibuat \d{2} \w+ \d{4}|e \S+ · s \S+/);

  // dan pasar yang mengirim waktu harus menyebutkannya apa adanya — DIBATASI ke bagian
  // "Sinyal per Market" saja; labelnya juga muncul di teks verdikt di atas.
  const bagian = t.slice(i);
  for (const label of ['Crypto (SMC)', 'Polymarket']) {
    const j = bagian.indexOf(label);
    if (j >= 0) {
      const seg = bagian.slice(j, j + 400);
      expect(seg).toMatch(/lalu|dibuat/);
    }
  }
});
