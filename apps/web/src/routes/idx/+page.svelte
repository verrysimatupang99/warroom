<script lang="ts">
	// IDX dengan sumber idx-edge (stock.arjum.com). Halaman ini menampilkan tiga hal
	// yang benar-benar tersedia: IHSG publik, ringkasan pasar (penggerak + blue chip),
	// dan pencarian saham. Yang belum ada tetap dinyatakan, bukan disembunyikan.
	import { onMount } from 'svelte';
	import { AREAS } from '$lib/nav';
	import { urlApi } from '$lib/api/client';
	import MarketShell from '$lib/components/MarketShell.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import Skeleton from '$lib/components/Skeleton.svelte';
	import RunningTrade from '$lib/components/market/RunningTrade.svelte';

	interface Candle { t: number; o: number; h: number; l: number; c: number; v: number }
	interface Pasar {
		symbol?: string; last?: number; open?: number; high?: number; low?: number;
		change_pct?: number; volume?: number; sumber?: string; candles?: Candle[];
	}
	interface Emiten {
		code?: string; last_price?: number; change?: number; change_pct?: number;
		freq?: number; lot?: number; value?: number; vwap?: number;
		data_ts?: string; market_label?: string; quote_age_ms?: number;
	}
	interface Ringkas {
		penggerak?: { gainers?: Emiten[]; losers?: Emiten[] };
		pemakaian?: { panggilan_hari_ini?: number; anggaran_harian?: number; sisa_perkiraan?: number };
		blue_chip?: { stocks?: Record<string, Emiten>; count?: number };
		sumber?: string; diambil?: string;
	}

	let d = $state<Pasar | null>(null);
	let ringkas = $state<Ringkas | null>(null);
	let galat = $state<string | null>(null);
	let galatRingkas = $state<string | null>(null);
	let memuat = $state(true);

	let kueri = $state('');
	let hasilCari = $state<{ stock_code?: string; stock_name?: string }[]>([]);
	let detail = $state<Emiten | null>(null);
	let memuatCari = $state(false);

	const area = AREAS.find((a) => a.kunci === 'idx')!;

	onMount(async () => {
		const [p, r] = await Promise.allSettled([
			fetch(urlApi('/api/v1/idx/market'), { credentials: 'include' }),
			fetch(urlApi('/api/v1/idx-edge/ringkas'), { credentials: 'include' })
		]);
		if (p.status === 'fulfilled' && p.value.ok) d = await p.value.json();
		else galat = 'Sumber IHSG tidak mengembalikan data.';
		if (r.status === 'fulfilled' && r.value.ok) {
			const isi = await r.value.json();
			ringkas = isi?.hasil ?? null;
		} else if (r.status === 'fulfilled') {
			const isi = await r.value.json().catch(() => null);
			galatRingkas = isi?.error?.message ?? `HTTP ${r.value.status}`;
		} else {
			galatRingkas = 'Tidak bisa menghubungi API.';
		}
		memuat = false;
	});

	async function cari() {
		const q = kueri.trim();
		if (q.length < 2) return;
		memuatCari = true;
		detail = null;
		try {
			const r = await fetch(urlApi(`/api/v1/idx-edge/cari?q=${encodeURIComponent(q)}`), {
				credentials: 'include'
			});
			const isi = await r.json().catch(() => null);
			hasilCari = r.ok ? (isi?.hasil ?? []) : [];
		} catch {
			hasilCari = [];
		}
		memuatCari = false;
	}

	async function buka(kode?: string) {
		if (!kode) return;
		try {
			const r = await fetch(urlApi(`/api/v1/idx-edge/harga/${kode}`), { credentials: 'include' });
			const isi = await r.json().catch(() => null);
			detail = r.ok ? (isi?.hasil ?? null) : null;
		} catch {
			detail = null;
		}
	}

	function angka(v: number | undefined, digit = 2) {
		return v == null ? '—' : v.toLocaleString('id-ID', { maximumFractionDigits: digit });
	}
	function rupiah(v: number | undefined) {
		if (v == null) return '—';
		if (v >= 1e12) return `${(v / 1e12).toFixed(2)} T`;
		if (v >= 1e9) return `${(v / 1e9).toFixed(1)} M`;
		return `${(v / 1e6).toFixed(0)} jt`;
	}
	function tanggal(t: number) {
		return new Date(t).toLocaleDateString('id-ID', { day: '2-digit', month: 'short' });
	}
