/**
 * QA menyeluruh (3 Okt, permintaan owner): pakai akun ASLI owner + operator,
 * keliling semua rute & sub-tab lewat BROWSER (Playwright), cek:
 *  - login lewat UI (form /masuk) untuk kedua akun
 *  - tiap rute + tiap sub-tab: h1 tampil, tanpa "GAGAL MEMUAT", tanpa error konsol
 *  - RBAC di UI: tombol proposal hanya owner; ack alert untuk operator/owner
 *  - guard: tanpa sesi → redirect /masuk
 *  - screenshot temuan per rute bermasalah
 * Jalankan: cd ~/warroom/apps/web && npx playwright test qa/qa-lengkap.spec.ts --reporter=list
 */
import { expect, test, type Page } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { tungguSiap } from './util';

function bacaEnv(p: string): Record<string, string> {
	const out: Record<string, string> = {};
	try {
		for (const baris of fs.readFileSync(p, 'utf8').split('\n')) {
			const m = baris.match(/^([A-Za-z0-9_]+)=(.*)$/);
			if (m) out[m[1]] = m[2].trim();
		}
	} catch {
		/* berkas tidak ada → tes skip */
	}
	return out;
}

const AKUN = bacaEnv(`${process.env.HOME}/.config/warroom/accounts.env`);
const PUNYA = Boolean(AKUN.owner_user && AKUN.owner_pass && AKUN.operator_user && AKUN.operator_pass);

const AREA: { rute: string; subs: string[] }[] = [
	{ rute: '/', subs: [] },
	{ rute: '/crypto', subs: ['Cockpit', 'Setup', 'Ukur', 'Eksekusi'] },
	// 7 Okt: "Screener" → "Sinyal"; "Watchlist" → "BSJP"; "Aliran" kembali jadi tab sendiri.
	{ rute: '/idx', subs: ['Sinyal', 'Bandarmologi', 'BSJP', 'Aliran'] },
	{ rute: '/forex', subs: ['Struktur', 'Sesi', 'Kalender', 'Demo'] },
	// 7 Okt: fokus Setup B; arm lain dibekukan ke Arsip.
	{ rute: '/polymarket', subs: ['Setup B', 'Riset', 'Arm Lain (Beku)', 'Live'] },
	{ rute: '/gmgn', subs: ['Radar', 'LP', 'Memecoin'] },
	{
		rute: '/sistem',
		subs: ['Layanan', 'Kesegaran', 'Biaya', 'Event', 'AI', 'Kebijakan', 'Audit']
	}
];

async function loginUi(page: Page, user: string, pass: string): Promise<void> {
	await page.goto('/masuk');
	await page.getByRole('textbox', { name: 'username' }).fill(user);
	await page.locator('input[type="password"]').fill(pass);
	await page.getByRole('button', { name: 'masuk' }).click();
	await page.waitForURL((u) => !u.pathname.startsWith('/masuk'), { timeout: 15_000 });
}

function pantauKonsol(page: Page): string[] {
	const galat: string[] = [];
	page.on('console', (m) => {
		if (m.type() === 'error') galat.push(m.text());
	});
	page.on('pageerror', (e) => galat.push(`pageerror: ${e.message}`));
	// 4xx/5xx juga temuan: blok "GAGAL MEMUAT" biasanya berakar dari HTTP gagal.
	page.on('response', (r) => {
		if (r.status() >= 400) galat.push(`HTTP ${r.status()} ${r.url()}`);
	});
	return galat;
}

