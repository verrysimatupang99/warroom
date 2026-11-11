<script lang="ts">
	// Hasil perbandingan EA yang diukur sendiri pada 29 Okt 2026, ditampilkan di dalam
	// produk supaya keputusan tidak hanya hidup di dokumen vault.
	// Semua baris berasal dari laporan backtest periode sama: 2023.10.27 - 2026.10.27,
	// XAUUSDm M5, deposit $10.000, Model 2 (M1 OHLC).
	interface Baris {
		nama: string;
		jenis: string;
		pf: string;
		trade: string;
		dd: string;
		catatan: string;
		nada: 'baik' | 'sedang' | 'hati-hati';
	}

	const BARIS: Baris[] = [
		{ nama: 'Galaxius (vendor, trial)', jenis: 'Scalper TP lebar, menang 38%', pf: '2,73', trade: '3.685', dd: '1,61 %', nada: 'hati-hati',
			catatan: 'Tahan biaya: slippage 2,02/fill baru membuatnya rugi. Rapuh karena bergantung pada 4,4R yang jarang.' },
		{ nama: 'GoldenBall (vendor, trial)', jenis: 'Swing harian, menang 79%', pf: '2,46', trade: '684', dd: '3,05 %', nada: 'sedang',
			catatan: 'Rasio 0,66 (menang 11,70, kalah 17,66). Lebih tahan sideways, lebih sakit saat salah arah. Kandidat pilot paper.' },
		{ nama: 'GOLD Reaper tp30', jenis: 'Milik sendiri', pf: '1,09', trade: '957', dd: '13,90 %', nada: 'sedang',
			catatan: 'Edge tipis, drawdown besar. Jujur tapi belum layak uang nyata.' },
		{ nama: 'GOLD Reaper H08', jenis: 'Milik sendiri, lot 0,15', pf: '1,07', trade: '1.017', dd: '9,71 %', nada: 'hati-hati',
			catatan: 'Setelah slippage dan komisi PF tinggal 1,01 (net $345). Varian 3 tahun lain negatif, PF 0,91.' },
		{ nama: 'WarRoom AutoTrader', jenis: 'Konektor eksekusi', pf: '—', trade: '6 live', dd: '−8,6 %', nada: 'baik',
			catatan: 'Bukan strategi. Ekuitas demo 456,98 dari 500. Satu-satunya yang tersambung ke API dan jurnal.' }
	];

	const WARNA: Record<Baris['nada'], string> = {
		baik: 'text-pos',
		sedang: 'text-text',
		'hati-hati': 'text-neg'
	};
</script>

<section class="rounded-card border border-line bg-surface p-4">
	<div class="flex flex-wrap items-center justify-between gap-2">
		<h2 class="text-13 font-bold text-text">Perbandingan EA, 3 tahun periode sama</h2>
		<span class="font-mono text-11 text-text-3">diukur 29 Okt 2026</span>
	</div>

	<div class="mt-2 overflow-x-auto">
		<table class="w-full text-11 text-left">
			<thead class="border-b border-line text-10 text-text-3">
				<tr>
					<th class="px-2 py-1.5">EA</th>
					<th class="px-2 py-1.5">Jenis</th>
					<th class="px-2 py-1.5 text-right">PF</th>
					<th class="px-2 py-1.5 text-right">Trade</th>
					<th class="px-2 py-1.5 text-right">DD</th>
					<th class="px-2 py-1.5">Catatan</th>
				</tr>
			</thead>
			<tbody class="divide-y divide-line-soft">
				{#each BARIS as b (b.nama)}
					<tr class="hover:bg-surface-2/60">
						<td class="px-2 py-1.5 text-text">{b.nama}</td>
						<td class="px-2 py-1.5 text-text-3">{b.jenis}</td>
						<td class="px-2 py-1.5 text-right font-mono {WARNA[b.nada]}">{b.pf}</td>
						<td class="px-2 py-1.5 text-right font-mono text-text-2">{b.trade}</td>
						<td class="px-2 py-1.5 text-right font-mono text-text-2">{b.dd}</td>
						<td class="px-2 py-1.5 text-text-3">{b.catatan}</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>

	<div class="mt-3 rounded border border-line bg-surface-2 p-3">
		<p class="text-12 font-bold text-text">Uji biaya: 3.685 deal dibaca ulang dari laporan</p>
		<div class="mt-2 overflow-x-auto">
			<table class="w-full text-11 text-left">
				<thead class="text-10 text-text-3">
					<tr>
						<th class="px-2 py-1">Skenario</th>
						<th class="px-2 py-1 text-right">Galaxius</th>
						<th class="px-2 py-1 text-right">GoldenBall</th>
						<th class="px-2 py-1 text-right">Reaper H08</th>
					</tr>
				</thead>
				<tbody class="text-text-2">
					<tr><td class="px-2 py-1">apa adanya</td><td class="px-2 py-1 text-right font-mono">2,74</td><td class="px-2 py-1 text-right font-mono">2,50</td><td class="px-2 py-1 text-right font-mono">1,07</td></tr>
					<tr><td class="px-2 py-1">slippage 0,05/fill</td><td class="px-2 py-1 text-right font-mono">2,65</td><td class="px-2 py-1 text-right font-mono">2,49</td><td class="px-2 py-1 text-right font-mono">1,04</td></tr>
					<tr><td class="px-2 py-1">komisi 7 dolar/lot</td><td class="px-2 py-1 text-right font-mono">2,67</td><td class="px-2 py-1 text-right font-mono">2,49</td><td class="px-2 py-1 text-right font-mono">1,05</td></tr>
					<tr><td class="px-2 py-1">keduanya</td><td class="px-2 py-1 text-right font-mono">2,59</td><td class="px-2 py-1 text-right font-mono">2,47</td><td class="px-2 py-1 text-right font-mono">1,01</td></tr>
				</tbody>
			</table>
		</div>
		<p class="mt-2 text-11 leading-relaxed text-text-3">
			Titik putus: Galaxius baru rugi pada slippage 2,02 harga per fill, GoldenBall 5,56,
			<strong class="text-text-2">GOLD Reaper hanya 0,11</strong>. Spread terukur 0,24, dua kali
			titik putus Reaper. Jadi yang paling rentan terhadap biaya adalah EA sendiri, bukan EA vendor.
			Pengukuran 3.685/684/1.017 deal dari laporan apa adanya.
		</p>
	</div>

	<div class="mt-3 rounded border border-line bg-surface-2 p-3">
		<p class="text-12 font-bold text-text">Keputusan</p>
		<p class="mt-1 text-11 leading-relaxed text-text-2">
			Yang dipakai sebagai lapisan eksekusi tetap <strong class="text-text">WarRoom AutoTrader</strong>,
			karena hanya itu yang tersambung ke API, telemetri, dan jurnal. Kandidat pilot paper adalah
			<strong class="text-text">GoldenBall</strong>. <strong class="text-text">Galaxius</strong> tidak
			diajukan untuk uang nyata, bukan karena biaya, tetapi karena lisensi trial, menang hanya 38%
			sehingga butuh ratusan trade untuk terlihat, dan pengujiannya hanya satu rezim pasar.
		</p>
		<p class="mt-2 text-11 leading-relaxed text-text-3">
			Batas pengujian: Model 2 (M1 OHLC), bukan real tick. Kedua EA vendor masih trial dan tidak punya
			rekam jejak live. Satu rezim pasar (tren emas kuat 2023 sampai 2026). Jangan menaikkan modal
			berdasarkan tabel ini.
		</p>
	</div>
</section>
