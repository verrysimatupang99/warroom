<script lang="ts">
	// Overextended — koin yang harganya sudah lari jauh… dan bukti apakah itu berarti apa-apa.
	//
	// Halaman ini dibuat karena sebuah postingan media sosial memamerkan short $VELVET dengan
	// alasan "derivatif mulai mereda". Diuji ke data Binance sungguhan, alasannya tidak didukung:
	// OI justru di puncak dan naik +10,7% pada jam masuk, funding tidak pernah ramai.
	//
	// Aturan halaman ini: label "overextended" TIDAK PERNAH tampil sendirian. Setiap baris wajib
	// membawa hasil uji edge-nya — apakah pola itu pernah membayar, dibanding short asal-asalan.
	import { getArea } from '$lib/api/client';
	import type { AreaPayload, Fakta } from '$lib/api/types';
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { AREAS } from '$lib/nav';
	import Block from '$lib/components/Block.svelte';
	import SubNav from '$lib/components/SubNav.svelte';
	import FreshnessBadge from '$lib/components/FreshnessBadge.svelte';

	const areaOver = AREAS.find((a) => a.kunci === 'overextended')!;
	let sub = $state(page.url.searchParams.get('sub') ?? 'ukur');

	$effect(() => {
		const s = page.url.searchParams.get('sub');
		if (s && areaOver.anak.some((a) => a.slug === s)) {
			sub = s;
		}
	});

	function pilihSub(s: string) {
		sub = s;
		if (typeof window !== 'undefined') {
			void goto(`?sub=${s}`, { replaceState: true, keepFocus: true, noScroll: true });
		}
	}

	interface UjiBaris {
		tahan_jam: number;
		n_sinyal: number;
		n_dasar: number;
		rata_dasar_pct: number;
		rata_sinyal_pct?: number;
		winrate_sinyal_pct?: number;
		selisih_poin?: number;
	}

	interface Simbol {
		symbol: string;
		pump_pct: number | null;
		turun_dari_puncak_pct: number | null;
		oi_mereda_pct: number | null;
		fr_pernah_ramai: boolean;
		fr_maks_pct: number | null;
		overextended: boolean;
		divergensi_cvd: boolean | null;
		edge_oi_fr: string;
		edge_oi_fr_detail: UjiBaris[];
		edge_cvd: string;
		edge_cvd_detail: UjiBaris[];
		catatan: string[];
	}

	interface Bagian {
		jumlah: number;
		paling_overextended: string | null;
		simbol: Simbol[];
		galat: string[];
		catatan: string[];
		diambil_epoch: number;
	}

	let payload = $state<AreaPayload | null>(null);
	let galat = $state<string | null>(null);
	let memuat = $state(true);

	async function muat() {
		try {
			payload = await getArea('crypto');
			galat = null;
		} catch (e) {
			galat = (e as Error)?.message ?? String(e);
		}
		memuat = false;
	}

	function nilaiObj(v: unknown): Record<string, unknown> | null {
		if (v && typeof v === 'object') return v as Record<string, unknown>;
		if (typeof v === 'string') {
			try {
				const d = JSON.parse(v);
				return d && typeof d === 'object' ? d : null;
			} catch {
				return null;
			}
		}
		return null;
	}

	const bagian = $derived.by(() => {
		for (const f of [...(payload?.facts ?? [])].reverse()) {
			if (f.key !== 'bagian' && f.key !== 'overextended') continue;
			const v = nilaiObj(f.value);
			const b = (v?.['overextended'] ?? (v?.['bagian'] as Record<string, unknown> | undefined)?.['overextended'] ?? v) as Record<string, unknown> | undefined;
			if (b && typeof b === 'object' && ('simbol' in b || 'jumlah' in b)) return { data: b as unknown as Bagian, fakta: f };
		}
		return null;
	});

	const pct = (n?: number | null) => (n == null ? '—' : `${n > 0 ? '+' : ''}${n.toFixed(1)}%`);

	function kelasVerdict(v?: string): string {
		if (v === 'ada-keunggulan') return 'text-pos';
		if (v === 'tidak-terbukti' || v === 'tidak-ada-sinyal') return 'text-neg';
		return 'text-text-3'; // perlu-uji-tambahan = jujur ragu
	}

	function labelVerdict(v?: string): string {
		switch (v) {
			case 'ada-keunggulan':
				return 'lebih baik dari asal-short';
			case 'tidak-terbukti':
				return 'tidak terbukti';
			case 'tidak-ada-sinyal':
				return 'sinyal tidak menyala';
			case 'perlu-uji-tambahan':
				return 'pasar turun — belum bisa dinilai';
			default:
				return '—';
		}
	}
