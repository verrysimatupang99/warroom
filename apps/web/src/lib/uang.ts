/**
 * Tipe bersama untuk MoneyStrip. Diletakkan di modul .ts (bukan di dalam komponen) supaya bisa
 * diimpor lintas komponen tanpa mengekspor dari `<script>` komponen.
 */
export interface SegmenUang {
	nilai: number | null;
	satuan?: string | null;
	sumber?: string | null;
	age_s?: number | null;
	status?: string | null;
	keterangan?: string | null;
}