<script lang="ts">
	// RiskMeter: Pengawas batas risiko real-time & kapasitas trading.
	// Operator dapat langsung tahu: seberapa aman alokasi risiko hari ini.
	import { angka, persenRisikoTerpakai, statusRisikoDari } from '$lib/format';

	interface RisikoData {
		mode?: string;
		hari_ini_r?: number;
		batas_rugi_r?: number;
		sisa_ruang_r?: number;
		maks_posisi?: number;
		posisi_terbuka?: number;
		risiko_per_trade_pct?: number;
		total_trade?: number;
		kunci_executor?: {
			held?: boolean;
			host?: string | null;
			age_s?: number | null;
		};
	}

	interface Props {
		risiko?: RisikoData | null;
	}

	let { risiko = null }: Props = $props();

	const batasR = $derived(risiko?.batas_rugi_r ?? 3.0);
	const hariIniR = $derived(risiko?.hari_ini_r ?? 0.0);
	const sisaR = $derived(risiko?.sisa_ruang_r ?? (batasR - hariIniR));
	const maksPosisi = $derived(risiko?.maks_posisi ?? 3);
	const posisiTerbuka = $derived(risiko?.posisi_terbuka ?? 0);

	// Kuota risiko harian = HANYA kerugian yang menghabiskannya (perbaikan 7 Okt).
	// Versi lama memakai Math.abs sehingga hari PROFIT tampil sebagai "limit tercapai".
	const pctTerpakai = $derived(persenRisikoTerpakai(hariIniR, batasR));
	const rugiHariIni = $derived(Math.max(0, -hariIniR));
	const profitHariIni = $derived(Math.max(0, hariIniR));

	// Status dari helper bersama — ambang identik dengan badge di Home (temuan 5 Okt 2026).
	const statusRisiko = $derived(statusRisikoDari(hariIniR, batasR));
</script>

<div class="permukaan-2 rounded-card border border-line p-3">
	<div class="mb-3 flex items-center justify-between border-b border-line-soft pb-2">
		<div class="flex items-center gap-2">
			<h3 class="text-13 font-medium text-text">Batas Risiko & Kapasitas</h3>
			<span class="rounded px-1.5 py-0.5 text-10 font-bold uppercase tracking-wider border {statusRisiko.kelas}">
				{statusRisiko.label}
			</span>
		</div>
		<span class="rounded bg-surface px-2 py-0.5 text-11 uppercase font-mono text-paper border border-line">
			Mode: {risiko?.mode ?? 'Paper'}
		</span>
	</div>

	<div class="space-y-3">
		<!-- Progress Bar Risiko Harian -->
		<div>
			<div class="flex items-center justify-between text-11 mb-1">
				<span class="text-text-3">Risiko Terpakai Hari Ini</span>
				<span class="angka text-text-2 font-medium">
					{angka(rugiHariIni)} R / <span class="text-text-3">{angka(batasR)} R Max</span>
				</span>
			</div>
			<div class="h-2 w-full rounded-full bg-surface overflow-hidden border border-line-soft">
				<div
					class="h-full rounded-full transition-all duration-500 {pctTerpakai >= 80 ? 'bg-neg' : pctTerpakai >= 50 ? 'bg-warn' : 'bg-pos'}"
					style={`width: ${Math.max(4, pctTerpakai)}%`}
				></div>
			</div>
			{#if profitHariIni > 0}
				<!-- Hari yang PROFIT tidak memakai kuota batas rugi. Dulu angkanya ditampilkan
				     sebagai "risiko terpakai 4R / 3R" — pembaca menyimpulkan pelanggaran. -->
				<div class="mt-0.5 text-10 text-pos">
					+{angka(profitHariIni)} R profit hari ini — tidak memakai kuota batas rugi
				</div>
			{/if}
			<div class="mt-1 flex justify-between text-10 text-text-3">
				<!-- Temuan QA 15 Okt (Medium): sisa > batas membingungkan. Rumus domain
				     (risk.py): sisa ruang rugi = batas harian + hasil hari ini → saat profit,
				     ruang rugi melebar di atas batas (tetap jujur, diberi rumus). -->
				<span>
					Sisa toleransi: <b class="angka text-text">{angka(sisaR)} R</b>
					{#if profitHariIni > 0}
						<span title={`batas ${angka(batasR)} R + profit ${angka(profitHariIni)} R hari ini`}>(batas + profit)</span>
					{/if}
				</span>
				<span>{angka(pctTerpakai)}% kuota</span>
			</div>
		</div>

		<!-- Grid Kapasitas Posisi -->
		<div class="grid grid-cols-2 gap-2 pt-1 border-t border-line-soft text-12">
			<div class="rounded border border-line bg-surface p-2">
				<span class="text-10 uppercase text-text-3 block">Slot Posisi</span>
				<div class="mt-0.5 flex items-baseline gap-1">
					<span class="angka text-15 font-bold text-text">{posisiTerbuka}</span>
					<span class="text-11 text-text-3">/ {maksPosisi} maks</span>
				</div>
			</div>

			<div class="rounded border border-line bg-surface p-2">
				<span class="text-10 uppercase text-text-3 block">Risiko Akun / Trade</span>
				<div class="mt-0.5 flex items-baseline gap-1">
					<span class="angka text-15 font-bold text-text">
						{risiko?.risiko_per_trade_pct != null ? `${risiko.risiko_per_trade_pct}%` : '1,0%'}
					</span>
					<span class="text-10 text-text-3 font-mono">1.0 R</span>
				</div>
				<!-- QA 7 Okt (P0): dulu label ini "Risiko / Trade" dan di kartu kandidat tertulis
				     "risiko 3,813%" (itu JARAK STOP). Pembaca wajar menyimpulkan policy dilanggar.
				     Sekarang dua istilahnya dipisah tegas: di sini RISIKO AKUN (1% ekuitas, yang
				     benar-benar dipertaruhkan); di kandidat tertulis JARAK STOP. Ukuran posisi
				     dihitung agar risiko akun tetap 1% — bukan nominal tetap. -->
				<div class="mt-0.5 text-10 text-text-3">ukuran posisi = 1% ÷ jarak stop</div>
			</div>
		</div>
	</div>
</div>
