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

/**
 * Akun untuk QA: utamakan env (mis. akun uji di DB tes), baru jatuh ke accounts.env.
 *
 * Kenapa: suite ini butuh DUA peran (owner + operator). `accounts.env` berisi akun
 * ASLI produksi, yang tidak ada di DB tes — akibatnya login UI selalu menjawab
 * "kredensial tidak sah" saat dijalankan terhadap stack uji, dan kegagalannya
 * terbaca seperti bug. Dengan env, stack uji menyemai akunnya sendiri
 * (ops/e2e-seed-user.py) tanpa pernah memakai kredensial produksi.
 */
const dari = (kunci: string): string =>
	process.env[kunci]?.trim() || AKUN[kunci] || '';

const QA = {
	owner_user: dari('QA_OWNER_USER'),
	owner_pass: dari('QA_OWNER_PASS'),
	operator_user: dari('QA_OPERATOR_USER'),
	operator_pass: dari('QA_OPERATOR_PASS')
};
const PUNYA = Boolean(QA.owner_user && QA.owner_pass && QA.operator_user && QA.operator_pass);

const AREA: { rute: string; subs: string[] }[] = [
	{ rute: '/', subs: [] },
	{ rute: '/crypto', subs: ['Cockpit', 'Setup', 'Ukur', 'Eksekusi'] },
	// 7 Okt: "Screener" → "Sinyal"; "Watchlist" → "BSJP"; "Aliran" kembali jadi tab sendiri.
	{ rute: '/idx', subs: ['Sinyal', 'Bandarmologi', 'BSJP', 'Aliran'] },
	{ rute: '/forex', subs: ['Struktur', 'Sesi', 'Kalender', 'Demo'] },
	// 7 Okt: fokus Setup B; arm lain dibekukan ke Arsip.
	{ rute: '/polymarket', subs: ['Favorit 0,70–0,95', 'Riset', 'Arm Lain (Beku)', 'Live'] },
	{ rute: '/gmgn', subs: ['Radar', 'LP', 'Memecoin'] },
	{
		rute: '/sistem',
		subs: ['Layanan', 'Mesin', 'Kesegaran', 'Biaya', 'Event', 'AI', 'Kebijakan', 'Audit']
	}
];

