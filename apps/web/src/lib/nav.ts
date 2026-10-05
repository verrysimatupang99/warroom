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
	ikon: string;
	kategori: 'pasar' | 'riset' | 'sistem';
	anak: Anak[];
}

export const AREAS: Area[] = [
	{
		kunci: 'home',
		label: 'Home',
		rute: '/',
		ikon: '⌂',
		kategori: 'pasar',
		anak: [
			{ slug: 'sinyal', label: 'Sinyal', kunci: [], catatan: 'Satu kartu sinyal terbaik per pasar' },
			{ slug: 'kinerja', label: 'Kinerja', kunci: [], catatan: 'Kurva ekuitas, leaderboard, risiko, kejadian' }
		]
	},
	{
		kunci: 'crypto',
		label: 'Crypto',
		rute: '/crypto',
		ikon: '₿',
		kategori: 'pasar',
		anak: [
			{ slug: 'cockpit', label: 'Cockpit', kunci: ['bagian', 'risiko', 'posisi'], catatan: 'Pair utama, risiko, posisi' },
			{ slug: 'setup', label: 'Setup', kunci: ['kandidat'], catatan: 'Kandidat SMC + verdict per aturan' },
			{ slug: 'ukur', label: 'Ukur', kunci: ['pengukuran'], catatan: 'Forward: lolos vs ditolak' },
			{ slug: 'lab', label: 'Lab', kunci: ['backtest'], catatan: 'Walk-forward, uji klaster & beda' },
			{ slug: 'overextended', label: 'Overextended', kunci: ['bagian'], catatan: 'Pump %, OI vs puncak, funding rate' },
			{ slug: 'eksekusi', label: 'Eksekusi', kunci: ['posisi', 'ledger'], catatan: 'Paper, fill, riwayat perintah' },
			{ slug: 'data', label: 'Data', kunci: ['pod_llm', 'bagian'], catatan: 'Kesehatan jalur & gap' }
		]
	},
	{
		kunci: 'polymarket',
		label: 'Polymarket',
		rute: '/polymarket',
		ikon: '◎',
		kategori: 'pasar',
		anak: [
			{ slug: 'verdict', label: 'Verdict', kunci: ['poly_paper', 'bagian'], catatan: 'n vs n dibutuhkan, CI vs BE' },
			{ slug: 'arm', label: 'Arm', kunci: ['poly_paper'], catatan: 'A/B/C/D + agen' },
			{ slug: 'agen', label: 'Agen', kunci: ['bagian'], catatan: 'Config, pelajaran, patch' },
			{ slug: 'dataset', label: 'Dataset', kunci: ['bagian'], catatan: 'Window, label, kualitas' },
			{ slug: 'replay', label: 'Replay', kunci: ['poly_paper'], catatan: 'Rentang beku' },
			{ slug: 'parity', label: 'Parity', kunci: ['bagian'], catatan: 'Drift mirror vs eksekutor' },
			{ slug: 'biaya', label: 'Biaya', kunci: ['lp_paper'], catatan: 'Fee, slippage, kapasitas' },
			{ slug: 'live', label: 'Live', kunci: ['equity', 'ledger'], catatan: 'Arming 3-way, dana nyata' }
		]
	},
	{
		kunci: 'idx',
		label: 'IDX',
		rute: '/idx',
		ikon: '▦',
		kategori: 'pasar',
		anak: [
			{ slug: 'screener', label: 'Screener', kunci: ['bagian'], catatan: 'Arjum × TradingView' },
			{ slug: 'bandarmologi', label: 'Bandarmologi', kunci: ['bagian'], catatan: 'Broker summary, ATS, no-sell' },
			{ slug: 'bsjp', label: 'BSJP', kunci: ['bagian'], catatan: 'Beli Sore Jual Pagi — uji edge overnight' },
			{ slug: 'aliran', label: 'Aliran', kunci: ['bagian'], catatan: 'Asing vs lokal' },
			{ slug: 'watchlist', label: 'Watchlist', kunci: ['bagian'], catatan: 'ARA Hunter & setup' }
		]
	},
	{
		kunci: 'forex',
		label: 'Forex',
		rute: '/forex',
		ikon: '⇄',
		kategori: 'pasar',
		anak: [
			{ slug: 'struktur', label: 'Struktur', kunci: ['bagian'], catatan: 'Bias, EMA, ATR, level kunci' },
			{ slug: 'sesi', label: 'Sesi', kunci: ['bagian'], catatan: 'Asia/London/NY (WIB)' },
			{ slug: 'kalender', label: 'Kalender', kunci: ['bagian'], catatan: 'Agenda + dampak' },
			{ slug: 'demo', label: 'Demo', kunci: ['bagian'], catatan: 'OANDA demo (label DEMO)' }
		]
	},
	{
		kunci: 'gmgn',
		label: 'GMGN',
		rute: '/gmgn',
		ikon: '⚡',
		kategori: 'pasar',
		anak: [
			{ slug: 'radar', label: 'Radar', kunci: ['radar'], catatan: 'Window per chain (Azure, baca-saja)' },
			{ slug: 'lp', label: 'LP', kunci: ['lp_paper', 'bagian'], catatan: 'Posisi paper LP, V/L, IL vs hold' },
			{ slug: 'token', label: 'Token', kunci: ['gmgn'], catatan: 'Trading metrics & win rate' },
			{ slug: 'bot', label: 'Bot', kunci: ['bagian'], catatan: 'Uji pumpportal (paper) & memecoin' }
		]
	},
	{
		kunci: 'sistem',
		label: 'Sistem',
		rute: '/sistem',
		ikon: '⚙',
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
	'/bukti': '/sistem?sub=kesegaran'
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
