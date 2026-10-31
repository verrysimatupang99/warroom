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
			'Universe dan harga dari MEXC. Kalau MEXC membatasi akses, angka berhenti diperbarui tanpa peringatan otomatis.'
		],
		forex: [
			'Telemetri bergantung pada VM Azure. Kalau VM mati, angka forex berhenti diperbarui; situs tetap hidup dengan data terakhir.',
			'Sinyal berasal dari Laya Sentinel di server ini. Kalau daemon itu berhenti, status akan tetap "menunggu setup" dan bukan berarti pasar sepi.',
			'Baru ada 6 trade live di akun demo. Itu terlalu kecil untuk menyimpulkan win rate 66,7% sebagai edge.',
			'Spread yang terukur 240 point ($0,28) adalah kondisi sekarang. Saat rollover dan berita, spread bisa melebar beberapa kali.',
			'War Room tidak mengirim order sendiri. Eksekusi dilakukan EA di terminal MT5, dan selisih antara sinyal dan fill dicatat di jurnal.'
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
