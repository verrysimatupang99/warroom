import { redirect } from '@sveltejs/kit';

// Rute lama ini DIHAPUS sebagai area pada perombakan 5 Okt 2026, tetapi tidak dimatikan:
// pengalihan menjaga penanda buku dan tautan lama tetap hidup. Alasan penggabungan:
// Area Overextended digabung ke Crypto — datanya dari snapshot crypto.
export const load = () => {
	throw redirect(308, '/crypto?sub=overextended');
};
