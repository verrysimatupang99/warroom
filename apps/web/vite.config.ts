import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [tailwindcss(), sveltekit()],
	server: {
		// Dev: teruskan ke API lokal supaya sesi cookie same-origin (tanpa CORS, EventSource
		// tetap membawa cookie). Di produksi Caddy yang mem-proxy /api ke 127.0.0.1:8800.
		proxy: {
			'/api': 'http://127.0.0.1:8800',
			'/metrics': 'http://127.0.0.1:8800'
		}
	}
});