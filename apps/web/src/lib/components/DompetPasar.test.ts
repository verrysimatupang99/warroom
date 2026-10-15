import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import DompetPasar from './DompetPasar.svelte';

// Temuan QA 15 Okt 2026 (High): baris saldo USD memakai formatter PnL sehingga
// tampil "+378.16 USD" tepat di atas baris "PnL −Rp 3.222.910" — terbaca sebagai
// PnL positif. Tanda `+` hanya untuk perubahan (PnL), bukan level (saldo).
describe('DompetPasar — saldo USD tidak boleh ber-tanda +', () => {
	const dompet = {
		kurs_usd_idr: 17921,
		pasar: {
			polymarket: {
				market: 'polymarket',
				tersedia: true,
				saldo_awal_idr: 10_000_000,
				mata_uang: 'USD',
				kurs_usd_idr: 17921,
				saldo_akhir_usd: 378.16,
				saldo_akhir_idr: 6_777_005,
				pnl_usd: -32.23,
				pnl_idr: -3_222_910,
				pnl_pct: -32.23,
				trade: 289
			}
		}
	};

	it('saldo akhir USD tanpa tanda + (level, bukan delta)', () => {
		render(DompetPasar, { props: { market: 'polymarket', dompet } });
		const teks = document.body.textContent ?? '';
		expect(teks).toContain('378,16 USD');
		expect(teks).not.toContain('+378,16 USD');
		expect(teks).not.toContain('+378.16 USD');
	});

	it('PnL rupiah tetap minus (konsisten dengan % negatif)', () => {
		render(DompetPasar, { props: { market: 'polymarket', dompet } });
		const teks = document.body.textContent ?? '';
		expect(teks).toContain('−Rp 3.222.910');
		expect(teks).toContain('-32.23%');
	});
});
