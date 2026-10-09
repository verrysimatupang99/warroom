/**
 * BAHASA MANUSIA — kamus istilah teknis → kalimat awam.
 *
 * Kenapa ini ada (keluhan pemilik 9 Okt 2026):
 *   "gw rasa makin susah aja dilihat webnya, terlalu pro, padahal targetnya bot trading doang"
 *
 * War Room tumbuh jadi dashboard quant: 85 istilah teknis di halaman Polymarket, 690 angka
 * di satu layar IDX. Pemakainya (pemilik) cuma mau tahu: "bot-ku hari ini ngapain, ada yang
 * layak dibeli atau tidak?" — bukan membaca `ci_low`, `deff`, `promotable`.
 *
 * ATURAN MODUL INI:
 *   - SATU tempat terjemahan. Kalau istilahnya muncul di 5 halaman, penjelasannya di sini,
 *     bukan disalin 5 kali (supaya tidak ada dua definisi yang pelan-pelan berbeda).
 *   - Angka TIDAK dikarang. Kamus ini hanya mengubah BAHASA, bukan nilai.
 *   - Istilah teknisnya TIDAK dibuang — dipindah ke balik tanda tanya / <details>. Yang mau
 *     detail tetap bisa membukanya; yang tidak, tidak dipaksa melihatnya.
 */

/** Satu entri kamus: istilah singkat + penjelasan manusia + istilah teknis aslinya. */
export interface Istilah {
	/** Nama yang tampil ke pemakai (bahasa manusia). */
	manusia: string;
	/** Kalimat penjelas, satu-dua baris, tanpa jargon. */
	artinya: string;
	/** Istilah teknis asli — untuk yang memang mau tahu. */
	teknis?: string;
}

/**
 * KAMUS. Kunci = istilah teknis yang muncul di UI; nilai = versi manusianya.
 * Ditulis dari kode & dokumen nyata (ADR-003, gate.py, pakem sampel), bukan karangan.
 */
