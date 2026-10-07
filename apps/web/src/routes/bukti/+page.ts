import { redirect } from '@sveltejs/kit';

// Rute lama ini DIHAPUS sebagai area pada perombakan 5 Okt 2026, tetapi tidak dimatikan:
// pengalihan menjaga penanda buku dan tautan lama tetap hidup. Alasan penggabungan:
// Sejak 7 Okt: /bukti = halaman Kinerja & Bukti (performance & proof) di Riset.
// Kesegaran & audit tetap di Sistem.
export const load = () => {
	throw redirect(308, '/riset?sub=bukti');
};
