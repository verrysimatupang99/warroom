/**
 * Akun QA + login lewat form UI.
 *
 * Dipisah dari qa-lengkap.spec.ts supaya spec lain bisa memakainya tanpa menyalin.
 * Akun diambil dari env lebih dulu (akun uji di DB tes), baru accounts.env —
 * jangan pernah bergantung pada kredensial produksi saat menguji stack uji.
 */
import type { Page } from '@playwright/test';
import fs from 'node:fs';

function bacaEnv(p: string): Record<string, string> {
	const out: Record<string, string> = {};
	try {
		for (const baris of fs.readFileSync(p, 'utf8').split('\n')) {
			const m = baris.match(/^([A-Za-z0-9_]+)=(.*)$/);
			if (m) out[m[1]] = m[2].trim();
		}
	} catch {
		/* berkas tidak ada → pemanggil akan skip */
	}
	return out;
}

const AKUN = bacaEnv(`${process.env.HOME}/.config/warroom/accounts.env`);

const dari = (kunci: string): string => process.env[kunci]?.trim() || AKUN[kunci] || '';

export const QA = {
	owner_user: dari('QA_OWNER_USER'),
	owner_pass: dari('QA_OWNER_PASS'),
	operator_user: dari('QA_OPERATOR_USER'),
	operator_pass: dari('QA_OPERATOR_PASS')
};

export const QA_LENGKAP = Boolean(
	QA.owner_user && QA.owner_pass && QA.operator_user && QA.operator_pass
);

/** Login lewat form /masuk, dengan retry untuk limiter 429 / hydration. */
export async function loginUi(page: Page, user: string, pass: string): Promise<void> {
	await page.goto('/masuk');
	await page.waitForSelector('form input[name="username"]', { timeout: 20_000 });
	for (let i = 0; i < 5; i++) {
		await page.locator('input[name="username"]').fill(user);
		await page.locator('input[name="password"]').fill(pass);
		await page.getByRole('button', { name: 'masuk' }).click();
		try {
			await page.waitForURL((u) => !u.pathname.startsWith('/masuk'), { timeout: 12_000 });
			return;
		} catch {
			await page.waitForTimeout(4000 * (i + 1));
		}
	}
	throw new Error('loginUi gagal setelah 5 percobaan (cek kredensial / limiter 429)');
}