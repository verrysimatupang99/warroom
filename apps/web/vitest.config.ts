import { svelte } from '@sveltejs/vite-plugin-svelte';
import { defineConfig } from 'vitest/config';
import { fileURLToPath } from 'node:url';

// Konfigurasi uji terpisah dari vite.config.ts: komponen yang diuji tidak menyentuh modul
// SvelteKit ($app/$env), jadi cukup plugin svelte + kondisi 'browser' agar runtime klien
// Svelte 5 yang dipakai, bukan runtime server. Alias `$lib` disalin manual karena plugin
// SvelteKit (yang biasanya menyediakannya) tidak dipasang di sini.
export default defineConfig({
	plugins: [svelte({ hot: false })],
	resolve: {
		conditions: ['browser'],
		alias: {
			$lib: fileURLToPath(new URL('./src/lib', import.meta.url))
		}
	},
	test: {
		environment: 'jsdom',
		globals: true,
		include: ['src/**/*.test.ts'],
		setupFiles: ['./src/tests/setup.ts']
	}
});