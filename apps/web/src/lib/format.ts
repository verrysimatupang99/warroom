/**
 * Format `id-ID` terpusat. Prinsip keras proyek: angka yang tidak ada ditampilkan `—`,
 * bukan 0 — jadi helper di sini tidak pernah mengarang nilai.
 */

export const TAK_ADA = '—';

/** True bila nilai punya isi yang bisa ditampilkan. */
export function ada(v: unknown): boolean {
	return v !== null && v !== undefined && v !== '';
}

/**
 * Status risiko bersama — SATU definisi ambang untuk KPI Home dan RiskMeter.
 *
 * Kenapa dipisah: badge "AMAN" dulu dipatok literal di kartu KPI (temuan 5 Okt 2026),
 * jadi bisa bilang "AMAN" walau data risiko belum ada / sudah lewat batas. Fungsi ini
 * memaksa kedua tempat memakai ambang yang sama persis (90% / 60%).
 *
 * PERBAIKAN 7 Okt (temuan saat mengerjakan tab Eksekusi): `hari_ini_r` adalah PnL
 * HARI INI dalam R — NEGATIF berarti rugi. Versi lama memakai `Math.abs()`, sehingga
 * hari yang PROFIT (+4R) ditampilkan sebagai "LIMIT TERCAPAI" — pembaca melihat
 * "risiko terpakai 4R / 3R" padahal itu keuntungan. Sekarang yang dihitung sebagai
 * risiko hanya kerugian; hari profit selalu AMAN.
 */
export interface StatusRisiko {
	label: string;
	kelas: string;
}

export function statusRisikoDari(hariIniR: unknown, batasR: unknown): StatusRisiko {
	if (!ada(hariIniR) || !ada(batasR) || Number(batasR) <= 0) {
		return { label: '—', kelas: 'text-text-3 bg-surface border-line' };
	}
	// Risiko = hanya sisi RUGI. Profit tidak memakai kuota batas rugi.
	const rugiR = Math.max(0, -Number(hariIniR));
	const pct = Math.min(100, Math.max(0, (rugiR / Number(batasR)) * 100));
	if (pct >= 90) return { label: 'LIMIT TERCAPAI', kelas: 'text-neg bg-neg/10 border-neg/40' };
	if (pct >= 60) return { label: 'WASPADA', kelas: 'text-warn bg-warn/10 border-warn/40' };
	return { label: 'AMAN', kelas: 'text-pos bg-pos/10 border-pos/40' };
}

/** Kuota risiko harian terpakai (0–100). Hanya kerugian yang menghabiskan kuota. */
export function persenRisikoTerpakai(hariIniR: unknown, batasR: unknown): number {
	if (!ada(hariIniR) || !ada(batasR) || Number(batasR) <= 0) return 0;
	const rugiR = Math.max(0, -Number(hariIniR));
	return Math.min(100, Math.max(0, (rugiR / Number(batasR)) * 100));
}

function keAngka(v: unknown): number | null {
	if (!ada(v)) return null;
	const n = typeof v === 'number' ? v : Number(v);
	return Number.isFinite(n) ? n : null;
}

/** Angka id-ID dengan pemisah ribuan desimal koma. Hilang/aneh → `—`. */
export function angka(v: unknown, opsi: { desimal?: number; tanda?: boolean } = {}): string {
	const n = keAngka(v);
	if (n === null) return TAK_ADA;
	const d = opsi.desimal ?? 2;
	return new Intl.NumberFormat('id-ID', {
		minimumFractionDigits: d,
		maximumFractionDigits: d,
		signDisplay: opsi.tanda ? 'exceptZero' : 'auto'
	}).format(n);
}

/** Bilangan bulat id-ID. */
export function bulat(v: unknown): string {
	return angka(v, { desimal: 0 });
}