export const KAMUS: Record<string, Istilah> = {
	gate: {
		manusia: 'pemeriksaan wajib',
		artinya:
			'Sebelum bot membeli, hasilnya harus lulus beberapa pemeriksaan (jumlah contoh cukup, untung di atas titik impas, data dibekukan). Kalau belum lulus, bot TIDAK beli — itu normal, bukan error.',
		teknis: 'gate: n≥30, Wilson 90%, ci_low > BE, split beku (ADR-003)'
	},
	'LOLOS GATE': {
		manusia: 'layak dibeli',
		artinya: 'Sudah melewati semua pemeriksaan wajib. Baru pada tahap ini keputusan beli boleh dipertimbangkan.',
		teknis: 'promotable: verdict=lolos'
	},
	promotable: {
		manusia: 'layak dibeli',
		artinya: 'Sudah lulus semua pemeriksaan. Angka ini biasanya 0, dan itu jujur — lebih baik menunggu daripada memaksa beli.',
		teknis: 'promotable_edge = true'
	},
	kandidat: {
		manusia: 'yang dipantau',
		artinya:
			'Ada sesuatu yang sedang diikuti bot, TAPI belum tentu layak dibeli. Ini daftar pantauan, bukan daftar rekomendasi.',
		teknis: 'kandidat (status_data=ada)'
	},
	verdict: {
		manusia: 'kesimpulan bot',
		artinya: 'Hasil penilaian akhir bot untuk satu pasar: layak dibeli, ditolak, atau belum cukup data.',
		teknis: 'verdict'
	},
	'break-even': {
		manusia: 'titik impas',
		artinya:
			'Batas minimal menang supaya tidak rugi. Kalau tingkat menang di bawah angka ini, strategi itu merugi walau terlihat "sering benar".',
		teknis: 'BE (break-even)'
	},
	'breakEven_pct': {
		manusia: 'titik impas',
		artinya: 'Batas minimal menang supaya tidak rugi.',
		teknis: 'breakEven_pct'
	},
	arm: {
		manusia: 'aturan beli',
		artinya: 'Satu cara spesifik bot memutuskan kapan membeli. Bot menguji beberapa cara sekaligus lalu memilih yang terbukti.',
		teknis: 'arm A/B/C/D'
	},
	deff: {
		manusia: 'ukuran keunggulan',
		artinya: 'Seberapa kuat keunggulan strategi di atas keberuntungan, setelah memperhitungkan jumlah contoh.',
		teknis: 'deff (defective effect)'
	},
	edge: {
		manusia: 'keunggulan',
		artinya: 'Kelebihan strategi yang membuatnya untung dalam jangka panjang, bukan sekadar hoki.',
		teknis: 'edge'
	},
	split: {
		manusia: 'pemisahan data',
		artinya:
			'Data dibagi: satu bagian untuk melatih, satu bagian untuk menguji. Hasil baru boleh dipercaya kalau data ujinya dibekukan sebelum dilihat.',
		teknis: 'split / split beku'
	},
	split_beku: {
		manusia: 'data uji dibekukan',
		artinya: 'Data uji dikunci lebih dulu supaya bot tidak "menghafal" jawabannya. Tanpa ini, hasilnya belum boleh dipercaya.',
		teknis: 'split=frozen'
	},
	Wilson: {
		manusia: 'perhitungan statistik',
		artinya: 'Cara menghitung batas bawah keyakinan dari hasil yang ada. Dipakai supaya bot tidak tertipu hasil bagus yang kebetulan.',
		teknis: 'Wilson interval'
	},
	ci_low: {
		manusia: 'batas bawah keyakinan',
		artinya: 'Angka paling pesimis dari rentang keyakinan. Bot hanya beli kalau angka paling pesimis ini sudah untung.',
		teknis: 'ci_low'
	},
	CI: {
		manusia: 'rentang keyakinan',
		artinya: 'Rentang tempat nilai sebenarnya kemungkinan besar berada. Makin sempit, makin yakin.',
		teknis: 'confidence interval'
	},
	drawdown: {
		manusia: 'penurunan terburuk',
		artinya: 'Seberapa dalam saldo pernah turun dari puncaknya. Ukuran risiko terburuk yang pernah dialami.',
		teknis: 'max drawdown'
	},
	'mean R': {
		manusia: 'rata-rata untung/rugi',
		artinya: 'Rata-rata hasil per transaksi dalam satuan risiko. Positif berarti untung, negatif berarti rugi.',
		teknis: 'mean R (risk multiple)'
	},
	WR: {
		manusia: 'tingkat menang',
		artinya: 'Persentase transaksi yang berakhir untung. Tinggi belum tentu bagus kalau yang rugi lebih besar.',
		teknis: 'win rate'
	},
	ledger: {
		manusia: 'catatan transaksi',
		artinya: 'Buku besar berisi SEMUA transaksi yang pernah terjadi — termasuk yang rugi. Tidak ada yang disembunyikan.',
		teknis: 'ledger'
	},
	paper: {
		manusia: 'uji coba (tanpa uang asli)',
		artinya: 'Bot berdagang dengan uang mainan dulu untuk membuktikan strateginya, sebelum memakai uang sungguhan.',
		teknis: 'paper trading'
	},
	snapshot: {
		manusia: 'rekaman kondisi',
		artinya: 'Gambar data pasar pada satu waktu tertentu, dipakai bot untuk mengambil keputusan.',
		teknis: 'snapshot'
	},
	provenance: {
		manusia: 'asal-usul angka',
		artinya: 'Dari mana angka ini datang, dan kapan terakhir diperbarui. Kalau sumbernya tak terbaca, ditulis apa adanya.',
		teknis: 'provenance'
	}
};

/** Pakem sampel (tingkat kepercayaan data) → bahasa manusia. */
export const PAKEM: Record<string, Istilah> = {
	INSUFFICIENT: {
		manusia: 'data masih sedikit',
		artinya: 'Kurang dari 10 hari data. Belum boleh dipakai mengambil keputusan apa pun.',
		teknis: 'INSUFFICIENT'
	},
	DIRECTIONAL: {
		manusia: 'baru arah kasar',
		artinya: 'Kurang dari 30 hari. Bisa menunjukkan arah, tapi belum boleh diklaim menghasilkan untung.',
		teknis: 'DIRECTIONAL'
	},
	PRELIMINARY: {
		manusia: 'evaluasi awal',
		artinya: 'Kurang dari 100 hari. Cukup untuk evaluasi awal, belum untuk keputusan besar.',
		teknis: 'PRELIMINARY'
	},
	TUNING: {
		manusia: 'data sudah cukup',
		artinya: '100 hari atau lebih. Baru pada tahap ini strategi boleh disetel ulang.',
		teknis: 'TUNING'
	}
};

/** Cari terjemahan satu istilah. Tak ada → kembalikan apa adanya (jangan mengarang). */
export function arti(istilah: string): Istilah | null {
	return KAMUS[istilah] ?? PAKEM[istilah] ?? null;
}

/** Versi manusia dari satu istilah; kalau tak dikenal, kembalikan aslinya. */
export function manusia(istilah: string): string {
	return arti(istilah)?.manusia ?? istilah;
}
