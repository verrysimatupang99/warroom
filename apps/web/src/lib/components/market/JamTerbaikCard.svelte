<script lang="ts">
	// Analisis jam & hari terbaik trade forex. Sumber: `/api/v1/journal/best-hours`.
	// `iso` di backend = waktu TUTUP (UTC); menang/rugi dari pnl_usd karena pnl_pct
	// kosong untuk forex. Semua angka kosong dari API ditampilkan '—', bukan 0.
	import { onMount } from 'svelte';
	import { urlApi } from '$lib/api/client';
	import { angka, TAK_ADA } from '$lib/format';

	interface Keranjang {
		n: number;
		menang: number;
		rugi: number;
		seri: number;
		winrate_pct: number | null;
		pnl_usd_total: number | null;
	}
	interface BarisJam extends Keranjang {
		jam: number;
	}
	interface BarisHari extends Keranjang {
		hari: string;
		index: number;
	}
	interface BestHours {
		market: string;
		satuan: string;
		min_n: number;
		n_total: number;
		n_tanpa_waktu: number;
		n_tanpa_hasil: number;
		per_jam: BarisJam[];
		per_hari: BarisHari[];
		jam_terbaik: BarisJam | null;
		hari_terbaik: BarisHari | null;
		sumber?: string;
		catatan?: string;
	}

	let data = $state<BestHours | null>(null);
	let galat = $state<string | null>(null);
	let memuat = $state(true);

	onMount(async () => {
		try {
			const r = await fetch(urlApi('/api/v1/journal/best-hours?market=forex'), {
				credentials: 'include'
			});
			const isi = await r.json().catch(() => null);
			if (!r.ok) {
				const pesan = isi?.error?.message ?? isi?.detail?.message ?? isi?.detail;
				galat = typeof pesan === 'string' ? pesan : `HTTP ${r.status}`;
			} else {
				data = isi as BestHours;
			}
		} catch (e) {
			galat = e instanceof Error ? e.message : 'gagal menghubungi API';
		}
		memuat = false;
	});

	// Hanya jam yang punya trade; 24 baris kosong bukan informasi, cuma derau.
	const jamTerisi = $derived((data?.per_jam ?? []).filter((b) => b.n > 0));
	const hariTerisi = $derived((data?.per_hari ?? []).filter((b) => b.n > 0));

	function usd(v: number | null | undefined) {
		if (v == null) return TAK_ADA;
		const tanda = v < 0 ? '−' : '+';
		return `${tanda}$${angka(Math.abs(v))}`;
	}
	function wr(v: number | null | undefined) {
		return v == null ? TAK_ADA : `${angka(v, { desimal: 0 })}%`;
	}
	function wl(b: Keranjang) {
		return `${b.menang}/${b.rugi}${b.seri ? `/${b.seri}` : ''}`;
	}
	function labelJam(j: number) {
		return `${String(j).padStart(2, '0')}:00`;
	}
	function kelasPnl(v: number | null | undefined) {
		if (v == null || v === 0) return 'text-text-2';
		return v > 0 ? 'text-pos' : 'text-neg';
	}
</script>

