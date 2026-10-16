/**
 * Konteks area pasar — SATU sumber untuk semua halaman market.
 *
 * Latar (audit 16 Okt 2026): AreaView.svelte menyimpan ~75 `{@const}` di dalam
 * snippet markup, bercampur dengan percabangan per-pasar. Akibatnya tiap pasar
 * tampak "beda sendiri" dan file itu membengkak jadi 3.700+ baris.
 *
 * Modul ini mengangkat SEMUA penghitungan itu ke fungsi murni, sehingga:
 *  - tiap komponen pasar menerima konteks yang sama (bentuk seragam);
 *  - markup hanya menggambar, tidak menghitung;
 *  - normalisasi antar-pasar jadi mungkin tanpa menyentuh logika.
 *
 * Aturan: fungsi di sini TIDAK menyentuh DOM dan TIDAK memanggil API. Ia hanya
 * menata ulang fakta yang sudah diterima. Dengan begitu ia bisa diuji sendiri.
 */

export type Fact = {
	kind?: string;
	key: string;
	value: unknown;
	source?: string | null;
	age_s?: number | null;
	status?: string | null;
};

/** Ambil satu fakta berdasarkan key; null bila tidak ada. */
export function temukanFakta(facts: Fact[], key: string): Fact | null {
	return facts.find((f) => f.key === key) ?? null;
}

export interface KonteksPasar {
	// fakta mentah
	faktaBagian: Fact | null;
	faktaPosisi: Fact | null;
	faktaRadar: Fact | null;
	faktaGmgn: Fact | null;
	faktaLpPaper: Fact | null;
	faktaPolyPaper: Fact | null;
	faktaPolyAlt: Fact | null;
	faktaTerpilih: Fact[];

	// objek nilai (siap dipakai markup)
	bagianObj: Record<string, any>;
	polyAltObj: Record<string, any> | null;
	polyPaperObj: Record<string, any> | null;
	radarObj: any;
	gmgnObj: any;
	gmgnPaperObj: any;
	lpPaperObj: any;
	lpMarkObj: any;
	lpVerifObj: any;
	idxAkurasiObj: any;
	idxSinyalObj: any;
	cryptoSinyalObj: any;
	forexSinyalObj: any;
	verdictObj: any;
	narasiObj: any;

	// potongan `bagian` (data per-pasar dari snapshot domain)
	idxArjum: any[];
	idxTv: any[];
	idxBandar: any;
	idx616: any[];
	bsjpObj: any;
	overextObj: any;
	forexObj: any;
	macroObj: any;
	memecoinObj: any;

	// posisi
	posisiArray: any[];
	posisiJumlah: number;

	// turunan pasar
	akurasiCryptoT: any;
	akurasiForexT: any;
	akurasiGmgnT: any;
	akurasiPolyT: any;
	idxSetupKarantina: any;
	forexSetupKarantina: any;
	kandidatArray: any[];
	sinyalAktif: Fact[];
	feedKeputusan: any;

	// helper format (fungsi)
	harga: (v: unknown) => string;
	hargaAdaptif: (v: unknown) => string;
}

/** Format harga adaptif: kripto mikro (0,0041) tidak boleh jadi "0,00". */
export function buatHarga(minDesimalBawah1 = 4): (v: unknown) => string {
	return (v: unknown): string => {
		// Number(null) === 0 dan Number('') === 0 — keduanya BUKAN harga nol sungguhan.
		// Tanpa penjagaan ini, nilai kosong tampil sebagai "0" dan menyesatkan pembaca.
		if (v == null || v === '') return '—';
		const n = typeof v === 'number' ? v : Number(v);
		if (!Number.isFinite(n)) return '—';
		const a = Math.abs(n);
		const dp = a >= 1000 ? 2 : a >= 1 ? minDesimalBawah1 : 8;
		return n.toLocaleString('id-ID', { maximumFractionDigits: dp });
	};
}

/**
 * Bangun konteks pasar dari fakta satu area.
 *
 * `kunci` = nama pasar (crypto/idx/forex/gmgn/polymarket) — dipakai untuk memilih
 * varian fakta (mis. `idx_risiko` vs `risiko`).
 */
