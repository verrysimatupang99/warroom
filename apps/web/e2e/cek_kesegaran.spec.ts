/**
 * Penjaga kesegaran data di Home (5 Nov 2026).
 *
 * Kelas bug yang dicegah: "pasar sepi" dan "worker mati" tampil identik. Strip
 * kesehatan dan badge segar/basi harus hadir dan berasal dari API — bila API
 * tidak melaporkan, UI wajib bilang tidak tahu (n/a), bukan hijau.
 */
import { expect, test } from '@playwright/test';

test('home: strip kesehatan sistem tampil', async ({ page }) => {
	await page.goto('/');
	const strip = page.getByTestId('health-strip');
	await expect(strip).toBeVisible({ timeout: 25000 });

	// Tiga penanda wajib ada — nilainya boleh ok/basi/gagal/n-a, tetapi tidak boleh hilang.
	const teks = (await strip.innerText()).toLowerCase();
	expect(teks).toContain('db');
	expect(teks).toContain('worker');
	expect(teks).toContain('data basi');

	// Tanpa laporan API, nada harus "tak" (abu-abu) — bukan hijau yang mengklaim sehat.
	const nada = await strip.locator('[data-nada]').evaluateAll((els) =>
		els.map((e) => (e as HTMLElement).dataset.nada)
	);
	expect(nada.every((n) => ['ok', 'gagal', 'tak'].includes(n ?? ''))).toBe(true);
});

test('home: tiap kartu pasar membawa status data (ada/kosong/gagal)', async ({ page }) => {
	await page.goto('/');
	const kartu = page.locator('.market-kartu');
	await expect(kartu.first()).toBeVisible({ timeout: 25000 });

	// Setiap kartu pasar WAJIB membawa status data — pembaca tahu mana yang mati
	// ('gagal') vs sepi ('kosong') vs ada sinyal ('ada'). Ini pengganti badge
	// freshness per-sinyal (kini di halaman masing-masing market).
	const status = await kartu.evaluateAll((els) =>
		els.map((e) =>
			['ada', 'kosong', 'gagal'].find((c) => e.classList.contains(c)) ?? 'tanpa-status'
		)
	);
	expect(status.length).toBeGreaterThan(0);
	expect(status.every((s) => s !== 'tanpa-status')).toBe(true);
});
