/**
 * Setup global: login SEKALI, simpan sesi, pakai ulang di semua tes.
 *
 * Kenapa login sekali (7 Okt): tiap tes yang login sendiri menghabiskan jatah
 * rate-limit (429 setelah belasan request) — gejalanya menyesatkan ("8 tes pertama
 * lewat, sisanya gagal", seperti server mati, padahal justru pembatas lajunya yang
 * bekerja). Sesi disimpan ke file state dan dipakai lewat `storageState`.
 *
 * Diperbaiki 9 Okt (R1):
 *  - Sesi **selalu dibuat ulang** tiap run (hapus file lama dulu). Sebelumnya file
 *    sesi basi dipertahankan, sehingga bila sesi server tak lagi valid, SEMUA tes
 *    ber-sesi gagal serentak dengan gejala ambigu ("timeout", bukan "belum login").
 *  - Kegagalan login kini **jelas**: HTTP + isi respons dicetak, bukan sekadar status.
 *  - Direktori `.auth` dibuat SEBELUM sesi ditulis (sebelumnya ada urutan terbalik
 *    pada `fs.mkdirSync` yang tidak berbahaya tapi membingungkan).
 */
import { chromium, type FullConfig } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const SESI = 'e2e/.auth/sesi.json';

export default async function globalSetup(config: FullConfig) {
  const baseURL = config.projects[0]?.use?.baseURL ?? 'http://127.0.0.1:4173';

  // Selalu mulai dari nol: sesi lama TIDAK dipakai. Kalau login di bawah berhasil,
  // sesi baru ditulis. Kalau gagal, tes ber-sesi akan menuai kegagalan yang jelas
  // (bukan diam-diam memakai sesi basi).
  fs.mkdirSync(path.dirname(SESI), { recursive: true });
  try {
    fs.rmSync(SESI);
  } catch {
    /* tidak ada file lama — tidak masalah */
  }

  const user = process.env.WARROOM_E2E_USER;
  const pass = process.env.WARROOM_E2E_PASS;
  if (!user || !pass) {
    throw new Error(
      'kredensial e2e tidak tersedia (WARROOM_E2E_USER / WARROOM_E2E_PASS). ' +
        'Isi ~/.config/warroom/e2e.env — tes ber-sesi tidak boleh dilewati diam-diam.'
    );
  }

  const browser = await chromium.launch();
  try {
    const page = await browser.newPage();
    const r = await page.request.post(`${baseURL}/api/v1/auth/login`, {
      data: { username: user, password: pass }
    });
    if (!r.ok()) {
      const isi = await r.text().catch(() => '');
      throw new Error(
        `login global gagal: HTTP ${r.status()} ke ${baseURL}/api/v1/auth/login — ${isi.slice(0, 200)}`
      );
    }
    await page.context().storageState({ path: SESI });
  } finally {
    await browser.close();
  }
}