export function buatKonteks(facts: Fact[], kunci: string, anak: { kunci?: string[] } | null): KonteksPasar {
	const angka = (v: any) => (typeof v === 'number' ? v : Number(v));

	const faktaBagian = temukanFakta(facts, 'bagian');
	const faktaPosisi =
		temukanFakta(facts, kunci === 'crypto' ? 'posisi' : `${kunci}_posisi`) ??
		temukanFakta(facts, 'posisi');
	const posisiArray = Array.isArray(faktaPosisi?.value) ? (faktaPosisi!.value as any[]) : [];

	const bagianObj = (faktaBagian?.value as Record<string, any>) ?? {};

	const faktaPasarAkurasi = temukanFakta(facts, 'pasar_akurasi');
	const pasarAkurasiObj = (faktaPasarAkurasi?.value as any) ?? null;

	const faktaPolyAlt = facts.find((f) => f.kind === 'poly.alt' && f.key === 'btc-5m') ?? null;

	return {
		faktaBagian,
		faktaPosisi,
		faktaRadar: temukanFakta(facts, 'radar'),
		faktaGmgn: temukanFakta(facts, 'gmgn'),
		faktaLpPaper: temukanFakta(facts, 'lp_paper'),
		faktaPolyPaper: temukanFakta(facts, 'poly_paper'),
		faktaPolyAlt,
		faktaTerpilih: anak && anak.kunci?.length
			? facts.filter((f) => anak.kunci!.includes(f.key))
			: facts,

		bagianObj,
		polyAltObj: (faktaPolyAlt?.value as Record<string, any>) ?? null,
		polyPaperObj: (temukanFakta(facts, 'poly_paper')?.value as any) ?? null,
		radarObj: (temukanFakta(facts, 'radar')?.value as any) ?? null,
		gmgnObj: (temukanFakta(facts, 'gmgn')?.value as any) ?? null,
		gmgnPaperObj: (temukanFakta(facts, 'gmgn')?.value as any) ?? null,
		lpPaperObj: (temukanFakta(facts, 'lp_paper')?.value as any) ?? null,
		lpMarkObj: (temukanFakta(facts, 'lp_mark')?.value as any) ?? null,
		lpVerifObj: (temukanFakta(facts, 'lp_verifikasi')?.value as any) ?? null,
		idxAkurasiObj: (temukanFakta(facts, 'idx_akurasi')?.value as any) ?? null,
		idxSinyalObj: (temukanFakta(facts, 'idx_sinyal')?.value as any) ?? null,
		cryptoSinyalObj: (temukanFakta(facts, 'crypto_sinyal')?.value as any) ?? null,
		forexSinyalObj: (temukanFakta(facts, 'forex_sinyal')?.value as any) ?? null,
		verdictObj: (temukanFakta(facts, 'verdict')?.value as any) ?? null,
		narasiObj: (facts.find((f) => f.kind === 'ai.brief' && f.key === kunci)?.value as any) ?? null,

		idxArjum: (bagianObj?.idx?.rows as any[]) ?? [],
		idxTv: (bagianObj?.idx_tv?.rows as any[]) ?? [],
		idxBandar: (bagianObj?.bandarmologi as any) ?? null,
		idx616: (bagianObj?.idx616?.terbuka as any[]) ?? [],
		bsjpObj: (bagianObj?.bsjp as any) ?? null,
		overextObj: (bagianObj?.overextended as any) ?? null,
		forexObj: (bagianObj?.forex as any) ?? null,
		macroObj: (bagianObj?.macro as any) ?? null,
		memecoinObj: (bagianObj?.memecoin as any) ?? null,

		posisiArray,
		posisiJumlah: posisiArray.length,

		akurasiCryptoT: (pasarAkurasiObj?.pasar?.crypto as any) ?? null,
		akurasiForexT: (pasarAkurasiObj?.pasar?.forex as any) ?? null,
		akurasiGmgnT: (pasarAkurasiObj?.pasar?.gmgn as any) ?? null,
		akurasiPolyT: (pasarAkurasiObj?.pasar?.polymarket as any) ?? null,
		idxSetupKarantina: (temukanFakta(facts, 'idx_akurasi')?.value as any)?.per_setup ?? null,
		forexSetupKarantina: (temukanFakta(facts, 'forex_sinyal')?.value as any)?.per_setup ?? null,
		kandidatArray: (temukanFakta(facts, 'kandidat')?.value as any[]) ?? [],
		sinyalAktif: facts.filter((f) => f.kind === 'signal'),
		feedKeputusan: (temukanFakta(facts, 'keputusan')?.value as any) ?? null,

		harga: buatHarga(4),
		hargaAdaptif: buatHarga(2),
	};
}
