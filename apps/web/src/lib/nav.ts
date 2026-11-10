/**
 * IA (information architecture) War Room — dirombak 28 Okt 2026.
 *
 * Aturan baru: **kerangka sama untuk tiap market**, empat tab universal
 * (Ringkas · Sinyal · Uji · Eksekusi) plus Alat hanya bila market benar-benar
 * punya alat. Market yang belum siap tidak menawarkan tab kosong; ia muncul
 * sebagai satu halaman Ringkas berstatus STANDBY.
 *
 * Sebelumnya nav menjanjikan 25 slot sub-tab untuk 5 market, sementara 20 di
 * antaranya tidak membawa isi berbeda (lihat audit 28 Okt: PasarForex hanya
 * mencetak judul, /crypto tidak memakai komponen pasar, 3 market masih
 * UnderConstruction). Sekarang yang ditawarkan nav sama dengan yang ada.
 */

export interface Anak {
	slug: string;
	label: string;
	/** kunci fakta yang relevan untuk sub ini (dipakai untuk memilih blok) */
	kunci: string[];
	catatan: string;
}

export interface Area {
	kunci: string;
	label: string;
	rute: string;
	/** Nama ikon SVG (lihat Ikon.svelte) — bukan glyph unicode: glyph tampil beda
	 *  di tiap platform dan tidak bisa diwarnai konsisten (audit QA 7 Okt). */
	ikon: string;
	kategori: 'pasar' | 'riset' | 'sistem';
	/** Label kecil di rail: apa yang bisa diharapkan sebelum diklik. */
	status?: 'AKTIF' | 'PAPER' | 'STANDBY' | 'SEBAGIAN';
	anak: Anak[];
}

/** Empat tab universal. Urutannya sama di semua market. */
const TAB_DASAR = (kunciSinyal: string[], kunciEksekusi: string[]): Anak[] => [
	{
		slug: 'ringkas',
		label: 'Ringkas',
		kunci: ['bagian', 'posisi', 'risiko'],
		catatan: 'Status, angka kunci, dan posisi terbuka'
	},
	{
		slug: 'sinyal',
		label: 'Sinyal',
		kunci: kunciSinyal,
		catatan: 'Kandidat, level, dan alasan sinyal ditolak'
	},
	{
		slug: 'uji',
		label: 'Uji',
		kunci: ['backtest', 'pengukuran', 'pasar_akurasi'],
		catatan: 'Hasil backtest dan walk-forward, beserta jumlah sampel'
	},
	{
		slug: 'eksekusi',
		label: 'Eksekusi',
		kunci: kunciEksekusi,
		catatan: 'Trade tercatat, fill, dan rekonsiliasi'
	}
];

