import { redirect } from '@sveltejs/kit';

// /agy ("AI Market Agent") hanya placeholder 14 baris dan tidak ada di AREAS
// (nav.ts), jadi tidak pernah muncul di menu. Dialihkan ke beranda supaya
// tautan lama tidak 404 (25 Okt 2026).
export const load = () => {
	throw redirect(308, '/');
};
