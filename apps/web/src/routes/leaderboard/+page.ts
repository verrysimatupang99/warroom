import { redirect } from '@sveltejs/kit';

// Rute ini tidak pernah punya tautan masuk (0 href) dan isinya hanya placeholder
// 14 baris. Leaderboard yang sebenarnya dirender oleh /riset?sub=leaderboard,
// jadi rute berdiri sendiri ini dialihkan ke sana (25 Okt 2026).
export const load = () => {
	throw redirect(308, '/riset?sub=leaderboard');
};
