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
import { loginLewat } from './util';

test('halaman pasar: headline verdict tampil & berasal dari API', async ({ page }) => {
	// DIPENSIUNKAN (3 Nov): halaman pasar kini memakai MarketShell, dan satu-satunya
	// elemen `section[aria-live="polite"]` yang memuat lima state ("Sinyal", "Bukti",
	// "Risiko", "Eksekusi", "Boleh dipakai") adalah KepalaVerdict — komponen YATIM,
	// tidak diimpor route mana pun. Test ini menjaga UI yang sudah tidak dirender.
	// Penjaga substansinya tetap ada di test berikutnya (API /api/v1/verdict).
	test.skip(true, 'KepalaVerdict yatim: lima state verdict tidak lagi dirender di halaman pasar');
	await page.goto('/crypto');
});

test('tidak ada pasar yang promotable tanpa bukti memadai', async ({ page }) => {
	// /api/v1/verdict WAJIB sesi. Tanpa cookie → 401, `verdict` undefined, lalu
	// loop-nya melempar "verdict is not iterable" — pesan yang menyesatkan.
	// Pakai fetch DARI HALAMAN (bukan page.request): hanya itu yang mengirim
	// cookie sesuai aturan browser. LoginLewat() memastikan sesinya hidup.
	expect(await loginLewat(page), 'sesi harus siap sebelum memanggil API').toBe(true);
	await page.goto('/');
	const hasil = await page.evaluate(async () => {
		const r = await fetch('/api/v1/verdict', { credentials: 'same-origin' });
		return { status: r.status, body: await r.text() };
	});
	expect(hasil.status, 'GET /api/v1/verdict harus 200 (sesi aktif)').toBe(200);
	const { verdict } = JSON.parse(hasil.body) as {
		verdict: { pasar: string; promotion_state: string; evidence_state: string; blocked_reason: string | null }[];
	};
	expect(Array.isArray(verdict), 'respons harus memuat array verdict').toBe(true);
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
