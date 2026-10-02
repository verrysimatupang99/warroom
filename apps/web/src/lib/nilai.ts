/**
 * Membaca bentuk nilai fakta apa adanya → ubin/tabel. Tidak ada nilai turunan yang dikarang:
 * hanya angka yang benar-benar ada di `value` yang muncul; sisanya ditandai kosong di UI.
 */

export interface TileNilai {
	label: string;
	nilai: number | null;
	jalur: string;
}

export interface KolomTabel {
	kunci: string;
	label: string;
	numerik: boolean;
}

export interface TabelNilai {
	judul: string;
	kolom: KolomTabel[];
	baris: Record<string, unknown>[];
}

function labelDari(jalur: string[]): string {
	return jalur
		.filter((j) => j !== '_kunci')
		.join(' › ')
		.replace(/_/g, ' ');
}

/** Angka pada objek (kedalaman ≤ 2). Array tidak dijadikan ubin — itu tugas tabel. */
export function tilesDari(v: unknown): TileNilai[] {
	const keluar: TileNilai[] = [];
	const jalan = (o: unknown, jalur: string[], kedalaman: number) => {
		if (!o || typeof o !== 'object' || Array.isArray(o) || kedalaman > 2) return;
		for (const [k, val] of Object.entries(o as Record<string, unknown>)) {
			if (typeof val === 'number' && Number.isFinite(val)) {
				keluar.push({ label: labelDari([...jalur, k]), nilai: val, jalur: [...jalur, k].join('.') });
			} else if (val && typeof val === 'object' && !Array.isArray(val)) {
				jalan(val, [...jalur, k], kedalaman + 1);
			}
		}
	};
	jalan(v, [], 0);
	return keluar.slice(0, 12);
}

function kolomUntuk(baris: Record<string, unknown>[]): KolomTabel[] {
	const kunci: string[] = [];
	for (const b of baris) {
		for (const k of Object.keys(b)) if (!kunci.includes(k)) kunci.push(k);
	}
	return kunci
		.filter((k) => {
			// hanya medan skalar yang berguna sebagai kolom
			return baris.some((b) => {
				const x = b[k];
				return x === null || ['string', 'number', 'boolean'].includes(typeof x);
			});
		})
		.slice(0, 10)
		.map((k) => ({
			kunci: k,
			label: k.replace(/_/g, ' '),
			numerik: baris.every((b) => b[k] === null || b[k] === undefined || typeof b[k] === 'number')
		}));
}

function tabelArray(judul: string, arr: unknown[]): TabelNilai | null {
	if (!arr.length) return null;
	const baris = arr.filter((x): x is Record<string, unknown> => !!x && typeof x === 'object' && !Array.isArray(x));
	if (!baris.length) return null;
	const kolom = kolomUntuk(baris);
	if (!kolom.length) return null;
	return { judul, kolom, baris };
}

/** Tabel dari array-of-objects atau object-of-objects (mis. `per_aturan`). */
export function tabelDari(v: unknown): TabelNilai[] {
	const keluar: TabelNilai[] = [];
	if (!v || typeof v !== 'object') return keluar;
	if (Array.isArray(v)) {
		const t = tabelArray('data', v);
		if (t) keluar.push(t);
		return keluar;
	}
	for (const [k, val] of Object.entries(v as Record<string, unknown>)) {
		if (Array.isArray(val)) {
			const t = tabelArray(k, val);
			if (t) keluar.push(t);
		} else if (val && typeof val === 'object') {
			const isi = Object.values(val as Record<string, unknown>);
			const semuaObjek =
				isi.length > 0 &&
				isi.every((x) => !!x && typeof x === 'object' && !Array.isArray(x));
			if (semuaObjek) {
				const baris = Object.entries(val as Record<string, Record<string, unknown>>).map(
					([kk, vv]) => ({ _kunci: kk, ...vv })
				);
				const t = tabelArray(k, baris);
				if (t) keluar.push(t);
			}
		}
	}
	return keluar;
}

/** Seri untuk sparkline — hanya dari data yang memang berupa deret (mis. equity.points[].cum). */
export function seriDari(_kunci: string, v: unknown): number[] {
	if (Array.isArray(v) && v.every((x) => typeof x === 'number')) return v as number[];
	if (v && typeof v === 'object') {
		const o = v as Record<string, unknown>;
		if (Array.isArray(o.points)) {
			const cum = o.points
				.map((p) => (p && typeof p === 'object' ? (p as Record<string, unknown>).cum : undefined))
				.filter((x): x is number => typeof x === 'number');
			if (cum.length >= 2) return cum;
			const r = o.points
				.map((p) => (p && typeof p === 'object' ? (p as Record<string, unknown>).r : undefined))
				.filter((x): x is number => typeof x === 'number');
			if (r.length >= 2) return r;
		}
	}
	return [];
}

/** Ringkasan satu nilai untuk ditampilkan di drawer/JSON. */
export function ringkasNilai(v: unknown): string {
	if (v === null || v === undefined) return '—';
	if (typeof v === 'string') return v;
	try {
		return JSON.stringify(v, null, 2);
	} catch {
		return String(v);
	}
}