</script>

<svelte:head>
	<title>Overextended — War Room</title>
</svelte:head>

<div class="space-y-4">
	<div class="border-b border-line pb-3">
		<div class="flex items-center gap-2">
			<h1 class="text-22 font-bold text-text font-display">Overextended &amp; Uji Edge</h1>
			<span class="rounded bg-surface px-2 py-0.5 text-11 font-mono uppercase text-accent border border-line">
				CRYPTO RESEARCH
			</span>
		</div>
		<p class="text-12 text-text-3 mt-1">
			Harga sudah naik banyak <b>bukan</b> alasan short. Puncak hanya diketahui setelahnya —
			karena itu setiap baris membawa <span class="angka font-mono text-accent">hasil uji edge empiris</span>.
		</p>
	</div>

	<!-- Sub-navigasi Tabs -->
	<SubNav area={areaOver} aktif={sub} onpilih={pilihSub} />

	{#if galat}
		<p class="rounded border border-neg/40 p-2 text-12 text-neg">Gagal memuat: {galat}</p>
	{/if}

	{#if sub === 'ukur'}
		<Block
			judul="Pengukuran Ekstensi Harga &amp; Derivatif"
			deskripsi="Seberapa jauh pump harga dari dasar, jarak dari puncak, perubahan OI, dan funding rate"
			memuat={memuat}
		>
			{#if !bagian}
				<p class="text-12 text-text-3">
					Belum ada fakta <span class="angka font-mono">bagian.overextended</span>.
				</p>
			{:else if (bagian.data.simbol ?? []).length === 0}
				<p class="text-12 text-text-3">Tidak ada simbol yang berhasil diukur.</p>
			{:else}
				<ul class="space-y-3">
					{#each bagian.data.simbol ?? [] as s (s.symbol)}
						<li class="rounded border border-line p-3 bg-surface">
							<div class="flex flex-wrap items-baseline justify-between gap-2 border-b border-line-soft pb-2 mb-2">
								<div class="flex items-center gap-2">
									<span class="angka text-15 font-bold text-text font-mono">{s.symbol}</span>
									<span class="angka text-12 font-semibold px-2 py-0.5 rounded border {s.overextended ? 'text-warn bg-warn/10 border-warn/30' : 'text-text-3 bg-canvas border-line'}">
										{s.overextended ? 'OVEREXTENDED' : 'NORMAL'} ({pct(s.pump_pct)})
									</span>
								</div>
								{#if s.divergensi_cvd}
									<span class="text-11 px-2 py-0.5 rounded bg-amber-500/15 text-amber-300 border border-amber-500/30 font-bold">
										DIVERGENSI CVD
									</span>
								{/if}
							</div>

							<div class="grid grid-cols-2 sm:grid-cols-4 gap-2 font-mono text-12 mb-2">
								<div class="rounded bg-canvas p-2 border border-line">
									<span class="text-10 text-text-3 block">TURUN DR PUNCAK</span>
									<span class="font-bold text-text">{pct(s.turun_dari_puncak_pct)}</span>
								</div>
								<div class="rounded bg-canvas p-2 border border-line">
									<span class="text-10 text-text-3 block">OI VS PUNCAK</span>
									<span class="font-bold text-accent">{pct(s.oi_mereda_pct)}</span>
								</div>
								<div class="rounded bg-canvas p-2 border border-line">
									<span class="text-10 text-text-3 block">FUNDING MAKS</span>
									<span class="font-bold text-text">{s.fr_maks_pct?.toFixed(4) ?? '—'}%</span>
								</div>
								<div class="rounded bg-canvas p-2 border border-line">
									<span class="text-10 text-text-3 block">STATUS DERIVATIF</span>
									<span class="font-bold {s.fr_pernah_ramai ? 'text-pos' : 'text-text-3'}">
										{s.fr_pernah_ramai ? 'RAMAI' : 'SUNYI'}
									</span>
								</div>
							</div>

							{#each s.catatan ?? [] as c}
								<p class="mt-1 text-11 text-text-3">• {c}</p>
							{/each}
						</li>
					{/each}
				</ul>

				{#each bagian.data.catatan ?? [] as c}
					<p class="mt-2 text-11 text-text-3">• {c}</p>
				{/each}
				{#if bagian.data.galat?.length}
					<p class="mt-1 text-11 text-neg">gagal: {bagian.data.galat.join(', ')}</p>
				{/if}
				<p class="mt-2 flex items-center gap-2 text-11 text-text-3">
					sumber <span class="angka font-mono">{bagian.fakta.source}</span>
					<FreshnessBadge
						status={bagian.fakta.status}
						age_s={bagian.fakta.age_s}
						ttl_s={bagian.fakta.ttl_s}
						source={bagian.fakta.source}
					/>
				</p>
			{/if}
		</Block>
	{:else if sub === 'uji'}
		<Block
			judul="Uji Edge Empiris: Apakah Short Pola Ini Pernah Membayar?"
			deskripsi="Hasil backtest terhadap data historis: membandingkan rata-rata sinyal vs baseline asal-short"
			memuat={memuat}
		>
			{#if !bagian || (bagian.data.simbol ?? []).length === 0}
				<p class="text-12 text-text-3">Belum ada data uji edge.</p>
			{:else}
				<div class="space-y-4">
					{#each bagian.data.simbol ?? [] as s (s.symbol)}
						<div class="rounded-card border border-line bg-surface p-3 space-y-2">
							<div class="flex items-center justify-between border-b border-line-soft pb-2">
								<span class="angka text-14 font-bold text-text font-mono">{s.symbol}</span>
								<div class="flex items-center gap-2">
									<span class="text-11 text-text-3">Aturan OI+FR:</span>
									<span class="angka font-bold text-11 {kelasVerdict(s.edge_oi_fr)}">{labelVerdict(s.edge_oi_fr)}</span>
									<span class="text-11 text-text-3">· CVD:</span>
									<span class="angka font-bold text-11 {kelasVerdict(s.edge_cvd)}">{labelVerdict(s.edge_cvd)}</span>
								</div>
							</div>

							{#if s.edge_oi_fr_detail?.length}
								<div class="overflow-x-auto">
									<table class="angka w-full text-12 text-text">
										<thead class="border-b border-line text-text-3 text-10 font-mono">
											<tr>
												<th class="text-left py-1.5 px-2">TAHAN</th>
												<th class="text-right py-1.5 px-2">RATA SINYAL</th>
												<th class="text-right py-1.5 px-2">WIN RATE</th>
												<th class="text-right py-1.5 px-2">ASAL-SHORT</th>
												<th class="text-right py-1.5 px-2">SELISIH EDGE</th>
											</tr>
										</thead>
										<tbody class="divide-y divide-line-soft font-mono">
											{#each s.edge_oi_fr_detail as b (b.tahan_jam)}
												<tr class="hover:bg-canvas/50">
													<td class="py-1.5 px-2 font-bold">{b.tahan_jam} Jam</td>
													<td class="py-1.5 px-2 text-right">
														{b.rata_sinyal_pct != null ? pct(b.rata_sinyal_pct) : '—'}
													</td>
													<td class="py-1.5 px-2 text-right">
														{b.winrate_sinyal_pct != null ? `${b.winrate_sinyal_pct.toFixed(0)}%` : '—'}
													</td>
													<td class="py-1.5 px-2 text-right text-text-3">{pct(b.rata_dasar_pct)}</td>
													<td class="py-1.5 px-2 text-right font-bold {b.selisih_poin != null && b.selisih_poin > 0 ? 'text-pos' : 'text-neg'}">
														{b.selisih_poin != null ? `${b.selisih_poin > 0 ? '+' : ''}${b.selisih_poin.toFixed(2)}pp` : '—'}
													</td>
												</tr>
											{/each}
										</tbody>
									</table>
								</div>
							{:else}
								<p class="text-11 text-text-3">Tidak ada data detail rentang penahanan.</p>
							{/if}
						</div>
					{/each}
				</div>
			{/if}
		</Block>
	{/if}
</div>
