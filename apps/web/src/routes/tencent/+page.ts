// Halaman debug sumber data dipindahkan ke Sistem > Data & Kesegaran (28 Okt 2026).
// Rute lama tetap hidup sebagai pengalihan supaya tautan dan penanda buku tidak mati.
import { redirect } from '@sveltejs/kit';

export function load() {
	redirect(308, '/sistem?sub=data');
}