<section class="rounded-card border border-line bg-surface p-4" data-testid="jam-terbaik">
	<div class="flex flex-wrap items-start justify-between gap-2">
		<div>
			<h2 class="text-13 font-bold text-text">Jam &amp; hari terbaik</h2>
			<p class="mt-0.5 text-11 text-text-3">
				XAUUSDc · trade forex tertutup, dikelompokkan menurut jam dan hari <span class="font-mono"
					>TUTUP</span
				> (UTC). Menang/rugi dari PnL USD, bukan persen.
			</p>
		</div>
		{#if data}
			<span class="font-mono text-10 text-text-3">{data.n_total} trade · min n {data.min_n}</span>
		{/if}
	</div>

	{#if memuat}
		<p class="mt-2 text-11 text-text-3">menghitung jam &amp; hari terbaik…</p>
	{:else if galat}
		<p class="mt-2 text-11 text-text-3">Analisis jam tidak terbaca: {galat}</p>
	{:else if !data || data.n_total === 0}
		<p class="mt-2 text-11 text-text-3">
			Belum ada trade forex tertutup. Analisis baru bermakna setelah EA menutup beberapa deal.
		</p>
	{:else}
		<div class="mt-3 grid gap-2 sm:grid-cols-2">
			<div
				class="rounded-card border p-2.5 {data.jam_terbaik
					? 'border-warn bg-warn/10'
					: 'border-line'}"
			>
				<p class="text-10 uppercase tracking-wide text-text-3">Jam terbaik</p>
				{#if data.jam_terbaik}
					<p class="mt-0.5 font-mono text-14 font-bold text-text">
						{labelJam(data.jam_terbaik.jam)}–{labelJam((data.jam_terbaik.jam + 1) % 24)}
						<span class="text-warn">UTC</span>
					</p>
					<p class="mt-0.5 text-11 text-text-3">
						{usd(data.jam_terbaik.pnl_usd_total)} dari {data.jam_terbaik.n} trade · win-rate {wr(
							data.jam_terbaik.winrate_pct
						)}
					</p>
				{:else}
					<p class="mt-0.5 text-11 text-text-3">
						Belum ada jam dengan minimal {data.min_n} trade tertutup.
					</p>
				{/if}
			</div>
			<div
				class="rounded-card border p-2.5 {data.hari_terbaik
					? 'border-warn bg-warn/10'
					: 'border-line'}"
			>
				<p class="text-10 uppercase tracking-wide text-text-3">Hari terbaik</p>
				{#if data.hari_terbaik}
					<p class="mt-0.5 font-mono text-14 font-bold text-text">{data.hari_terbaik.hari}</p>
					<p class="mt-0.5 text-11 text-text-3">
						{usd(data.hari_terbaik.pnl_usd_total)} dari {data.hari_terbaik.n} trade · win-rate {wr(
							data.hari_terbaik.winrate_pct
						)}
					</p>
				{:else}
					<p class="mt-0.5 text-11 text-text-3">
						Belum ada hari dengan minimal {data.min_n} trade tertutup.
					</p>
				{/if}
			</div>
		</div>

		<div class="mt-3 grid gap-4 lg:grid-cols-2">
			<div>
				<h3 class="text-12 font-bold text-text">Per jam (UTC)</h3>
				{#if jamTerisi.length === 0}
					<p class="mt-1 text-11 text-text-3">Tidak ada jam yang bisa dihitung.</p>
				{:else}
					<div class="mt-1.5 overflow-x-auto">
						<table class="w-full text-11 text-left">
							<thead class="border-b border-line text-10 text-text-3">
								<tr>
									<th class="px-1.5 py-1">Jam</th>
									<th class="px-1.5 py-1 text-right">n</th>
									<th class="px-1.5 py-1 text-right">M/K</th>
									<th class="px-1.5 py-1">Win-rate</th>
									<th class="px-1.5 py-1 text-right">PnL</th>
								</tr>
							</thead>
							<tbody class="divide-y divide-line-soft">
								{#each jamTerisi as b (b.jam)}
									{@const utama = data.jam_terbaik?.jam === b.jam}
									<tr class:bg-surface-2={utama}>
										<td class="px-1.5 py-1 font-mono" class:text-warn={utama} class:text-text={!utama}>
											{labelJam(b.jam)}
										</td>
										<td class="px-1.5 py-1 text-right font-mono text-text-2">{b.n}</td>
										<td class="px-1.5 py-1 text-right font-mono text-text-3">{wl(b)}</td>
										<td class="px-1.5 py-1">
											<div class="flex items-center gap-1.5">
												<div class="h-1.5 w-16 overflow-hidden rounded-full bg-surface-2">
													<div
														class="h-full rounded-full"
														class:bg-pos={b.winrate_pct != null && b.winrate_pct >= 50}
														class:bg-neg={b.winrate_pct != null && b.winrate_pct < 50}
														style:width="{(b.winrate_pct ?? 0).toFixed(0)}%"
													></div>
												</div>
												<span class="font-mono text-10 text-text-2">{wr(b.winrate_pct)}</span>
											</div>
										</td>
										<td class="px-1.5 py-1 text-right font-mono {kelasPnl(b.pnl_usd_total)}">
											{usd(b.pnl_usd_total)}
										</td>
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				{/if}
			</div>

			<div>
				<h3 class="text-12 font-bold text-text">Per hari</h3>
				{#if hariTerisi.length === 0}
					<p class="mt-1 text-11 text-text-3">Tidak ada hari yang bisa dihitung.</p>
				{:else}
					<div class="mt-1.5 space-y-1">
						{#each data.per_hari as b (b.index)}
							{@const utama = data.hari_terbaik?.index === b.index}
							<div
								class="flex items-center gap-2 rounded border border-line px-2 py-1 text-11"
								class:border-warn={utama}
								class:bg-surface-2={utama}
							>
								<span class="w-14 font-mono" class:text-warn={utama} class:text-text={!utama}
									>{b.hari}</span
								>
								<div class="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-2">
									<div
										class="h-full rounded-full"
										class:bg-pos={b.winrate_pct != null && b.winrate_pct >= 50}
										class:bg-neg={b.winrate_pct != null && b.winrate_pct < 50}
										style:width="{(b.winrate_pct ?? 0).toFixed(0)}%"
									></div>
								</div>
								<span class="w-10 text-right font-mono text-10 text-text-3">
									{b.n > 0 ? `${b.n}×` : TAK_ADA}
								</span>
								<span class="w-14 text-right font-mono text-10 text-text-3">{wr(b.winrate_pct)}</span>
								<span class="w-20 text-right font-mono {kelasPnl(b.pnl_usd_total)}">
									{b.n > 0 ? usd(b.pnl_usd_total) : TAK_ADA}
								</span>
							</div>
						{/each}
					</div>
				{/if}
			</div>
		</div>

		{#if data.catatan}
			<p class="mt-3 border-t border-line pt-2 text-10 text-text-3">
				{data.catatan}{#if data.sumber}
					· sumber: {data.sumber}{/if}
			</p>
		{/if}
	{/if}
</section>
