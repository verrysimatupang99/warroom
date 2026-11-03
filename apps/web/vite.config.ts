import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig, loadEnv } from 'vite';

// Target API untuk proxy dev/preview. Default 127.0.0.1:8800 (API lokal / Caddy di
// produksi). E2E mengarahkannya ke API yang memakai DB tes lewat env
// WARROOM_API_TARGET, supaya suite tidak pernah membaca/menulis DB produksi.
//
// Catatan tipe: proyek ini sengaja tidak memasang @types/node, jadi `process`
// tidak boleh dipakai di sini (svelte-check akan gagal: "Cannot find name
// 'process'"). `loadEnv` cukup dipanggil dengan folder akar bawaan vite.
export default defineConfig(({ mode }) => {
	const env = loadEnv(mode, '.', 'WARROOM_');
	const apiTarget = env.WARROOM_API_TARGET || 'http://127.0.0.1:8800';

	return {
		plugins: [tailwindcss(), sveltekit()],
		server: {
			// Dev: teruskan ke API lokal supaya sesi cookie same-origin (tanpa CORS, EventSource
			// tetap membawa cookie). Di produksi Caddy yang mem-proxy /api ke 127.0.0.1:8800.
			proxy: {
				'/api': apiTarget,
				'/metrics': apiTarget
			}
		},
		preview: {
			// E2E memakai `vite preview` (tanpa Caddy): proxy yang sama supaya cookie same-origin.
			proxy: {
				'/api': apiTarget,
				'/metrics': apiTarget
			}
		}
	};
});