</script>

<svelte:head><title>IDX | War Room</title></svelte:head>

<MarketShell {area} aktif="ringkas" tanpaKepala>
<div class="space-y-4">
	<PageHeader
		eyebrow="War Room · IDX"
		title="IDX"
		tag="AKTIF"
		description="IHSG dari sumber publik, plus data per emiten dari idx-edge: harga, penggerak, ringkasan broker, dan laporan keuangan."
		terverifikasi={true}
		sumber="yahoo:jkse + idx-edge:stock.arjum.com"
	/>

	{#if memuat}
		<Skeleton baris={5} tinggi={44} />
	{:else}
		<!-- IHSG -->
		{#if d}
			<section class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
				<div class="rounded-card border border-line bg-surface p-4">
					<div class="label-mikro font-mono text-text-3">IHSG</div>
					<div class="mt-1 font-mono text-17 font-bold text-text">{angka(d.last)}</div>
					<div class="mt-1 text-11 text-text-3">pembukaan {angka(d.open)}</div>
				</div>
				<div class="rounded-card border border-line bg-surface p-4">
					<div class="label-mikro font-mono text-text-3">PERUBAHAN</div>
					<div class="mt-1 font-mono text-17 font-bold"
						class:text-neg={(d.change_pct ?? 0) < 0} class:text-pos={(d.change_pct ?? 0) > 0}>
						{(d.change_pct ?? 0).toFixed(2)} %
					</div>
					<div class="mt-1 text-11 text-text-3">terhadap penutupan sebelumnya</div>
				</div>
				<div class="rounded-card border border-line bg-surface p-4">
					<div class="label-mikro font-mono text-text-3">RENTANG HARI INI</div>
					<div class="mt-1 font-mono text-14 font-bold text-text">{angka(d.low)} – {angka(d.high)}</div>
				</div>
				<div class="rounded-card border border-line bg-surface p-4">
					<div class="label-mikro font-mono text-text-3">VOLUME</div>
					<div class="mt-1 font-mono text-17 font-bold text-text">
						{d.volume ? `${angka(d.volume / 1_000_000, 1)} jt` : '—'}
					</div>
					{#if !d.volume}
						<div class="mt-1 text-11 text-text-3">sumber tidak mengirim volume</div>
					{/if}
				</div>
			</section>
		{:else if galat}
			<EmptyState judul="IHSG tidak tersedia" pesan={galat} ringkas={true} />
		{/if}

		<!-- Cari emiten -->
		<section class="rounded-card border border-line bg-surface p-4">
			<h2 class="text-13 font-bold text-text">Cari emiten</h2>
			<form class="mt-2 flex gap-2" onsubmit={(e) => { e.preventDefault(); void cari(); }}>
				<input
					type="text" bind:value={kueri} placeholder="BBCA, BBRI, TLKM…" maxlength="12"
					class="min-h-[44px] flex-1 rounded-control border border-line bg-surface-2 px-3 font-mono text-12 uppercase text-text"
				/>
				<button
					type="submit" disabled={memuatCari || kueri.trim().length < 2}
					class="min-h-[44px] rounded-control border border-line px-3 font-mono text-11 text-text-2 hover:border-accent hover:text-accent disabled:opacity-40"
				>
					{memuatCari ? 'mencari…' : 'cari'}
				</button>
			</form>

			{#if hasilCari.length > 0}
				<ul class="mt-2 divide-y divide-line-soft">
					{#each hasilCari as s (s.stock_code)}
						<li>
							<button
								type="button"
								class="flex w-full items-center justify-between gap-2 py-2 text-left hover:text-accent"
								onclick={() => buka(s.stock_code)}
							>
								<span class="font-mono text-12 font-bold text-text">{s.stock_code}</span>
								<span class="truncate text-11 text-text-3">{s.stock_name}</span>
							</button>
						</li>
					{/each}
				</ul>
			{/if}

			{#if detail}
				<div class="mt-3 rounded border border-line bg-surface-2 p-3">
					<div class="flex flex-wrap items-baseline gap-2">
						<span class="font-mono text-14 font-bold text-text">{detail.code}</span>
						<span class="font-mono text-14" class:text-pos={(detail.change_pct ?? 0) > 0} class:text-neg={(detail.change_pct ?? 0) < 0}>
							{angka(detail.last_price)} ({detail.change_pct ?? 0} %)
						</span>
						<span class="font-mono text-10 text-text-3">{detail.market_label ?? ''}</span>
					</div>
					<dl class="mt-2 grid gap-2 text-11 sm:grid-cols-4">
						<div><dt class="text-text-3">Frekuensi</dt><dd class="font-mono text-text">{angka(detail.freq, 0)}</dd></div>
						<div><dt class="text-text-3">Lot</dt><dd class="font-mono text-text">{angka(detail.lot, 0)}</dd></div>
						<div><dt class="text-text-3">Nilai</dt><dd class="font-mono text-text">{rupiah(detail.value)}</dd></div>
						<div><dt class="text-text-3">VWAP</dt><dd class="font-mono text-text">{angka(detail.vwap)}</dd></div>
					</dl>
				</div>
			{/if}
		</section>

		<RunningTrade />

		<!-- Penggerak -->
		{#if ringkas?.penggerak?.gainers?.length}
			<section class="rounded-card border border-line bg-surface p-4">
				<div class="flex flex-wrap items-center justify-between gap-2">
					<h2 class="text-13 font-bold text-text">Penggerak hari ini</h2>
					<span class="font-mono text-10 text-text-3">idx-edge · {ringkas.diambil?.slice(11, 16) ?? ''} WIB</span>
				</div>
				<div class="mt-2 grid gap-3 sm:grid-cols-2">
					<div>
						<div class="label-mikro font-mono text-pos">NAIK</div>
						<ul class="mt-1 divide-y divide-line-soft">
							{#each (ringkas.penggerak.gainers ?? []).slice(0, 5) as g (g.code)}
								<li class="flex items-center justify-between py-1 text-11">
									<button type="button" class="font-mono text-text hover:text-accent" onclick={() => buka(g.code)}>{g.code}</button>
									<span class="font-mono text-pos">{angka(g.last_price)} · +{angka(g.change_pct)}%</span>
								</li>
							{/each}
						</ul>
					</div>
					<div>
						<div class="label-mikro font-mono text-neg">TURUN</div>
						<ul class="mt-1 divide-y divide-line-soft">
							{#each (ringkas.penggerak.losers ?? []).slice(0, 5) as g (g.code)}
								<li class="flex items-center justify-between py-1 text-11">
									<button type="button" class="font-mono text-text hover:text-accent" onclick={() => buka(g.code)}>{g.code}</button>
									<span class="font-mono text-neg">{angka(g.last_price)} · {angka(g.change_pct)}%</span>
								</li>
							{/each}
						</ul>
					</div>
				</div>
			</section>
		{:else if galatRingkas}
			<section class="rounded-card border border-line bg-surface p-4">
				<h2 class="text-13 font-bold text-text">Penggerak hari ini</h2>
				<p class="mt-1 text-11 text-text-3">Sumber idx-edge belum bisa dipakai: {galatRingkas}</p>
			</section>
		{/if}

		<!-- Blue chip -->
		{#if ringkas?.blue_chip?.stocks}
			<section class="rounded-card border border-line bg-surface p-4">
				<h2 class="text-13 font-bold text-text">Blue chip</h2>
				<div class="mt-2 overflow-x-auto">
					<table class="w-full text-11 text-left">
						<thead class="border-b border-line text-10 text-text-3">
							<tr>
								<th class="px-2 py-1.5">Kode</th>
								<th class="px-2 py-1.5 text-right">Harga</th>
								<th class="px-2 py-1.5 text-right">Perubahan</th>
								<th class="px-2 py-1.5 text-right">Nilai</th>
								<th class="px-2 py-1.5 text-right">VWAP</th>
							</tr>
						</thead>
						<tbody class="divide-y divide-line-soft">
							{#each Object.values(ringkas.blue_chip.stocks) as s (s.code)}
								<tr class="hover:bg-surface-2/60">
									<td class="px-2 py-1.5 font-mono text-text">{s.code}</td>
									<td class="px-2 py-1.5 text-right font-mono text-text">{angka(s.last_price)}</td>
									<td class="px-2 py-1.5 text-right font-mono" class:text-pos={(s.change_pct ?? 0) > 0} class:text-neg={(s.change_pct ?? 0) < 0}>
										{angka(s.change_pct)} %
									</td>
									<td class="px-2 py-1.5 text-right font-mono text-text-2">{rupiah(s.value)}</td>
									<td class="px-2 py-1.5 text-right font-mono text-text-3">{angka(s.vwap)}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</section>
		{/if}

		<!-- Candle -->
		{#if d?.candles?.length}
			<section class="rounded-card border border-line bg-surface p-4">
				<h2 class="text-13 font-bold text-text">Candle harian IHSG</h2>
				<div class="mt-2 overflow-x-auto">
					<table class="w-full text-11 text-left">
						<thead class="border-b border-line text-10 text-text-3">
							<tr>
								<th class="px-2 py-1.5">Tanggal</th>
								<th class="px-2 py-1.5 text-right">Open</th>
								<th class="px-2 py-1.5 text-right">High</th>
								<th class="px-2 py-1.5 text-right">Low</th>
								<th class="px-2 py-1.5 text-right">Close</th>
							</tr>
						</thead>
						<tbody class="divide-y divide-line-soft">
							{#each (d.candles ?? []).slice(-15).reverse() as c (c.t)}
								<tr class="hover:bg-surface-2/60">
									<td class="px-2 py-1.5 font-mono text-text-3">{tanggal(c.t)}</td>
									<td class="px-2 py-1.5 text-right font-mono text-text-2">{angka(c.o)}</td>
									<td class="px-2 py-1.5 text-right font-mono text-pos">{angka(c.h)}</td>
									<td class="px-2 py-1.5 text-right font-mono text-neg">{angka(c.l)}</td>
									<td class="px-2 py-1.5 text-right font-mono font-bold text-text">{angka(c.c)}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</section>
		{/if}

		<!-- Batas jujur -->
		<section class="rounded-card border border-line bg-surface p-4">
			<h2 class="text-13 font-bold text-text">Batas jujur</h2>
			{#if ringkas?.pemakaian}
				<div class="mt-2 rounded border border-line bg-surface-2 p-2">
					<div class="flex flex-wrap items-baseline gap-x-3 gap-y-1 font-mono text-11">
						<span class="text-text-3">Panggilan keluar hari ini</span>
						<span class="text-text font-bold">{ringkas.pemakaian.panggilan_hari_ini ?? 0}</span>
						<span class="text-text-3">/ anggaran {ringkas.pemakaian.anggaran_harian ?? 0}</span>
						<span class="text-text-3">· sisa ± {ringkas.pemakaian.sisa_perkiraan ?? 0}</span>
					</div>
					<p class="mt-1 text-10 leading-relaxed text-text-3">
						Dihitung sendiri dari panggilan keluar. Sisa kuota resmi hanya terlihat di dashboard
						arjum karena endpoint usage menolak API key. Kuota berbayar per panggilan, jadi halaman
						ini memakai cache: quote 60 detik, riwayat 15 menit, laporan keuangan 24 jam.
					</p>
				</div>
			{/if}
			<ul class="mt-2 space-y-1.5 text-11 leading-relaxed text-text-2">
				<li>· Harga saham dari idx-edge bisa tertunda; kolom waktu sumber ditampilkan, jangan dipakai sebagai harga eksekusi.</li>
				<li>· Sebagian endpoint idx-edge memakan kuota per panggilan (1 kode = 1 kuota untuk daftar harga).</li>
				<li>· Tidak ada sinyal IDX yang dikirim ke mana pun. Halaman ini hanya menampilkan data.</li>
				<li>· Scanner otomatis dan bandarmologi harian belum dijadwalkan; data broker masih dibuka manual per emiten.</li>
			</ul>
		</section>
	{/if}
</div>
</MarketShell>
