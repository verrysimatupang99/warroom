#!/usr/bin/env node
/**
 * Lint token War Room — cegah nilai desain hardcoded masuk ke komponen/rute.
 *
 * Kenapa ini ada (bukan memakai validator generik skill):
 *   `app.css` ADALAH sumber token (lapis primitive), jadi hex di sana sah. Yang
 *   harus dicegah adalah hex/ukuran hardcoded di KOMPONEN dan RUTE — di situ nilai
 *   harus menunjuk token, supaya ganti tema/palet cukup di satu tempat.
 *
 * Aturan:
 *   1. `#rrggbb` / `#rgb` di dalam berkas .svelte (style maupun atribut) -> gagal.
 *      (Pengecualian: di dalam komentar.)
 *   2. Nilai panjang absolut di inline `style="..."` (px/rem) -> gagal.
 *      Padding/margin lewat kelas Tailwind atau token; jangan angka mentah.
 *
 * Pakai: node scripts/lint-tokens.mjs [dir]   (default: src)
 * Keluar 0 bila bersih, 1 bila ada pelanggaran.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

const ROOT = process.argv[2] || 'src';
const SKIP_DIRS = new Set(['node_modules', '.svelte-kit', 'build', 'dist', '.git']);

/** Buang komentar pada SATU baris (blok `/* */`, HTML, dan `//`), tanpa menyentuh URL. */
function barisTanpaKomentar(line) {
	return line
		.replace(/\/\*[\s\S]*?\*\//g, '')
		.replace(/<!--[\s\S]*?-->/g, '')
		.replace(/(^|\s)\/\/[^\n]*/g, '$1');
}

const pelanggaran = [];
const files = [];
(function walk(dir) {
	for (const name of readdirSync(dir)) {
		if (SKIP_DIRS.has(name)) continue;
		const p = join(dir, name);
		if (statSync(p).isDirectory()) walk(p);
		else if (p.endsWith('.svelte')) files.push(p);
	}
})(ROOT);
for (const f of files) {
	const raw = readFileSync(f, 'utf8').split('\n');
	// Diproses PER BARIS: penanda `lint-tokens-disable` sering ditulis di dalam
	// komentar CSS, jadi kalau komentar dibuang lebih dulu penandanya ikut hilang.
	let aktif = true;
	raw.forEach((line, i) => {
		if (/lint-tokens-disable/.test(line)) { aktif = false; return; }
		if (/lint-tokens-enable/.test(line)) { aktif = true; return; }
		if (!aktif) return;
		const bersih = barisTanpaKomentar(line);

		// 1) hex warna
		const hex = bersih.match(/#(?:[0-9a-fA-F]{3}){1,2}\b/);
		if (hex) {
			pelanggaran.push({ f, line: i + 1, jenis: 'hex', nilai: hex[0], teks: line.trim().slice(0, 90) });
		}
		// 2) inline style dengan px/rem absolut
		const st = bersih.match(/style="[^"]*?(\d+(?:\.\d+)?(?:px|rem))/);
		if (st) {
			pelanggaran.push({ f, line: i + 1, jenis: 'inline-panjang', nilai: st[1], teks: line.trim().slice(0, 90) });
		}
	});
}

if (pelanggaran.length === 0) {
	console.log(`lint-tokens: bersih — ${files.length} berkas .svelte, 0 nilai hardcoded.`);
	process.exit(0);
}

console.error(`lint-tokens: ${pelanggaran.length} pelanggaran di ${files.length} berkas:`);
for (const p of pelanggaran) {
	console.error(`  ${relative(process.cwd(), p.f)}:${p.line}  [${p.jenis} ${p.nilai}]  ${p.teks}`);
}
console.error('\nGunakan token (var(--color-*), kelas text-*/p-*, atau --card-*), bukan nilai mentah.');
process.exit(1);