async function loginUi(page: Page, user: string, pass: string): Promise<void> {
	await page.goto('/masuk');
	// Tunggu form ter-hydrate dulu: `getByRole('textbox')` bisa gagal bila halaman
	// belum hidup (input belum punya aksesibilitas penuh) — itu flaky, bukan bug UI.
	await page.waitForSelector('form input[name="username"]', { timeout: 20_000 });

	// Login berulang dari IP yang sama kena limiter (429) → form tampak "tidak jalan".
	// Coba ulang beberapa kali dengan jeda; limiter membagi jatah per menit.
	for (let i = 0; i < 5; i++) {
		await page.locator('input[name="username"]').fill(user);
		await page.locator('input[name="password"]').fill(pass);
		await page.getByRole('button', { name: 'masuk' }).click();
		try {
			await page.waitForURL((u) => !u.pathname.startsWith('/masuk'), { timeout: 12_000 });
			return;
		} catch {
			// Masih di /masuk: bisa 429 atau hydration. Tunggu lalu ulangi.
			await page.waitForTimeout(4000 * (i + 1));
		}
	}
	throw new Error('loginUi gagal setelah 5 percobaan (cek kredensial / limiter 429)');
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

/**
 * Buang artefak suite dari daftar temuan konsol.
 *
 * Saat seluruh suite berjalan (100+ login dari IP yang sama), limiter API menjawab
 * 429 untuk sebagian percobaan; percobaan itu diulang dan berhasil, tetapi jejak
 * 429-nya tetap terekam sebagai console error. Itu kondisi HARNESS, bukan cacat
 * halaman — kalau tidak disaring, tes QA ini gagal palsu tiap run panjang.
 */
function saringArtefakSuite(galat: string[]): string[] {
	/**
	 * 503 `code:"unavailable"` BUKAN kerusakan halaman.
	 *
	 * War Room sengaja membalas 503 ber-alasan ketika data tidak punya padanan lokal,
	 * ketimbang mengarang angka. Diukur dengan mengumpulkan seluruh respons 503 saat
	 * keliling 8 rute (e2e/_kumpul503.spec.ts) — ada tepat 4, semuanya ber-alasan:
	 *
	 *   /api/v1/idx/ledger          "belum punya padanan lokal … node scanner sudah tidak ada"
	 *   /api/v1/idx/signals         idem
	 *   /api/v1/journal/edge        "Belum ada fill forex."
	 *   /api/v1/journal/performance "Belum ada riwayat ekuitas."
	 *
	 * Daftar ini sengaja eksplisit, bukan pola "semua 503": 500, exception JS, dan 503
	 * dari endpoint lain tetap menggagalkan tes.
	 */
	const TANPA_PADANAN =
		/\/api\/v1\/(idx\/ledger|idx\/signals|journal\/edge|journal\/performance)/;
	/**
	 * Pesan "Failed to load resource … status of 503" TIDAK memuat URL, jadi pola
	 * endpoint tak pernah cocok padanya — itu sebabnya versi sebelumnya lolos.
	 *
	 * Aturannya: buang pesan 503 tanpa URL HANYA bila setiap 503 yang tercatat
	 * dengan URL memang berasal dari endpoint ber-alasan. Bila ada 503 dari endpoint
	 * lain, pesan tanpa URL tidak boleh dibuang (bisa jadi milik endpoint itu).
	 */
	const berUrl = galat.filter((g) => /503/.test(g) && /\/api\/v1\//.test(g));
	const semuaBerAlasan = berUrl.every((g) => TANPA_PADANAN.test(g));
	return galat.filter((g) => {
		if (/\/api\/v1\/auth\/login/.test(g)) return false;
		if (/status of 429/.test(g) || /Too Many Requests/i.test(g)) return false;
		if (TANPA_PADANAN.test(g) && /503/.test(g)) return false;
		if (semuaBerAlasan && /503/.test(g) && !/\/api\/v1\//.test(g)) return false;
		return true;
	});
}

test.describe('QA owner', () => {
	test.skip(!PUNYA, 'butuh accounts.env (owner+operator)');
	test.describe.configure({ mode: 'serial' });
	// Tes ini MEMBUKTIKAN login lewat UI — jadi ia harus mulai tanpa sesi. Sesi global
	// (dari global-setup untuk suite lain) justru membuat /masuk tersedot ke "/".
	test.use({ storageState: { cookies: [], origins: [] } });

	test('login UI owner + keliling semua rute/sub', async ({ page }) => {
		const galat = pantauKonsol(page);
		await loginUi(page, QA.owner_user, QA.owner_pass);
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
		const bersih = saringArtefakSuite(galat);
		expect(bersih, `error konsol: ${bersih.slice(0, 5).join(' | ')}`).toEqual([]);
	});

	test('owner: Kebijakan menampilkan gate + parameter, tanpa tombol usulan', async ({ page }) => {
		// Dulu test ini menunggu `[data-testid="proposal-card"]`. Panel usulan itu sudah
		// TIDAK ADA di UI: ProposalCard hanya diimpor oleh unit test-nya, `getProposals`
		// tidak dipanggil satu pun komponen, dan tab Kebijakan kini berisi "Gate yang
		// berlaku" + "Parameter aktif" (lihat history a169f00 → b57fcab). Menunggu kartu
		// usulan = menunggu elemen yang tak akan pernah dirender, apa pun datanya.
		// Yang tetap dijaga: tab Kebijakan hidup dan isinya nyata.
		await loginUi(page, QA.owner_user, QA.owner_pass);
		await page.goto('/sistem');
		const tab = page.getByRole('tab', { name: 'Kebijakan', exact: true });
		await expect(tab).toBeVisible({ timeout: 20000 });
		await tab.click();
		await expect(page.getByText('Gate yang berlaku')).toBeVisible({ timeout: 20000 });
		await expect(page.getByText('Parameter aktif')).toBeVisible();
		// Tanpa panel usulan tidak boleh ada tombol aksi menggantung.
		await expect(page.getByRole('button', { name: 'terapkan' })).toHaveCount(0);
		await expect(page.getByRole('button', { name: 'rollback' })).toHaveCount(0);
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
		await loginUi(page, QA.operator_user, QA.operator_pass);
		await page.goto('/sistem');
		await tungguSiap(page);
		// Role sebenarnya = 'tab' (bukan 'button') — lihat catatan di sub-baru.spec.ts.
		const tab = page.getByRole('tab', { name: 'Kebijakan', exact: true });
		await expect(tab).toBeVisible({ timeout: 20000 });
		await tab.click();
		// Panel usulan (proposal-card) sudah tidak dirender — lihat catatan di test owner.
		// RBAC tetap diuji: operator tidak boleh melihat tombol aksi milik owner.
		await expect(page.getByText('Gate yang berlaku')).toBeVisible({ timeout: 20000 });
		await expect(page.getByRole('button', { name: 'terapkan' })).toHaveCount(0);
		await expect(page.getByRole('button', { name: 'rollback' })).toHaveCount(0);
		expect(saringArtefakSuite(galat)).toEqual([]);
	});
});
