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
	import Block from '$lib/components/Block.svelte';
	import FreshnessBadge from '$lib/components/FreshnessBadge.svelte';

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
			if (b && typeof b === 'object' && ('simbol' in b || 'jumlah' in b)) return { data: b as Bagian, fakta: f };
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

<div class="space-y-3">
	<header class="flex flex-wrap items-baseline justify-between gap-2">
		<h1 class="text-16 text-text">Overextended</h1>
		<p class="text-11 text-text-3">
			Harga sudah naik banyak <b>bukan</b> alasan short. Puncak hanya diketahui setelahnya —
			karena itu setiap baris membawa <span class="angka">hasil uji edge</span>-nya.
		</p>
	</header>

	{#if galat}
		<p class="rounded border border-neg/40 p-2 text-12 text-neg">Gagal memuat: {galat}</p>
	{/if}

	<Block
		judul="Ukur + uji, bukan label"
		deskripsi="Untuk setiap koin: seberapa jauh larinya, kondisi derivatifnya, dan apakah men-short pola ini pernah membayar"
		memuat={memuat}
	>
		{#if !bagian}
			<p class="text-12 text-text-3">
				Belum ada fakta <span class="angka">bagian.overextended</span>.
			</p>
		{:else if (bagian.data.simbol ?? []).length === 0}
			<p class="text-12 text-text-3">Tidak ada simbol yang berhasil diukur.</p>
		{:else}
			<ul class="space-y-3">
				{#each bagian.data.simbol ?? [] as s (s.symbol)}
					<li class="rounded border border-line p-2">
						<div class="flex flex-wrap items-baseline gap-2">
							<span class="angka text-13 text-text">{s.symbol}</span>
							<span class="angka text-12 {s.overextended ? 'text-warn' : 'text-text-3'}">
								{s.overextended ? 'overextended' : 'normal'} {pct(s.pump_pct)}
							</span>
							{#if s.divergensi_cvd}
								<span class="text-11 text-warn">divergensi CVD</span>
							{/if}
						</div>

						<p class="angka mt-1 text-12 text-text-2">
							dari puncak {pct(s.turun_dari_puncak_pct)} · OI vs puncak {pct(s.oi_mereda_pct)} ·
							funding maks {s.fr_maks_pct?.toFixed(4) ?? '—'}%
							{#if !s.fr_pernah_ramai}
								<span class="text-text-3">(tidak pernah ramai)</span>
							{/if}
						</p>

						<div class="mt-2 space-y-1">
							<p class="text-12 text-text-2">
								aturan OI+FR:
								<span class="angka {kelasVerdict(s.edge_oi_fr)}">{labelVerdict(s.edge_oi_fr)}</span>
							</p>
							<p class="text-12 text-text-2">
								aturan divergensi CVD:
								<span class="angka {kelasVerdict(s.edge_cvd)}">{labelVerdict(s.edge_cvd)}</span>
							</p>

							{#if s.edge_oi_fr_detail?.length}
								<div class="overflow-x-auto">
									<table class="angka w-full text-11 text-text-3">
										<thead>
											<tr>
												<th class="text-left font-normal">tahan</th>
												<th class="text-right font-normal">sinyal</th>
												<th class="text-right font-normal">menang</th>
												<th class="text-right font-normal">asal-short</th>
												<th class="text-right font-normal">selisih</th>
											</tr>
										</thead>
										<tbody>
											{#each s.edge_oi_fr_detail as b (b.tahan_jam)}
												<tr>
													<td>{b.tahan_jam}j</td>
													<td class="text-right">
														{b.rata_sinyal_pct != null ? pct(b.rata_sinyal_pct) : '—'}
													</td>
													<td class="text-right">
														{b.winrate_sinyal_pct != null ? `${b.winrate_sinyal_pct.toFixed(0)}%` : '—'}
													</td>
													<td class="text-right">{pct(b.rata_dasar_pct)}</td>
													<td class="text-right {b.selisih_poin != null && b.selisih_poin > 0 ? 'text-pos' : 'text-neg'}">
														{b.selisih_poin != null ? `${b.selisih_poin > 0 ? '+' : ''}${b.selisih_poin.toFixed(2)}pp` : '—'}
													</td>
												</tr>
											{/each}
										</tbody>
									</table>
								</div>
							{/if}
						</div>

						{#each s.catatan ?? [] as c}
							<p class="mt-1 text-11 text-text-3">· {c}</p>
						{/each}
					</li>
				{/each}
			</ul>

			{#each bagian.data.catatan ?? [] as c}
				<p class="mt-2 text-11 text-text-3">· {c}</p>
			{/each}
			{#if bagian.data.galat?.length}
				<p class="mt-1 text-11 text-neg">gagal: {bagian.data.galat.join(', ')}</p>
			{/if}
			<p class="mt-1 flex items-center gap-2 text-11 text-text-3">
				sumber <span class="angka">{bagian.fakta.source}</span>
				<FreshnessBadge
					status={bagian.fakta.status}
					age_s={bagian.fakta.age_s}
					ttl_s={bagian.fakta.ttl_s}
					source={bagian.fakta.source}
				/>
			</p>
		{/if}
	</Block>
</div>