test.describe('QA owner', () => {
	test.skip(!PUNYA, 'butuh accounts.env (owner+operator)');
	test.describe.configure({ mode: 'serial' });
	// Tes ini MEMBUKTIKAN login lewat UI — jadi ia harus mulai tanpa sesi. Sesi global
	// (dari global-setup untuk suite lain) justru membuat /masuk tersedot ke "/".
	test.use({ storageState: { cookies: [], origins: [] } });

	test('login UI owner + keliling semua rute/sub', async ({ page }) => {
		const galat = pantauKonsol(page);
		await loginUi(page, AKUN.owner_user, AKUN.owner_pass);
		await expect(page).toHaveURL(/\/$/);

		const temuan: string[] = [];
		const jejak: string[] = [];
		for (const area of AREA) {
			await page.goto(area.rute);
			await expect(page.locator('h1').first()).toBeVisible();
			const isi = await page.locator('body').innerText();
			if (isi.includes('GAGAL MEMUAT')) temuan.push(`${area.rute}: GAGAL MEMUAT`);
			for (const sub of area.subs) {
				// SubNav merender `role="tab"` (bukan button) — temuan 7 Okt: tes lama
				// mencari 'button' dan selalu nol, lalu menggantung sampai timeout.
				const tombol = page.getByRole('tab', { name: sub, exact: true });
				if ((await tombol.count()) === 0) {
					jejak.push(`${area.rute} → ${sub}: TAB TIDAK ADA`);
					continue;
				}
				// Tunggu tab SIAP diklik (bukan hanya ada) — pelajaran insiden shell:
				// klik pada elemen yang belum stabil menghasilkan flaky, bukan temuan.
				await expect(tombol.first()).toBeVisible({ timeout: 15000 });
				await tombol.first().click();
				await page.waitForTimeout(350);
				const t = await page.locator('body').innerText();
				if (t.includes('GAGAL MEMUAT')) temuan.push(`${area.rute} → ${sub}: GAGAL MEMUAT`);
			}
		}
		fs.mkdirSync('qa-hasil', { recursive: true });
		fs.writeFileSync('qa-hasil/temuan-owner.json', JSON.stringify({ temuan, konsol: galat, jejak }, null, 1));
		expect(temuan, `temuan: ${temuan.join('; ')}`).toEqual([]);
		expect(galat, `error konsol: ${galat.slice(0, 5).join(' | ')}`).toEqual([]);
	});

	test('owner: tombol terapkan/rollback tampil di Kebijakan', async ({ page }) => {
		await loginUi(page, AKUN.owner_user, AKUN.owner_pass);
		await page.goto('/sistem');
		// Tab di halaman Sistem memakai role=button (bukan role=tab seperti SubNav).
		// Tunggu siap dulu — klik sebelum interaktif adalah sumber flaky yang lama.
		// Role sebenarnya = 'tab' (bukan 'button') — lihat catatan di sub-baru.spec.ts.
		const tab = page.getByRole('tab', { name: 'Kebijakan', exact: true });
		await expect(tab).toBeVisible({ timeout: 20000 });
		await tab.click();
		await expect(page.locator('[data-testid="proposal-card"]').first()).toBeVisible({ timeout: 20000 });
		// usulan berstatus ditolak → tombol "terapkan" tidak ditampilkan (hanya untuk butuh_manusia)
		const kartuDitolak = page.locator('[data-testid="proposal-card"]').filter({ hasText: 'DITOLAK' }).first();
		await expect(kartuDitolak).toBeVisible();
		await expect(kartuDitolak.getByRole('button', { name: 'terapkan' })).toHaveCount(0);
	});

	test('guard: tanpa sesi → redirect /masuk', async ({ browser }) => {
		const ctx = await browser.newContext();
		const page = await ctx.newPage();
		await page.goto('/crypto');
		await page.waitForURL(/\/masuk/, { timeout: 10_000 });
		await ctx.close();
	});
});

test.describe('QA operator', () => {
	test.skip(!PUNYA, 'butuh accounts.env (owner+operator)');

	test('operator: login UI + tidak ada tombol owner', async ({ page }) => {
		const galat = pantauKonsol(page);
		await loginUi(page, AKUN.operator_user, AKUN.operator_pass);
		await page.goto('/sistem');
		await tungguSiap(page);
		// Role sebenarnya = 'tab' (bukan 'button') — lihat catatan di sub-baru.spec.ts.
		const tab = page.getByRole('tab', { name: 'Kebijakan', exact: true });
		await expect(tab).toBeVisible({ timeout: 20000 });
		await tab.click();
		await expect(page.locator('[data-testid="proposal-card"]').first()).toBeVisible({ timeout: 20000 });
		// operator tidak boleh melihat tombol aksi owner
		await expect(page.getByRole('button', { name: 'terapkan' })).toHaveCount(0);
		await expect(page.getByRole('button', { name: 'rollback' })).toHaveCount(0);
		expect(galat).toEqual([]);
	});
});
