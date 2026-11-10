/**
 * Penjaga Home (6 Okt): panel "Akurasi & PnL per Market" wajib menampilkan angka nyata
 * dari fakta pasar_akurasi/idx_akurasi — dan WAJIB jujur untuk market yang belum ada
 * (alasan tampil, bukan nol). Kelas bug yang dicegah: Home dan halaman detail berbeda.
 */
import { expect, test } from '@playwright/test';

/** Buka semua <details> agar isi lipatan ikut ter-render (innerText detail tertutup tidak memuatnya). */
async function bukaSemuaLipatan(page: import('@playwright/test').Page) {
  const n = await page.locator('details').count();
  for (let i = 0; i < n; i++) {
    await page.locator('details').nth(i).evaluate((el) => {
      (el as HTMLDetailsElement).open = true;
    });
  }
  await page.waitForTimeout(300);
}

test('home: akurasi per market + narasi tetap ada', async ({ page }) => {
  // Sesi sudah dibuat global-setup (login sekali per suite) — lihat playwright.config.ts.
  await page.goto('/');
  await expect(page.getByText('Akurasi & PnL per Market').first()).toBeVisible({ timeout: 25000 });
  // Tabel akurasi ada DI DALAM <details> yang terlipat (revisi owner 7 Okt: progressive
  // disclosure). innerText elemen <details> tertutup TIDAK memuat isinya, jadi tes harus
  // membukanya dulu — kalau tidak, label pakem tidak pernah terlihat dan tes gagal
  // walaupun datanya ada (temuan R1, 9 Okt).
  await bukaSemuaLipatan(page);
  const t = await page.locator('body').innerText();
  const i = t.indexOf('Akurasi & PnL per Market');
  console.log('--- HOME AKURASI (idx=' + i + ') ---');
  console.log(t.slice(Math.max(0, i), Math.max(0, i) + 700));
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

test('home: status pasar per market tampil (ringkasan + link ke detail)', async ({ page }) => {
	// Sesi dibuat global-setup (login sekali per suite) — lihat playwright.config.ts.
	await page.goto('/');
	await expect(page.getByText('Status Pasar').first()).toBeVisible({ timeout: 25000 });
	const kartu = page.locator('.market-kartu');
	await expect(kartu.first()).toBeVisible({ timeout: 25000 });

	// Ringkasan beranda: tiap market punya kartu status (ada/kosong/gagal) + link ke
	// halaman detail (tempat timestamp & kesegaran sinyal lengkap ditampilkan).
	const status = await kartu.evaluateAll((els) =>
		els.map((e) =>
			['ada', 'kosong', 'gagal'].find((c) => e.classList.contains(c)) ?? 'tanpa-status'
		)
	);
	expect(status.length).toBeGreaterThan(0);
	expect(status.every((s) => s !== 'tanpa-status')).toBe(true);

	// Setiap kartu pasar menautkan ke halaman detailnya — kesegaran sinyal bisa
	// dinilai di sana (bukan hilang, hanya dipindah dari beranda).
	const tautan = await kartu.evaluateAll((els) => els.map((e) => (e as HTMLAnchorElement).getAttribute('href')));
	expect(tautan.every((h) => h && h.startsWith('/'))).toBe(true);
});
