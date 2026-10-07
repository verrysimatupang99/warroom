import adapter from '@sveltejs/adapter-node';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	kit: {
		// adapter-node: satu proses Node di belakang Caddy (03-backend.md §2).
		adapter: adapter(),

		// CSP ENFORCE (audit QA putaran 2, 7 Okt). Sebelumnya kebijakan hanya
		// Report-Only di nginx — dan tanpa `report-uri` ia tidak pernah mengumpulkan
		// laporan, jadi "menunggu log bersih" tidak akan pernah selesai. SvelteKit
		// menghitung HASH untuk skrip bootstrap inline-nya sendiri (hash berubah tiap
		// build, jadi tidak bisa ditulis tangan di nginx) dan menyisipkan
		// <meta http-equiv="content-security-policy">. Meta itulah yang menegakkan.
		// `unsafe-inline` hanya untuk STYLE (Svelte memakai style inline di komponen);
		// script TIDAK diberi unsafe-inline.
		csp: {
			mode: 'hash',
			directives: {
				'default-src': ['self'],
				'script-src': ['self'],
				'style-src': ['self', 'unsafe-inline', 'https://fonts.googleapis.com'],
				'font-src': ['self', 'https://fonts.gstatic.com'],
				'img-src': ['self', 'data:'],
				'connect-src': ['self'],
				'object-src': ['none'],
				'base-uri': ['self'],
				'frame-ancestors': ['none'],
				'form-action': ['self']
			}
		}
	}
};

export default config;