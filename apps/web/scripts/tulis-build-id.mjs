/**
 * Tulis identitas build ke `build/build-id.txt` setelah `vite build` selesai.
 *
 * Kenapa ada: insiden 2026-10-08/09 — build web selesai 21:00 tetapi proses node yang
 * jalan berasal dari 20:58. Proses memegang manifest lama di memori sementara chunk di
 * disk sudah diganti build baru -> HTTP 500 di SEMUA halaman, tanpa cara mendeteksinya.
 *
 * Dengan file ini, skrip deploy bisa membandingkan:
 *   - build_id di DISK (file ini, hasil build terakhir), dan
 *   - build_id yang dilaporkan PROSES yang sedang jalan (lewat /api/v1/build atau env).
 * Bila berbeda -> proses belum di-restart -> deploy harus menolak melapor "ok".
 *
 * Sumber build_id (urut prioritas):
 *   1. env WARROOM_BUILD_ID  (di-set oleh skrip deploy)
 *   2. git rev-parse --short HEAD + stempel waktu (bila repo git tersedia)
 *   3. stempel waktu murni
 */
import { execSync } from 'node:child_process';
import { writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const sini = dirname(fileURLToPath(import.meta.url));
const buildDir = resolve(sini, '..', 'build');

function dariGit() {
	try {
		const sha = execSync('git rev-parse --short HEAD', {
			cwd: resolve(sini, '..'),
			stdio: ['ignore', 'pipe', 'ignore']
		})
			.toString()
			.trim();
		return sha || '';
	} catch {
		return '';
	}
}

const dariEnv = (process.env.WARROOM_BUILD_ID ?? '').trim();
const sha = dariGit();
const stempel = new Date().toISOString().replace(/[-:]/g, '').replace(/\..+/, 'Z');

const buildId = dariEnv || (sha ? `${sha}-${stempel}` : `local-${stempel}`);

// Tulis file yang dibaca skrip deploy.
writeFileSync(resolve(buildDir, 'build-id.txt'), `${buildId}\n`, 'utf8');

// Juga tulis nilai kecil untuk dibaca server runtime (adapter-node mengimpor modul JS).
writeFileSync(
	resolve(buildDir, 'build-id.js'),
	`// Dibuat otomatis oleh scripts/tulis-build-id.mjs — JANGAN diedit tangan.\nexport const BUILD_ID = ${JSON.stringify(buildId)};\n`,
	'utf8'
);

console.log(`build_id ditulis: ${buildId}`);
console.log(`  -> build/build-id.txt`);
console.log(`  -> build/build-id.js`);
