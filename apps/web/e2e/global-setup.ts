/**
 * Setup global (7 Okt): login SEKALI, simpan sesi, pakai ulang di semua tes.
 *
 * Kenapa: tiap tes yang login sendiri menghabiskan jatah rate-limit (429 setelah
 * belasan request) — gejalanya menyesatkan ("8 tes pertama lewat, sisanya gagal",
 * seperti server mati, padahal justru pembatas lajunya yang bekerja).
 * Sesi disimpan ke file state dan dipakai lewat `storageState`.
 */
import { chromium, type FullConfig } from '@playwright/test';
import fs from 'node:fs';

export default async function globalSetup(config: FullConfig) {
  const baseURL = config.projects[0]?.use?.baseURL ?? 'http://127.0.0.1:4173';
  const browser = await chromium.launch();
  const page = await browser.newPage();
  const r = await page.request.post(`${baseURL}/api/v1/auth/login`, {
    data: {
      username: process.env.WARROOM_E2E_USER,
      password: process.env.WARROOM_E2E_PASS
    }
  });
  if (!r.ok()) {
    // Jangan menelan kegagalan: tes harus tahu sesi tidak terbentuk.
    throw new Error(`login global gagal: HTTP ${r.status()}`);
  }
  await page.context().storageState({ path: 'e2e/.auth/sesi.json' });
  fs.mkdirSync('e2e/.auth', { recursive: true });
  await browser.close();
}
