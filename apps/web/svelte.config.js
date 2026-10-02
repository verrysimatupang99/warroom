import adapter from '@sveltejs/adapter-node';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	kit: {
		// adapter-node: satu proses Node di belakang Caddy (03-backend.md §2).
		adapter: adapter()
	}
};

export default config;