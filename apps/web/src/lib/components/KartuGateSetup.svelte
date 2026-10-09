<script lang="ts">
	/**
	 * KartuGateSetup — "Gate live-trading, centang otomatis" per setup.
	 *
	 * Bentuk ini DITIRU dari desk IDX Tencent (`/idx616/`: "Gate live-trading — centang
	 * otomatis", `LAYAK LIVE` / `UNPROVEN — paper dulu`) dan DISESUAIKAN dengan aturan War
	 * Room: angka tidak pernah dihitung di sini — semuanya datang apa adanya dari fakta
	 * `idx_akurasi` (per_setup). Komponen ini hanya MENYUSUN centang dari angka yang sudah ada.
	 *
	 * Aturan yang tidak diubah: ambang pakem & gate tetap milik owner (n≥30, ci=0.90, rumus BE).
	 * Yang diperiksa di sini adalah kelayakan SAMPAI BISA DINILAI, bukan promosi live.
	 */
	interface Seri {
		setup?: string | null;
		n?: number | null;
		n_hari?: number | null;
		winrate_pct?: number | null;
		mean_r?: number | null;
		total_r?: number | null;
		pakem?: string | null;
		tingkat?: string | null;
		ci_winrate?: number[] | null;
		profit_factor?: number | null;
		max_drawdown_r?: number | null;
		alasan?: string[] | null;
		dikarantina?: boolean;
		alasan_karantina?: string | null;
	}

	interface Props {
		blok: {
			per_setup?: Record<string, Seri>;
			tuntas?: number | null;
			belum_tuntas?: number | null;
			sumber?: string | null;
		} | null;
		judul?: string;
	}

	let { blok, judul = 'Gate live-trading — centang otomatis' }: Props = $props();

	/** Ambang "sampai bisa dinilai" — SAMA dengan pakem bukti backend (gate.py):
	 *  INSUFFICIENT <10 · DIRECTIONAL 10–29 · PRELIMINARY ≥30 · TUNING ≥100 (pada n hari efektif).
	 *  Nama pakem dibaca dari fakta; komponen ini memakai angka harinya hanya untuk centang. */
	const MIN_TUNTAS = 30; // n trade tuntas — ambang gate owner (n≥30), bukan ambang baru
	const MIN_HARI = 10; // hari efektif minimum sebelum sebuah setup boleh dinilai serius

	const baris = $derived(
		Object.entries(blok?.per_setup ?? {}).map(([kunci, s]) => {
			const tingkat = String(s.pakem ?? s.tingkat ?? '').toUpperCase();

			// Centang = pertanyaan "apakah setup ini sudah bisa dinilai?" — bukan "apakah profit?".
			const cek = [
				{
					k: 'Sampel tuntas (n≥30)',
					v: `${s.n ?? 0} tuntas`,
					ok: (s.n ?? 0) >= MIN_TUNTAS
				},
				{
					k: `Hari efektif (≥${MIN_HARI})`,
					v: `${s.n_hari ?? 0} hari`,
					ok: (s.n_hari ?? 0) >= MIN_HARI
				},
				{
					k: 'Pakem sampel ≥ PEMILIHAN',
					v: tingkat || '—',
					// Hanya PRELIMINARY/TUNING yang lolos "cukup untuk dinilai"; sisanya kurang sampel.
					ok: tingkat === 'PRELIMINARY' || tingkat === 'TUNING'
				},
				{
					k: 'Ekspektasi bersih > 0',
					v: s.mean_r == null ? '—' : `${s.mean_r > 0 ? '+' : ''}${s.mean_r} R`,
					ok: (s.mean_r ?? 0) > 0
				}
			];

			const semua = cek.every((c) => c.ok);
			return { kunci, s, tingkat, cek, semua };
		})
	);

	const jumlahLayak = $derived(baris.filter((b) => b.semua).length);
</script>

<div class="permukaan-2 rounded-card border border-line p-3">
	<div class="mb-3 flex flex-wrap items-center justify-between gap-2 border-b border-line-soft pb-2">
		<div>
			<h3 class="text-14 font-medium text-text">{judul}</h3>
			<p class="text-11 text-text-3">
				Empat syarat dinilai otomatis dari fakta <span class="font-mono">idx_akurasi</span> —
				semua harus ✓ sebelum sebuah aturan boleh disebut "layak dijalankan serius".
				<span class="text-warn">Ini bukan izin live</span>; promosi live tetap NO-GO sampai owner memutuskan.
			</p>
		</div>
		<span class="rounded bg-surface px-2 py-0.5 text-11 font-mono border border-line {jumlahLayak > 0 ? 'text-pos' : 'text-text-3'}">
			{jumlahLayak}/{baris.length} layak
		</span>
	</div>

	{#if !baris.length}
		<div class="py-4 text-center text-12 text-text-3">Tidak ada setup di ledger akurasi.</div>
	{:else}
		<div class="grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
			{#each baris as b (b.kunci)}
				<div class="rounded-card border {b.semua ? 'border-pos/40 bg-pos/5' : 'border-line bg-surface'} p-2.5">
					<div class="mb-2 flex flex-wrap items-center justify-between gap-1.5">
						<h4 class="text-12 font-bold text-text">
							{b.s.setup ?? b.kunci}
							{#if b.s.dikarantina}
								<span
									class="ml-1 rounded border border-neg/40 bg-neg/10 px-1.5 py-0.5 text-10 font-bold text-neg align-middle whitespace-nowrap"
									title={b.s.alasan_karantina ?? 'Rugi dalam data uji — diarsipkan dari wajah pasar, tetap ditampilkan untuk audit'}
								>DIARSIPKAN</span>
							{/if}
						</h4>
						<span
							class="rounded border px-1.5 py-0.5 text-10 font-bold {b.semua
								? 'border-pos/40 bg-pos/10 text-pos'
								: 'border-neg/40 bg-neg/10 text-neg'}"
						>
							{b.semua ? 'LAYAK DINILAI' : 'BELUM CUKUP — kumpulkan sampel'}
						</span>
					</div>

					<div class="space-y-1">
						{#each b.cek as c}
							<div class="flex items-center justify-between gap-2 text-11">
								<span class="text-text-2">{c.k}</span>
								<span class="angka whitespace-nowrap {c.ok ? 'text-pos' : 'text-neg'}">
									{c.ok ? '✓' : '✗'} {c.v}
								</span>
							</div>
						{/each}
					</div>

					{#if b.s.alasan?.length}
						<ul class="mt-2 space-y-0.5 border-t border-line-soft pt-1.5">
							{#each b.s.alasan as a}
								<li class="text-10 text-text-3">· {a}</li>
							{/each}
						</ul>
					{/if}
				</div>
			{/each}
		</div>

		<p class="mt-2 text-10 text-text-3">
			<b>Populasi:</b> kolom <span class="font-mono">n</span> = trade TUNTAS di ledger
			{blok?.tuntas != null ? `(${blok.tuntas} tuntas · ${blok.belum_tuntas ?? 0} jalan)` : ''}.
			Ambang (n≥30, hari≥10, pakem ≥ PRELIMINARY) adalah aturan bukti yang sudah ada —
			bukan ambang baru yang dihitung komponen ini.
		</p>
		{#if blok?.sumber}
			<p class="mt-1 truncate font-mono text-10 text-text-3">Sumber: {blok.sumber}</p>
		{/if}
	{/if}
</div>