/** Persentase dari proporsi 0..1. */
export function persen(v: unknown, desimal = 2): string {
	const n = keAngka(v);
	if (n === null) return TAK_ADA;
	return `${angka(n * 100, { desimal })}%`;
}

/** Rupiah utuh (tanpa sen). */
export function rupiah(v: unknown): string {
	const n = keAngka(v);
	if (n === null) return TAK_ADA;
	return `Rp ${angka(n, { desimal: 0 })}`;
}

/**
 * Umur dalam detik → bentuk pendek mono: `45s`, `10m`, `2j`, `3h`.
 * Dipakai badge kesegaran sehingga formatnya konsisten dengan blueprint `segar Xm`.
 */
export function umurDetik(s: number | null | undefined): string {
	const n = keAngka(s);
	if (n === null) return TAK_ADA;
	const a = Math.abs(n);
	if (a < 60) return `${Math.round(a)}s`;
	if (a < 3600) return `${Math.round(a / 60)}m`;
	if (a < 86400) return `${Math.round(a / 3600)}j`;
	return `${Math.round(a / 86400)}h`;
}

const TZ = 'Asia/Jakarta';

/** Tanggal+jam WIB: `02 Okt 2026 04:12 WIB`. */
export function waktuWIB(iso: string | null | undefined): string {
	if (!ada(iso)) return TAK_ADA;
	const d = new Date(iso as string);
	if (Number.isNaN(d.getTime())) return TAK_ADA;
	const tgl = new Intl.DateTimeFormat('id-ID', {
		timeZone: TZ,
		day: '2-digit',
		month: 'short',
		year: 'numeric',
		hour: '2-digit',
		minute: '2-digit',
		hour12: false
	}).format(d);
	return `${tgl} WIB`;
}

/** Jam WIB dengan detik, untuk jam topbar. */
export function jamWIB(d: Date = new Date()): string {
	return new Intl.DateTimeFormat('id-ID', {
		timeZone: TZ,
		hour: '2-digit',
		minute: '2-digit',
		second: '2-digit',
		hour12: false
	}).format(d);
}

/** Nilai apa pun → teks ringkas untuk tabel (objek/array dipadatkan). */
export function teksNilai(v: unknown): string {
	if (!ada(v)) return TAK_ADA;
	if (typeof v === 'number') return angka(v);
	if (typeof v === 'boolean') return v ? 'ya' : 'tidak';
	if (typeof v === 'string') return v;
	try {
		return JSON.stringify(v);
	} catch {
		return String(v);
	}
}

/** Nilai apa pun → angka untuk grafik; null bila bukan angka. */
export function seriAngka(v: unknown): number[] {
	if (!Array.isArray(v)) return [];
	return v.map((x) => keAngka(x)).filter((x): x is number => x !== null);
}

function sel(v: unknown): string {
	const t = teksNilai(v);
	// Kutip bila mengandung pemisah agar CSV tetap sah.
	return /[",\n;]/.test(t) ? `"${t.replace(/"/g, '""')}"` : t;
}

/** Matriks → teks CSV (pemisah `;` supaya ramah Excel id-ID yang memakai koma desimal). */
export function keCSV(kepala: string[], baris: unknown[][]): string {
	const garis = [kepala.map(sel).join(';'), ...baris.map((r) => r.map(sel).join(';'))];
	return `${garis.join('\n')}\n`;
}

/** Unduh teks sebagai berkas (browser). Di lingkungan uji/jsdom jadi no-op aman. */
export function unduhTeks(nama: string, isi: string, tipe = 'text/csv;charset=utf-8'): void {
	if (typeof document === 'undefined' || typeof URL.createObjectURL !== 'function') return;
	const blob = new Blob([isi], { type: tipe });
	const url = URL.createObjectURL(blob);
	const a = document.createElement('a');
	a.href = url;
	a.download = nama;
	a.rel = 'noopener';
	document.body.appendChild(a);
	a.click();
	a.remove();
	URL.revokeObjectURL(url);
}