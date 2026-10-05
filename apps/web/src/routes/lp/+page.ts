import { redirect } from '@sveltejs/kit';

// Rute lama ini DIHAPUS sebagai area pada perombakan 5 Okt 2026, tetapi tidak dimatikan:
// pengalihan menjaga penanda buku dan tautan lama tetap hidup. Alasan penggabungan:
// Area LP Pool digabung ke GMGN — sub LP sudah ada di sana.
export const load = () => {
	throw redirect(308, '/gmgn?sub=lp');
};
