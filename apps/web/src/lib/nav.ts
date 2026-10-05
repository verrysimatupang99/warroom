/**
 * IA (information architecture) War Room.
 * Satu sumber untuk rail, bottom tab, dan sub-nav supaya rute dan chip tidak pernah berbeda definisi.
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
		anak: []
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
			{ slug: 'bandarmologi', label: 'Bandarmologi', kunci: ['bagian'], catatan: 'Broker summary, konsentrasi' },
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
			{ slug: 'lp', label: 'LP', kunci: ['lp_paper'], catatan: 'Posisi paper LP, V/L' },
			{ slug: 'token', label: 'Token', kunci: ['gmgn'], catatan: 'Trading metrics & win rate' },
			{ slug: 'bot', label: 'Bot', kunci: ['bagian'], catatan: 'Uji pumpportal (paper) & memecoin' }
		]
	},
	{
		kunci: 'bukti',
		label: 'Bukti',
		rute: '/bukti',
		ikon: '✓',
		kategori: 'riset',
		anak: []
	},
	{
		kunci: 'bandar',
		label: 'Bandarmologi',
		rute: '/bandar',
		ikon: '🜲',
		kategori: 'riset',
		anak: [
			{ slug: 'broker', label: 'Broker', kunci: ['bagian'], catatan: 'ATS, no-sell, akumulator' },
			{ slug: 'batas', label: 'Batas', kunci: ['bagian'], catatan: 'Yang bisa & tidak bisa diukur' }
		]
	},
	{
		kunci: 'lp',
		label: 'LP Pool',
		rute: '/lp',
		ikon: '≋',
		kategori: 'riset',
		anak: [
			{ slug: 'posisi', label: 'Posisi', kunci: ['bagian'], catatan: 'Uang nyata + IL vs hold' },
			{ slug: 'kandidat', label: 'Kandidat', kunci: ['bagian'], catatan: 'Pencarian pool, urut volume' }
		]
	},
	{
		kunci: 'overextended',
		label: 'Overextended',
		rute: '/overextended',
		ikon: '⟰',
		kategori: 'riset',
		anak: [
			{ slug: 'ukur', label: 'Ukur', kunci: ['bagian'], catatan: 'Pump %, OI vs puncak, FR' },
			{ slug: 'uji', label: 'Uji', kunci: ['bagian'], catatan: 'Apakah short pola ini pernah bayar' }
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