export const AREAS: Area[] = [
	{
		kunci: 'home',
		label: 'Beranda',
		rute: '/',
		ikon: 'home',
		kategori: 'pasar',
		anak: []
	},
	{
		kunci: 'crypto',
		label: 'Crypto',
		rute: '/crypto',
		ikon: 'crypto',
		kategori: 'pasar',
		status: 'PAPER',
		anak: TAB_DASAR(['crypto_sinyal', 'kandidat'], ['ledger', 'posisi'])
	},
	{
		kunci: 'forex',
		label: 'Forex',
		rute: '/forex',
		ikon: 'forex',
		kategori: 'pasar',
		status: 'AKTIF',
		anak: [
			...TAB_DASAR(['forex_sinyal', 'bagian'], ['ledger', 'equity']),
			{
				slug: 'alat',
				label: 'Alat',
				kunci: ['risiko'],
				catatan: 'Lot sizer, risiko per trade, dan batas harian'
			},
			{
				slug: 'paper',
				label: 'Paper',
				kunci: ['ledger', 'equity'],
				catatan: 'Catatan eksekusi kertas forex (terpisah dari MT5 live)'
			}
		]
	},
	{
		kunci: 'polymarket',
		label: 'Polymarket',
		rute: '/polymarket',
		ikon: 'polymarket',
		kategori: 'pasar',
		status: 'STANDBY',
		anak: []
	},
	{
		kunci: 'idx',
		label: 'IDX',
		rute: '/idx',
		ikon: 'idx',
		kategori: 'pasar',
		// 29 Okt: IHSG kini punya sumber lokal, jadi bukan lagi standby penuh.
		// 29 Okt: idx-edge terpasang (harga emiten, penggerak, broker). Bukan standby lagi.
		status: 'AKTIF',
		anak: []
	},
	{
		kunci: 'gmgn',
		label: 'GMGN',
		rute: '/gmgn',
		ikon: 'gmgn',
		kategori: 'pasar',
		status: 'STANDBY',
		anak: []
	},
	{
		kunci: 'jurnal',
		label: 'Jurnal',
		rute: '/jurnal',
		ikon: 'forex',
		kategori: 'pasar',
		anak: []
	},
	{
		kunci: 'ledger',
		label: 'Ledger',
		rute: '/ledger',
		ikon: 'forex',
		kategori: 'riset',
		anak: []
	},
	{
		kunci: 'riset',
		label: 'Riset',
		rute: '/riset',
		ikon: 'riset',
		kategori: 'riset',
		anak: [
			{ slug: 'kinerja', label: 'Kinerja', kunci: ['equity', 'ledger'], catatan: 'Statistik, trade terakhir, PnL per pair' },
			{ slug: 'bukti', label: 'Bukti', kunci: [], catatan: 'Laporan backtest: periode, sampel, dan tautan unduh' },
			{ slug: 'leaderboard', label: 'Leaderboard', kunci: ['equity', 'ledger'], catatan: 'Peringkat strategi menurut PF setelah biaya' },
			{ slug: 'kalender', label: 'Kalender', kunci: ['bagian'], catatan: 'Agenda makro: CPI, NFP, FOMC' }
		]
	},
	{
		kunci: 'sistem',
		label: 'Sistem',
		rute: '/sistem',
		ikon: 'sistem',
		kategori: 'sistem',
		anak: [
			{ slug: 'layanan', label: 'Layanan', kunci: [], catatan: 'Status unit, uptime, memori, dan CPU' },
			{ slug: 'data', label: 'Data & Kesegaran', kunci: [], catatan: 'Sumber data, endpoint, umur data, dan mode lokal/upstream' },
			{ slug: 'event', label: 'Event & Audit', kunci: [], catatan: 'Umpan kejadian dan riwayat perubahan' },
			{ slug: 'kebijakan', label: 'Kebijakan', kunci: [], catatan: 'Gate, batas risiko, dan biaya berjalan' },
			{ slug: 'vault', label: 'Vault Kredensial', kunci: [], catatan: 'Simpan endpoint + API key platform (salin-tempel manual)' },
			{ slug: 'pengaturan', label: 'Pengaturan', kunci: [], catatan: 'Sakelar fitur: Laya AI hidup/mati' },
		]
	},
	{
		kunci: 'info',
		label: 'Info',
		rute: '/info',
		ikon: 'info',
		kategori: 'riset',
		anak: [
			{ slug: 'catatan', label: 'Catatan', kunci: [], catatan: 'Dokumentasi proyek dari repo' },
			{ slug: 'berita', label: 'Berita', kunci: ['bagian'], catatan: 'RSS publik: Cointelegraph, Decrypt' },
			{ slug: 'cara-kerja', label: 'Cara kerja', kunci: [], catatan: 'Aliran domain → worker → API → web' },
			{ slug: 'bantuan', label: 'Bantuan', kunci: [], catatan: 'Tanya-jawab dari perilaku nyata' }
		]
	}
];

/**
 * Rute lama → tujuan baru. Area yang digabung tidak dihapus diam-diam: rutenya tetap hidup
 * sebagai pengalihan supaya penanda buku dan tautan lama tidak mati.
 */
export const PENGALIHAN: Record<string, string> = {
	'/bandar': '/idx',
	'/lp': '/gmgn',
	'/overextended': '/crypto?sub=ringkas',
	'/bukti': '/riset?sub=bukti',
	// 28 Okt: Server Tencent jadi tab "Data & Kesegaran" di Sistem.
	'/tencent': '/sistem?sub=data',
	// Info pindah ke satu rute dengan tab.
	'/catatan': '/info?sub=catatan',
	'/berita': '/info?sub=berita',
	'/cara-kerja': '/info?sub=cara-kerja',
	'/bantuan': '/info?sub=bantuan'
};

/** Slug lama yang masih dipakai tautan/penanda buku, dipetakan ke tab baru. */
export const SLUG_LAMA: Record<string, string> = {
	cockpit: 'ringkas',
	setup: 'sinyal',
	ukur: 'uji',
	kesegaran: 'data',
	mesin: 'layanan',
	audit: 'event',
	biaya: 'kebijakan',
	alat: 'alat'
};

/** Bottom tab mobile: 5 slot utama. */
export const TAB_MOBILE = ['/', '/crypto', '/forex', '/jurnal', '/sistem'];

export function areaDariJalur(jalur: string): Area | null {
	const bersih = jalur.length > 1 ? jalur.replace(/\/$/, '') : jalur;
	if (bersih === '/') return AREAS[0];
	return AREAS.find((a) => a.rute === bersih) ?? null;
}

export function labelArea(rute: string): string {
	return AREAS.find((a) => a.rute === rute)?.label ?? rute;
}
