// Rekam demo operating War Room: login -> navigasi -> klik tab -> scroll.
// Video disimpan ke videos/ (Playwright merekam tiap context).
const { chromium } = require('playwright');
const path = require('path');

const BASE = 'https://polywarroom.vps.webdock.cloud';
const OUT = path.resolve('videos');

(async () => {
  const browser = await chromium.launch({ args: ['--autoplay-policy=no-user-gesture-required'] });
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
    recordVideo: { dir: OUT, size: { width: 1920, height: 1080 } },
  });
  const page = await context.newPage();

  const wait = (ms) => page.waitForTimeout(ms);
  const hold = async (ms) => { await wait(ms); };

  // 1. Login sebagai demo
  await page.goto(BASE + '/masuk');
  await page.fill('#masuk-username', 'demo');
  await page.fill('#masuk-sandi', 'kiroween2026');
  await page.click('button[type="submit"]');
  await page.waitForURL(BASE + '/');
  await hold(3500);

  // 2. Beranda: scroll pelan menunjukkan ringkasan + setup entry
  await page.mouse.wheel(0, 400);
  await hold(2000);
  await page.mouse.wheel(0, -400);
  await hold(1500);

  // 3. Crypto: klik tab Sinyal lalu Uji
  await page.goto(BASE + '/crypto');
  await hold(2500);
  await page.click('text=Sinyal');
  await hold(2500);
  await page.click('text=Uji');
  await hold(2000);

  // 4. Forex: cockpit live (tab Ringkas), lalu Eksekusi
  await page.goto(BASE + '/forex');
  await hold(3000);
  await page.mouse.wheel(0, 300);
  await hold(1500);
  await page.click('text=Eksekusi');
  await hold(2500);

  // 5. IDX: klik tab Sinyal (empty state jujur), lalu Ringkas
  await page.goto(BASE + '/idx');
  await hold(2500);
  await page.click('text=Sinyal');
  await hold(2000);
  await page.click('text=Ringkas');
  await hold(2000);

  // 6. Jurnal: tabel trade
  await page.goto(BASE + '/jurnal');
  await hold(3000);
  await page.mouse.wheel(0, 500);
  await hold(2000);

  // 7. Ledger: ringkasan PnL
  await page.goto(BASE + '/ledger');
  await hold(3000);

  // 8. Sistem: watchdog infrastruktur
  await page.goto(BASE + '/sistem');
  await hold(3000);
  await page.mouse.wheel(0, 400);
  await hold(2000);

  await browser.close();
  console.log('rekaman selesai -> ' + OUT);
})();
