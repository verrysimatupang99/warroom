/**
 * IA (information architecture) War Room — dirombak 5 Okt 2026.
 *
 * Sebelumnya 11 area dengan tumpang tindih. Penggabungan dilakukan berdasarkan SUMBER DATA
 * halaman lama, bukan selera:
 * - `/bandar` memanggil `getArea('idx')` → datanya sama dengan `idx.bandarmologi`.
 * - `/lp` memanggil `getArea('crypto')` + `bagian.lp` → LP sudah punya sub di GMGN.
 * - `/overextended` memanggil `getArea('crypto')` + `bagian.overextended` → milik Crypto.
 * - `/bukti` dilayani sub Sistem (kesegaran/audit) + kartu sinyal di Home.
 *
 * Hasilnya 7 area; tiap sub punya sumber data yang jelas dan berbeda. Satu sumber untuk
 * rail, bottom tab, dan sub-nav supaya rute dan chip tidak pernah berbeda definisi.
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
	anak: Anak[];
}

export const AREAS: Area[] = [
	{
		kunci: 'home',
		label: 'Home',
		rute: '/',
		ikon: 'home',
		kategori: 'pasar',
		// Tanpa anak: `/` adalah halaman pratinjau arah baru yang dirender mandiri
		// (routes/+page.svelte), bukan AreaView ber-tab. Dua anak lama (Sinyal,
		// Kinerja) tidak punya tujuan — tab-nya tak pernah muncul — jadi dihapus
		// 6 Okt 2026 supaya nav tak menjanjikan tautan mati. Bila arah pratinjau
		// diputuskan menang, tab ditambahkan lagi bersama isinya.
		anak: []
	},
	{
		kunci: 'crypto',
		label: 'Crypto',
		rute: '/crypto',
		ikon: 'crypto',
		kategori: 'pasar',
		anak: [
			{ slug: 'cockpit', label: 'Cockpit', kunci: ['bagian', 'risiko', 'posisi', 'crypto_sinyal', 'pasar_akurasi'], catatan: 'Pair utama, risiko, posisi, sinyal & entry setup' },
			{ slug: 'setup', label: 'Setup', kunci: ['kandidat', 'crypto_sinyal', 'pasar_akurasi'], catatan: 'Kandidat SMC + verdict per aturan + entry setup' },
			{ slug: 'ukur', label: 'Ukur', kunci: ['pengukuran', 'backtest', 'pasar_akurasi'], catatan: 'Forward lolos vs ditolak + lab backtest + akurasi' },
			{ slug: 'eksekusi', label: 'Eksekusi', kunci: ['posisi', 'ledger'], catatan: 'Paper, fill, ledger, overextended' }
		]
	},
	{
		kunci: 'polymarket',
		label: 'Polymarket',
		rute: '/polymarket',
		ikon: 'polymarket',
		kategori: 'pasar',
		anak: [
			// Keputusan owner 7 Okt: fokus ke SETUP B KANDIDAT; arm A/C/D dibekukan (diarsipkan,
			// tidak dihapus — bukti tetap ada, hanya tidak lagi jadi pusat perhatian).
			{ slug: 'setup-b', label: 'Favorit 0,70–0,95', kunci: ['poly_paper', 'pasar_akurasi', 'dompet'], catatan: 'Arm B = beli favorit di band 0,70–0,95 (yang dipakai): dompet, akurasi, verdict' },
			{ slug: 'riset', label: 'Riset', kunci: ['bagian', 'poly_paper'], catatan: 'Dataset, parity/drift, katalog replay (bekas dataset+verdict)' },
			{ slug: 'arsip', label: 'Arm Lain (Beku)', kunci: ['poly_paper', 'pasar_akurasi'], catatan: 'A momentum · C fade · D favorit — dibekukan, disimpan sebagai bukti' },
			{ slug: 'live', label: 'Live', kunci: ['equity', 'ledger'], catatan: 'Arming 3-way, dana nyata (status: belum arming)' }
		]
	},
	{
		kunci: 'idx',
		label: 'IDX',
		rute: '/idx',
		ikon: 'idx',
		kategori: 'pasar',
		anak: [
			// Keputusan owner 7 Okt: "screener" diganti "Sinyal" yang isinya bandarmologi + BSJP.
			// Sumbernya tetap sama (Arjum + ledger 616), tapi yang ditonjolkan adalah SINYALNYA,
			// bukan daftar screener mentah.
			{ slug: 'sinyal', label: 'Sinyal', kunci: ['idx_sinyal', 'idx_akurasi', 'bandarmologi_skor', 'bagian', 'dompet'], catatan: 'Bandarmologi + BSJP + ARA: sinyal, skor, dan akurasi' },
			{ slug: 'bandarmologi', label: 'Bandarmologi', kunci: ['bagian', 'bandarmologi_skor'], catatan: 'Broker summary, ATS, skor 0–100 per emiten' },
			{ slug: 'bsjp', label: 'BSJP', kunci: ['bagian', 'idx_akurasi', 'idx_sinyal'], catatan: 'Beli Sore Jual Pagi + ARA Hunter (ledger mesin)' },
			{ slug: 'aliran', label: 'Aliran', kunci: ['bagian'], catatan: 'Modal asing vs lokal, akumulasi senyap, konflik distribusi' }
		]
	},
	{
		kunci: 'forex',
		label: 'Forex',
		rute: '/forex',
		ikon: 'forex',
		kategori: 'pasar',
		anak: [
			{ slug: 'struktur', label: 'Struktur', kunci: ['bagian', 'forex_sinyal', 'pasar_akurasi'], catatan: 'Bias, EMA, ATR + sinyal & entry setup' },
			{ slug: 'sesi', label: 'Sesi', kunci: ['bagian', 'pasar_akurasi'], catatan: 'Asia/London/NY (WIB) + akurasi' },
			{ slug: 'kalender', label: 'Kalender', kunci: ['bagian'], catatan: 'Agenda + dampak' },
			{ slug: 'demo', label: 'Demo', kunci: ['bagian'], catatan: 'OANDA demo (label DEMO)' }
		]
	},
	{
		kunci: 'gmgn',
		label: 'GMGN',
		rute: '/gmgn',
		ikon: 'gmgn',
		kategori: 'pasar',
		anak: [
			{ slug: 'radar', label: 'Radar', kunci: ['radar'], catatan: 'Window per chain (lokal Webdock)' },
			{ slug: 'lp', label: 'LP', kunci: ['lp_paper', 'bagian', 'pasar_akurasi'], catatan: 'Posisi paper LP, V/L, IL vs hold + akurasi' },
			{ slug: 'memecoin', label: 'Memecoin', kunci: ['gmgn', 'bagian'], catatan: 'Smart money, whale, pumpfun' }
		]
	},
	{
		kunci: 'sistem',
		label: 'Sistem',
		rute: '/sistem',
		ikon: 'sistem',
		kategori: 'sistem',
		anak: [
			{ slug: 'layanan', label: 'Layanan', kunci: [], catatan: 'Unit lintas host, uptime, restart' },
			{ slug: 'kesegaran', label: 'Kesegaran', kunci: [], catatan: 'Matriks umur vs ambang' },
			{ slug: 'biaya', label: 'Biaya', kunci: [], catatan: 'Kuota & konsumsi' },
			{ slug: 'event', label: 'Event', kunci: [], catatan: 'Event log lengkap' },
			{ slug: 'ai', label: 'AI', kunci: [], catatan: 'LLMConsole' },
			{ slug: 'kebijakan', label: 'Kebijakan', kunci: [], catatan: 'agent-policy.json' },
			{ slug: 'audit', label: 'Audit', kunci: [], catatan: 'Jejak perubahan' }
		]
	},
	{
		// Area RISET — mengikuti arsitektur algentis (/performance, /calendar, /tools).
		// Isi kita sendiri: bukti ledger nyata, kalender ekonomi dari bagian.macro,
		// dan kalkulator yang murni berhitung (tak butuh API).
		kunci: 'riset',
		label: 'Riset',
		rute: '/riset',
		ikon: 'riset',
		kategori: 'riset',
		anak: [
			{ slug: 'kinerja', label: 'Kinerja', kunci: ['equity', 'ledger'], catatan: 'Statistik, trade terakhir, PnL per pair' },
			// Halaman Kinerja & Bukti (audit QA putaran 3): tujuh jawaban berdampingan untuk
			// SEMUA pasar — trade tuntas, WR, total R, PnL, drawdown, biaya, periode + denominator.
			{ slug: 'bukti', label: 'Bukti', kunci: [], catatan: 'Semua pasar berdampingan: trade tuntas, biaya, periode, denominator' },
			{ slug: 'kalender', label: 'Kalender', kunci: ['bagian'], catatan: 'Agenda makro: CPI, NFP, FOMC' },
			{ slug: 'alat', label: 'Alat', kunci: [], catatan: 'Position size, likuidasi, risk/reward' }
		]
	},
	{
		// Halaman penjelas — mengikuti /learn, /news, /system, /faq algentis.
		// Isi kita sendiri; berita dari RSS publik.
		kunci: 'info',
		label: 'Info',
		rute: '/catatan',
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
	'/bandar': '/idx?sub=bandarmologi',
	'/lp': '/gmgn?sub=lp',
	'/overextended': '/crypto?sub=overextended',
	// 7 Okt: /bukti dialihkan ke sub Bukti (Riset) — halaman performance & proof.
	'/bukti': '/riset?sub=bukti'
};

/** Bottom tab mobile: 5 utama */
export const TAB_MOBILE = ['/', '/crypto', '/polymarket', '/idx', '/sistem'];

export function areaDariJalur(jalur: string): Area | null {
	const bersih = jalur.length > 1 ? jalur.replace(/\/$/, '') : jalur;
	if (bersih === '/') return AREAS[0];
	return AREAS.find((a) => a.rute === bersih) ?? null;
}

export function labelArea(rute: string): string {
	return AREAS.find((a) => a.rute === rute)?.label ?? rute;
}
