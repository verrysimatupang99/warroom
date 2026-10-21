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
			{ slug: 'setup', label: 'Sinyal & Setup', kunci: ['kandidat', 'crypto_sinyal', 'pasar_akurasi'], catatan: 'Kandidat SMC + verdict per aturan + entry setup' },
			{ slug: 'alat', label: 'Alat / Tools', kunci: ['bagian', 'risiko'], catatan: 'SMC POI Scanner, leverage & kalkulator margin likuidasi' },
			{ slug: 'ukur', label: 'Kuantitatif / Backtest', kunci: ['pengukuran', 'backtest', 'pasar_akurasi'], catatan: 'Forward lolos vs ditolak + lab backtest + akurasi' },
			{ slug: 'eksekusi', label: 'Eksekusi / Paper Ledger', kunci: ['posisi', 'ledger'], catatan: 'Paper, fill, ledger, overextended' }
		]
	},
	{
		kunci: 'polymarket',
		label: 'Polymarket',
		rute: '/polymarket',
		ikon: 'polymarket',
		kategori: 'pasar',
		anak: [
			{ slug: 'cockpit', label: 'Cockpit', kunci: ['poly_paper', 'pasar_akurasi', 'dompet'], catatan: 'Ringkasan pasar Polymarket, akurasi, dan dompet paper' },
			{ slug: 'setup', label: 'Sinyal & Setup', kunci: ['poly_paper', 'pasar_akurasi'], catatan: 'Band favorit 0,70–0,95 + PolyBTC 5m momentum' },
			{ slug: 'alat', label: 'Alat / Tools', kunci: ['poly_paper'], catatan: 'Kelly sizing binary options & parity drift spot vs binary' },
			{ slug: 'ukur', label: 'Kuantitatif / Backtest', kunci: ['bagian', 'poly_paper'], catatan: 'Dataset, parity/drift, katalog replay dan pengujian kuantitatif' },
			{ slug: 'eksekusi', label: 'Eksekusi / Paper Ledger', kunci: ['equity', 'ledger', 'poly_paper'], catatan: 'Paper trade ledger, arming 3-way, dan eksekusi' }
		]
	},
	{
		kunci: 'idx',
		label: 'IDX',
		rute: '/idx',
		ikon: 'idx',
		kategori: 'pasar',
		anak: [
			{ slug: 'cockpit', label: 'Cockpit', kunci: ['idx_sinyal', 'idx_akurasi', 'bandarmologi_skor', 'bagian', 'dompet'], catatan: 'Overview pasar modal domestik, emiten aktif, dan metrik bandarmologi' },
			{ slug: 'setup', label: 'Sinyal & Setup', kunci: ['bagian', 'bandarmologi_skor', 'idx_sinyal'], catatan: 'Sinyal BSJP, ARA Hunter, dan Broker Summary' },
			{ slug: 'alat', label: 'Alat / Tools', kunci: ['bandarmologi_skor', 'bagian'], catatan: 'Foreign flow tracker, bandarmologi ATS analyzer & cash risk sizer' },
			{ slug: 'ukur', label: 'Kuantitatif / Backtest', kunci: ['bagian', 'idx_akurasi'], catatan: 'Uji statistik BSJP, backtest aturan ARA, dan akurasi emiten' },
			{ slug: 'eksekusi', label: 'Eksekusi / Paper Ledger', kunci: ['bagian', 'dompet'], catatan: 'Simulasi paper trade portofolio IDX dan riwayat transaksi' }
		]
	},
	{
		kunci: 'forex',
		label: 'Forex',
		rute: '/forex',
		ikon: 'forex',
		kategori: 'pasar',
		anak: [
			{ slug: 'cockpit', label: 'Cockpit', kunci: ['bagian', 'forex_sinyal', 'pasar_akurasi'], catatan: 'Struktur harga Gold (XAU/USD) & Pair Forex, bias EMA, dan metrik kuantitatif' },
			{ slug: 'setup', label: 'Sinyal & Setup', kunci: ['bagian', 'forex_sinyal'], catatan: 'Setup Break & Retest, zona entry, dan jadwal sesi market' },
			{ slug: 'alat', label: 'Alat / Tools', kunci: ['bagian', 'forex_sinyal'], catatan: 'Prop-firm safety guard $5K Global4Ex, lot sizer & macro stand-down calendar' },
			{ slug: 'ukur', label: 'Kuantitatif / Backtest', kunci: ['bagian', 'pasar_akurasi'], catatan: 'Hasil backtest & tuning parameter 15m Gold/Forex' },
			{ slug: 'eksekusi', label: 'Eksekusi / Paper Ledger', kunci: ['bagian'], catatan: 'Paper execution ledger & Forward trading test' }
		]
	},
	{
		kunci: 'gmgn',
		label: 'GMGN',
		rute: '/gmgn',
		ikon: 'gmgn',
		kategori: 'pasar',
		anak: [
			{ slug: 'cockpit', label: 'Cockpit', kunci: ['radar', 'gmgn', 'pasar_akurasi'], catatan: 'Overview likuiditas on-chain, scanner pool, dan metrik smart money' },
			{ slug: 'setup', label: 'Sinyal & Setup', kunci: ['gmgn', 'bagian'], catatan: 'Deteksi token baru, sinyal pumpfun, dan radar likuiditas' },
			{ slug: 'alat', label: 'Alat / Tools', kunci: ['gmgn', 'radar'], catatan: 'Smart money inflow radar, dev wallet score & slippage calculator' },
			{ slug: 'ukur', label: 'Kuantitatif / Backtest', kunci: ['lp_paper', 'bagian', 'pasar_akurasi'], catatan: 'Ukur IL vs Hold, simulasi yield, dan metrik LP' },
			{ slug: 'eksekusi', label: 'Eksekusi / Paper Ledger', kunci: ['lp_paper', 'bagian'], catatan: 'Paper trade runner GMGN & transaksi pool' }
		]
	},
	{
		kunci: 'sistem',
		label: 'Sistem',
		rute: '/sistem',
		ikon: 'sistem',
		kategori: 'sistem',
		anak: [
			{ slug: 'layanan', label: 'Layanan', kunci: ['bagian'], catatan: 'Unit lintas host, uptime, restart' },
			{ slug: 'mesin', label: 'Mesin', kunci: ['lpagent'], catatan: 'Sumber data pihak ketiga: LP Agent (telemetri Solana/Meteora)' },
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
			{ slug: 'leaderboard', label: 'Leaderboard', kunci: ['equity', 'ledger'], catatan: 'Papan peringkat strategi kuantitatif, status setup & rekonsiliasi' },
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

/** Bottom tab mobile: 5 slot penuh + menu "Lainnya" (BottomNav).
 *  Riset & Info TIDAK masuk slot — dijangkau lewat "Lainnya" bersama Forex & GMGN
 *  (10 Okt 2026). Alasan: 7–9 sel selebar jempol berdesakan di 360px; 5 primer +
 *  overflow satu ketuk menjaga target sentuh & keterbacaan label. NavBar desktop
 *  tetap menampilkan kesembilan area tanpa overflow. */
export const TAB_MOBILE = ['/', '/crypto', '/polymarket', '/idx', '/sistem'];

export function areaDariJalur(jalur: string): Area | null {
	const bersih = jalur.length > 1 ? jalur.replace(/\/$/, '') : jalur;
	if (bersih === '/') return AREAS[0];
	return AREAS.find((a) => a.rute === bersih) ?? null;
}

export function labelArea(rute: string): string {
	return AREAS.find((a) => a.rute === rute)?.label ?? rute;
}
