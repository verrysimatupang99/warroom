import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/svelte';
import { afterEach } from 'vitest';

// jsdom tidak menjalankan matchMedia; komponen yang menghormati prefers-reduced-motion
// membutuhkannya saat di-mount. Stub netral supaya uji tidak bergantung pada perilaku OS.
if (typeof window !== 'undefined' && !window.matchMedia) {
	window.matchMedia = ((query: string) => ({
		matches: false,
		media: query,
		onchange: null,
		addListener: () => {},
		removeListener: () => {},
		addEventListener: () => {},
		removeEventListener: () => {},
		dispatchEvent: () => false
	})) as unknown as typeof window.matchMedia;
}

afterEach(() => cleanup());