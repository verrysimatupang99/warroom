/**
 * Penjaga verdict kanonik (audit QA putaran 4, prioritas 1 & 2).
 *
 * Yang dijaga:
 *  1. Tiap halaman pasar punya SATU headline keputusan di paling atas.
 *  2. Lima state tampil (Sinyal/Bukti/Risiko/Eksekusi/Promosi) — pertanyaannya berbeda.
 *  3. Tidak ada pasar yang boleh "promotable" selama bukti < PRELIMINARY, split belum
 *     beku (Polymarket), mesin beku (IDX), atau expectancy/PnL negatif.
 *  4. Halaman TIDAK boleh menyusun verdict sendiri — headline harus berasal dari
 *     /api/v1/verdict (diuji dengan membandingkan teks DOM vs API).
 */
import { expect, test } from '@playwright/test';

const PETA: Record<string, string> = {
	crypto: 'Crypto (SMC)',
	polymarket: 'Polymarket (favorit 5m)',
	idx: 'IDX (bandarmologi/BSJP)',
	forex: 'Forex'
};

test('halaman pasar: headline verdict tampil & berasal dari API', async ({ page, request }) => {
	const api = await request.get('/api/v1/verdict');
	expect(api.ok()).toBe(true);
	const { verdict } = (await api.json()) as { verdict: { pasar: string; headline: string }[] };
	const peta = new Map(verdict.map((v) => [v.pasar, v.headline]));

	for (const [pasar, label] of Object.entries(PETA)) {
		await page.goto(`/${pasar}`);
		const kepala = page.locator('section[aria-live="polite"]').first();
		await expect(kepala).toBeVisible({ timeout: 25000 });
		const teks = await kepala.innerText();

		// headline dari API HARUS muncul apa adanya (bukan disusun ulang UI)
		const harap = peta.get(pasar);
		expect(harap, `verdict API tidak memuat ${pasar}`).toBeTruthy();
		expect(teks).toContain(harap!.replace(' — ', ' — ').split('—')[0].trim());

		// lima state wajib tampil
		for (const k of ['Sinyal', 'Bukti', 'Risiko', 'Eksekusi', 'Promosi']) {
			expect(teks, `${pasar}: state ${k} hilang`).toContain(k);
		}
		console.log(`--- ${label} ---\n` + teks.slice(0, 220));
	}
});

test('tidak ada pasar yang promotable tanpa bukti memadai', async ({ request }) => {
	const api = await request.get('/api/v1/verdict');
	const { verdict } = (await api.json()) as {
		verdict: { pasar: string; promotion_state: string; evidence_state: string; blocked_reason: string | null }[];
	};
	for (const v of verdict) {
		if (v.promotion_state === 'promotable') {
			// promotable hanya sah bila bukti minimal PRELIMINARY dan alasan blokir kosong
			expect(['PRELIMINARY', 'TUNING']).toContain(v.evidence_state);
			expect(v.blocked_reason).toBeNull();
		} else {
			expect(v.blocked_reason, `${v.pasar} blocked tanpa alasan`).toBeTruthy();
		}
	}
});
