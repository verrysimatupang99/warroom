<script lang="ts">
	// Blok "batas jujur" per market. Ini bagian yang menjawab: apa yang bisa gagal
	// di sini, dan apa yang sengaja belum diukur. Ditulis dari keadaan sistem, bukan
	// dari harapan.
	interface Props {
		market: 'crypto' | 'forex';
	}
	let { market }: Props = $props();

	const BATAS = {
		crypto: [
			'Semua angka di halaman ini paper. Tidak ada order yang dikirim ke bursa.',
			'Entry dicatat di harga candle, bukan harga fill. Jadi tidak ada slippage dan tidak ada biaya taker yang terukur.',
			'Riwayat ekuitas baru direkam sejak 28 Okt 2026; sebelumnya hanya kondisi terakhir yang disimpan.',
			'Level SMC belum tersedia lokal. Yang tampil di tab Sinyal hanya level struktur dari candle.',
			'Universe dan harga dari OKX. Kalau OKX membatasi akses, angka berhenti diperbarui tanpa peringatan otomatis.'
		],
		forex: [
			'Telemetri bergantung pada runner Instabox (box-2aacb3). Kalau runner berhenti, angka forex berhenti diperbarui; situs tetap hidup dengan data terakhir.',
			'Sinyal dihitung dari telemetri MT5 + aturan EMA/RSI/ATR di EA GOLD_Reaper_Hexa (London 08–09 & NY 13:15–15:59 jam server). Laya AI sedang dinonaktifkan; "menunggu setup" berarti aturan belum terpenuhi.',
			'Akun utama kini berjalan di Exness Real Cent (#452009427, satuan USC = $0,01 USD) dengan jumlah sampel live yang masih bertumbuh.',
			'Spread XAUUSDc terukur sekitar 160–240 point ($0,16–$0,24) di kondisi normal. Saat rollover dan rilis berita, spread bisa melebar beberapa kali.',
			'War Room tidak mengirim order dari browser. Eksekusi dilakukan EA di terminal MT5 (Twin-Order Scalp +0.7R & Runner +2.0R), dan setiap deal dicatat di jurnal.'
		]
	} as const;

	const daftar = $derived(BATAS[market]);
</script>

<section class="rounded-card border border-line bg-surface p-4" aria-labelledby={`batas-${market}`}>
	<h2 id={`batas-${market}`} class="text-13 font-bold text-text">Batas jujur</h2>
	<ul class="mt-2 space-y-1.5">
		{#each daftar as b, i (i)}
			<li class="flex gap-2 text-11 leading-relaxed text-text-2">
				<span class="font-mono text-text-3">·</span>
				<span>{b}</span>
			</li>
		{/each}
	</ul>
</section>
