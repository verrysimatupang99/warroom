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
	expect(teks).toContain('fakta basi');

	// Tanpa laporan API, nada harus "tak" (abu-abu) — bukan hijau yang mengklaim sehat.
	const nada = await strip.locator('[data-nada]').evaluateAll((els) =>
		els.map((e) => (e as HTMLElement).dataset.nada)
	);
	expect(nada.every((n) => ['ok', 'gagal', 'tak'].includes(n ?? ''))).toBe(true);
});

test('home: kartu pasar membawa horizon kesegaran, bukan hanya angka umur', async ({ page }) => {
	await page.goto('/');
	const kartu = page.locator('.sinyal-kartu').first();
	await expect(kartu).toBeVisible({ timeout: 25000 });

	// Badge kesegaran memakai data-testid="freshness" (komponen FreshnessBadge).
	const badge = kartu.getByTestId('freshness').first();
	await expect(badge).toBeVisible();

	// Nada hanya boleh salah satu dari nilai yang didefinisikan; "n/a" sah bila TTL
	// sinyal tidak dilaporkan API.
	const nada = await badge.getAttribute('data-nada');
	expect(['segar', 'basi', 'cache', 'n/a']).toContain(nada);
});
