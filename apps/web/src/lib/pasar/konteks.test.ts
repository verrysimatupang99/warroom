import { describe, expect, it } from 'vitest';
import { buatHarga, buatHargaAdaptif, buatKonteks, temukanFakta, type Fact } from './konteks';

const f = (key: string, value: unknown, kind = 'snapshot'): Fact => ({ key, kind, value });

describe('temukanFakta', () => {
	it('mengembalikan fakta yang cocok', () => {
		const facts = [f('a', 1), f('b', 2)];
		expect(temukanFakta(facts, 'b')?.value).toBe(2);
	});

	it('mengembalikan null bila tidak ada (bukan melempar)', () => {
		expect(temukanFakta([], 'x')).toBeNull();
	});
});

describe('buatHarga', () => {
	it('kripto mikro tidak dibulatkan jadi 0,00', () => {
		// 1000PEPE ~ 0,0041 — kalau salah, akan tampil "0,00"
		const h = buatHarga(4);
		expect(h(0.0041)).toContain('0,0041');
	});

	it('angka besar dibatasi 2 desimal', () => {
		expect(buatHarga(4)(1234.5678)).toBe('1.234,57');
	});

	it('nilai tidak valid jadi "—", bukan NaN', () => {
		expect(buatHarga(4)(null)).toBe('—');
		expect(buatHarga(4)(undefined)).toBe('—');
		expect(buatHarga(4)('bukan-angka')).toBe('—');
	});
});

describe('buatHargaAdaptif', () => {
	const h = buatHargaAdaptif();

	it('angka >= 1 dibatasi 2 desimal', () => {
		expect(h(1.23456)).toBe('1,23');
	});

	it('angka antara 0,01 dan 1 dibatasi 4 desimal (bukan 8)', () => {
		expect(h(0.123456789)).toBe('0,1235');
	});

	it('angka di bawah 0,01 dibatasi 8 desimal', () => {
		expect(h(0.000123456789)).toContain('0,00012346');
	});

	it('nilai kosong jadi "—", bukan 0', () => {
		expect(h(null)).toBe('—');
		expect(h('')).toBe('—');
	});
});

describe('buatKonteks', () => {
	const facts: Fact[] = [
		f('bagian', { idx: { rows: [{ kode: 'BBCA' }] }, forex: { bias: 'long' } }),
		f('posisi', [{ pair: 'ETHUSDT' }, { pair: 'BTCUSDT' }]),
		f('radar', { ada: true }),
		f('poly_paper', { arms: [] }),
		f('pasar_akurasi', { pasar: { crypto: { wr: 0.5 }, polymarket: { wr: 0.8 } } }),
		{ kind: 'poly.alt', key: 'btc-5m', value: { tersedia: true, jalan: false } },
		{ kind: 'signal', key: 'ETHUSDT', value: { arah: 'LONG' } },
		{ kind: 'ai.brief', key: 'crypto', value: { status: 'ok' } },
	];

	it('mengangkat potongan `bagian` ke field siap-pakai', () => {
		const k = buatKonteks(facts, 'crypto', null);
		expect(k.idxArjum).toEqual([{ kode: 'BBCA' }]);
		expect(k.forexObj).toEqual({ bias: 'long' });
	});

	it('menghitung jumlah posisi dari panjang array', () => {
		const k = buatKonteks(facts, 'crypto', null);
		expect(k.posisiArray).toHaveLength(2);
		expect(k.posisiJumlah).toBe(2);
	});

	it('memilih varian fakta sesuai pasar', () => {
		const k = buatKonteks(facts, 'crypto', null);
		expect(k.akurasiCryptoT).toEqual({ wr: 0.5 });
		expect(k.akurasiPolyT).toEqual({ wr: 0.8 });
		expect(k.akurasiForexT).toBeNull();
	});

	it('mengambil fakta poly.alt khusus (kind berbeda dari snapshot)', () => {
		const k = buatKonteks(facts, 'polymarket', null);
		expect(k.polyAltObj).toEqual({ tersedia: true, jalan: false });
	});

	it('narasi hanya untuk pasar yang cocok', () => {
		expect(buatKonteks(facts, 'crypto', null).narasiObj).toEqual({ status: 'ok' });
		expect(buatKonteks(facts, 'idx', null).narasiObj).toBeNull();
	});

	it('kandidat & sinyal aktif terpisah sesuai jenisnya', () => {
		const k = buatKonteks(facts, 'crypto', null);
		expect(k.sinyalAktif).toHaveLength(1);
		expect(k.sinyalAktif[0].key).toBe('ETHUSDT');
	});

	it('fakta terpilih mengikuti daftar kunci anak bila ada', () => {
		const k = buatKonteks(facts, 'crypto', { kunci: ['radar'] });
		expect(k.faktaTerpilih.map((x) => x.key)).toEqual(['radar']);
	});

	it('fakta kosong tidak melempar — semua null/array kosong', () => {
		const k = buatKonteks([], 'crypto', null);
		expect(k.posisiJumlah).toBe(0);
		expect(k.bagianObj).toEqual({});
		expect(k.polyAltObj).toBeNull();
		expect(k.idxArjum).toEqual([]);
	});
});
