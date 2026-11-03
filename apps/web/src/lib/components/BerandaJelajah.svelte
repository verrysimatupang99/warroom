<script lang="ts">
	// Blok Beranda yang mengikuti urutan algentis.xyz: satu kalimat posisi, hub
	// "Jelajahi" menuju tiap area, batas jujur, dan disclosure risiko.
	// Tidak ada angka karangan di sini: yang ditulis hanya hal yang bisa diperiksa.
	import { AREAS } from '$lib/nav';

	const AREA_JELAJAH = AREAS.filter((a) => a.rute !== '/');

	const BATAS = [
		'Sinyal bisa salah. Angka backtest tidak menjamin hasil berikutnya.',
		'Sumber data pihak ketiga bisa berhenti kapan saja: OKX, Yahoo, TradingView, Stockbit.',
		'Telemetri MT5 bergantung pada VM Azure. Kalau VM mati, angka forex berhenti diperbarui.',
		'Jurnal crypto hanya mencatat harga candle, bukan fill bursa, jadi tidak mengukur slippage.',
		'Level SMC asli belum tersedia; yang ada hanya level struktur yang dihitung ulang dari candle.'
	];
</script>

<section class="rounded-card border border-line bg-surface p-4">
	<p class="text-14 font-medium leading-relaxed text-text sm:text-15">
		War Room memutuskan apakah ada yang layak dieksekusi, lalu menyiapkan keputusan itu lewat
		paper sebelum uang nyata. <span class="text-text-3">Kalau tidak ada yang lolos, ia diam.</span>
	</p>
</section>

<section aria-labelledby="judul-jelajah">
	<h2 id="judul-jelajah" class="label-mikro font-mono text-text-3">JELAJAHI</h2>
	<div class="mt-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
		{#each AREA_JELAJAH as a (a.kunci)}
			<a
				href={a.rute}
				class="group rounded-card border border-line bg-surface p-3 transition-colors hover:border-accent"
			>
				<div class="flex items-center justify-between gap-2">
					<span class="text-13 font-bold text-text group-hover:text-accent">{a.label}</span>
					{#if a.status}
						<span class="rounded border border-line px-1.5 py-0.5 font-mono text-10 text-text-3">
							{a.status}
						</span>
					{/if}
				</div>
				<p class="mt-1 text-11 leading-relaxed text-text-3">
					{#if a.anak.length > 0}
						{a.anak.length} tab: {a.anak.map((x) => x.label).join(' · ')}
					{:else if a.kunci === 'jurnal'}
						Riwayat eksekusi lintas market dengan filter
					{:else if a.kunci === 'info'}
						Catatan, berita, cara kerja, dan bantuan
					{:else}
						{a.label}
					{/if}
				</p>
			</a>
		{/each}
	</div>
</section>

<section class="rounded-card border border-line bg-surface p-4" aria-labelledby="judul-batas">
	<h2 id="judul-batas" class="text-13 font-bold text-text">Batas jujur</h2>
	<ul class="mt-2 space-y-1.5">
		{#each BATAS as b, i (i)}
			<li class="flex gap-2 text-11 leading-relaxed text-text-2">
				<span class="font-mono text-text-3">·</span>
				<span>{b}</span>
			</li>
		{/each}
	</ul>
</section>

<p class="text-11 leading-relaxed text-text-3">
	Disclosure risiko: trading derivatif dengan leverage membawa risiko kehilangan modal.
	War Room adalah alat analisis, bukan nasihat keuangan. Kinerja masa lalu tidak menjamin
	hasil berikutnya. Semua keputusan dan eksekusi sepenuhnya tanggung jawab pemilik akun.
</p>
