/**
 * Penjaga ikon & target interaksi (audit QA putaran 4, prioritas 4):
 *  - tidak ada glyph unicode/emoji sebagai ikon di navigasi (harus SVG),
 *  - target sentuh kontrol utama ≥ 44 px (nav atas, TopBar, bottom nav).
 *
 * Diukur dari DOM yang BENAR-BENAR dirender — bukan dari kode. Pelajaran dari insiden
 * shell: "ada di kode" tidak sama dengan "terlihat & bisa ditekan".
 */
import { expect, test } from '@playwright/test';

test('navigasi memakai SVG, bukan glyph unicode', async ({ page }) => {
	await page.goto('/crypto?sub=cockpit');
	await expect(page.locator('nav[aria-label="Navigasi area"]')).toBeVisible({ timeout: 25000 });

	const hasil = await page.evaluate(() => {
		const nav = document.querySelector('nav[aria-label="Navigasi area"]');
		if (!nav) return { svg: 0, glyph: [] as string[], teks: '' };
		const svg = nav.querySelectorAll('svg').length;
		// glyph unicode yang dulu dipakai sebagai ikon
		const GLYPH = /[⌂₿◎▦⇄⚡⚙⌁▤◈⚖⌕❄✦☾🔔⚠]/u;
		const glyph: string[] = [];
		for (const el of Array.from(nav.querySelectorAll('*'))) {
			const t = (el.textContent ?? '').trim();
			if (t && GLYPH.test(t) && el.children.length === 0) glyph.push(t.slice(0, 20));
		}
		return { svg, glyph, teks: (nav.textContent ?? '').trim().slice(0, 80) };
	});
	console.log('--- NAV ---', JSON.stringify(hasil));
	expect(hasil.svg, 'nav harus memakai ikon SVG').toBeGreaterThan(0);
	expect(hasil.glyph, `glyph unicode masih tampil: ${hasil.glyph.join(' ')}`).toEqual([]);
});

test('target sentuh kontrol utama ≥ 44 px', async ({ page }) => {
	await page.goto('/');
	await page.waitForTimeout(2500);
	const kecil = await page.evaluate(() => {
		const keluar: string[] = [];
		const pilih = [
			...Array.from(document.querySelectorAll('nav[aria-label="Navigasi area"] a')),
			...Array.from(document.querySelectorAll('header a, header button'))
		];
		for (const el of pilih) {
			const e = el as HTMLElement;
			const r = e.getBoundingClientRect();
			if (r.height === 0) continue; // tersembunyi di layar ini
			if (r.height < 44) keluar.push(`${e.textContent?.trim().slice(0, 18) || e.getAttribute('aria-label')} = ${Math.round(r.height)}px`);
		}
		return keluar;
	});
	console.log('--- TARGET KECIL ---\n' + (kecil.join('\n') || '(semua ≥44px)'));
	expect(kecil, `target < 44px:\n${kecil.join('\n')}`).toEqual([]);
});
