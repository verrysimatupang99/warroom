<script lang="ts">
	// Bandarmologi — broker-flow IDX dari data Arjum yang sudah kita punya.
	//
	// Asal-usul: sebuah alat screener IDX publik mempromosikan parameter "High Bid/Offer, High ATS,
	// No Sell, Close High, High Non-Regular" sebagai cara menemukan emiten yang broker flow-nya
	// bagus. Halaman ini mereplikasi yang BISA direplikasi dari data yang sudah kita bayar
	// kuotanya, dan menyatakan dengan jujur yang TIDAK bisa.
	//
	// Aturan halaman ini: skor disebut HEURISTIK — bukan "win rate" atau "akurasi". Meniru cara
	// mengukur bukan bukti bahwa strateginya menguntungkan.
	import { getArea } from '$lib/api/client';
	import type { AreaPayload, Fakta } from '$lib/api/types';
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { AREAS } from '$lib/nav';
	import Block from '$lib/components/Block.svelte';
	import SubNav from '$lib/components/SubNav.svelte';
	import FreshnessBadge from '$lib/components/FreshnessBadge.svelte';

	const areaBandar = AREAS.find((a) => a.kunci === 'bandar')!;
	let sub = $state(page.url.searchParams.get('sub') ?? 'broker');

	$effect(() => {
		const s = page.url.searchParams.get('sub');
		if (s && areaBandar.anak.some((a) => a.slug === s)) {
			sub = s;
		}
	});

	function pilihSub(s: string) {
		sub = s;
		if (typeof window !== 'undefined') {
			void goto(`?sub=${s}`, { replaceState: true, keepFocus: true, noScroll: true });
		}
	}

	interface Broker {
		broker?: string;
		nama?: string;
		net_nilai?: number;
		frq_beli?: number;
		frq_jual?: number;
	}

	interface Baris {
		kode?: string;
		tanggal?: string;
		ats_beli?: number | null;
		ats_jual?: number | null;
		porsi_frq_beli?: number | null;
		net_juta?: number;
		frq_beli?: number;
		frq_jual?: number;
		no_sell?: boolean;
		skor_heuristik?: number;
		pembeli_teratas?: Broker;
		penjual_teratas?: Broker;
		jumlah_broker?: number;
	}

	interface Bagian {
		hari?: string;
		jumlah?: number;
		diperiksa?: string[];
		maks_ticker?: number;
		hasil?: Baris[];
		galat?: string[];
		catatan?: string[];
	}

	let payload = $state<AreaPayload | null>(null);
	let galat = $state<string | null>(null);
	let memuat = $state(true);

	async function muat() {
		try {
			payload = await getArea('idx');
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
			if (f.key !== 'bagian' && f.key !== 'bandarmologi') continue;
			const v = nilaiObj(f.value);
			const b = (v?.['bandarmologi'] ?? (v?.['bagian'] as Record<string, unknown> | undefined)?.['bandarmologi'] ?? v) as Record<string, unknown> | undefined;
			if (b && typeof b === 'object' && ('hasil' in b || 'diperiksa' in b)) return { data: b as Bagian, fakta: f };
		}
		return null;
	});

	const rp = (n?: number | null) =>
		n == null ? '—' : `Rp${n.toLocaleString('id-ID', { maximumFractionDigits: 0 })}`;
	const jt = (n?: number) =>
		n == null ? '—' : `${n > 0 ? '+' : ''}${n.toLocaleString('id-ID', { maximumFractionDigits: 1 })} jt`;
	const besar = (n?: number) =>
		Math.abs(n ?? 0) >= 1e9
			? `${n! > 0 ? '+' : ''}${(n! / 1e9).toFixed(2)} M`
			: `${n! > 0 ? '+' : ''}${(n! / 1e6).toFixed(0)} jt`;

	function kelasSkor(s?: number): string {
		if (s == null) return 'text-text-3';
		if (s >= 80) return 'text-pos';
		if (s >= 60) return 'text-text-2';
		return 'text-text-3';
	}
</script>

<svelte:head>
	<title>Bandarmologi — War Room</title>
</svelte:head>

<div class="space-y-4">
	<div class="border-b border-line pb-3">
		<div class="flex items-center gap-2">
			<h1 class="text-22 font-bold text-text font-display">Bandarmologi &amp; Broker Flow</h1>
			<span class="rounded bg-surface px-2 py-0.5 text-11 font-mono uppercase text-accent border border-line">
				IDX FLOW
			</span>
		</div>
		<p class="text-12 text-text-3 mt-1">
			Broker-flow IDX dari Arjum. Skor di sini <b>heuristik deskriptif</b> — mereplikasi cara ukur, bukan
			jaminan untung.
		</p>
	</div>

	<!-- Sub-navigasi Tabs -->
	<SubNav area={areaBandar} aktif={sub} onpilih={pilihSub} />

	{#if galat}
		<p class="rounded border border-neg/40 p-2 text-12 text-neg">Gagal memuat: {galat}</p>
	{/if}

	{#if sub === 'broker'}
		<Block
			judul="Broker Flow Hari Ini"
			deskripsi="Kandidat dari screener Arjum, diukur dengan data broker (bfrq/sfrq/bval/nval)"
			memuat={memuat}
		>
			{#if !bagian}
				<p class="text-12 text-text-3">
					Belum ada fakta <span class="angka">bagian.bandarmologi</span>.
				</p>
			{:else if (bagian.data.hasil ?? []).length === 0}
				<p class="text-12 text-text-2">Tidak ada emiten yang berhasil diukur.</p>
				<p class="mt-1 text-11 text-text-3">
					Biasanya karena cache harian belum terisi atau kuota Arjum sedang dijaga.
				</p>
			{:else}
				<ul class="space-y-2">
					{#each bagian.data.hasil ?? [] as r (r.kode)}
						<li class="rounded border border-line p-2.5 bg-surface">
							<div class="flex flex-wrap items-baseline gap-2">
								<span class="angka text-14 font-bold text-text font-mono">{r.kode}</span>
								<span class="angka text-12 font-semibold {kelasSkor(r.skor_heuristik)}">
									skor {r.skor_heuristik?.toFixed(1) ?? '—'}
								</span>
								{#if r.no_sell}<span class="text-11 px-1.5 py-0.5 rounded bg-pos/15 text-pos border border-pos/30 font-bold">NO SELL</span>{/if}
								<span class="text-10 text-text-3 font-mono">tanggal {r.tanggal ?? '—'}</span>
							</div>

							<p class="angka mt-1.5 text-12 text-text-2">
								net {jt(r.net_juta)} · frekuensi beli:jual {r.frq_beli?.toLocaleString('id-ID') ?? '—'} :
								{r.frq_jual?.toLocaleString('id-ID') ?? '—'}
								{#if r.porsi_frq_beli != null}
									({(r.porsi_frq_beli * 100).toFixed(0)}% beli)
								{/if}
							</p>
							<p class="angka text-12 text-text-2">
								ATS beli {rp(r.ats_beli)} vs jual {rp(r.ats_jual)}
								{#if r.ats_beli != null && r.ats_jual != null}
									<span class="text-text-3">
										— {r.ats_beli > r.ats_jual ? 'transaksi besar di sisi beli (akumulasi)' : 'transaksi besar di sisi jual (distribusi)'}
									</span>
								{/if}
							</p>

							{#if r.pembeli_teratas}
								<p class="text-11 text-text-3 mt-1">
									akumulator teratas: <span class="angka font-bold text-text">{r.pembeli_teratas.broker}</span> {r.pembeli_teratas.nama ?? ''}
									<span class="angka font-mono {r.pembeli_teratas.net_nilai && r.pembeli_teratas.net_nilai > 0 ? 'text-pos' : 'text-neg'}">
										({besar(r.pembeli_teratas.net_nilai)})
									</span>
								</p>
							{/if}
							{#if r.penjual_teratas}
								<p class="text-11 text-text-3">
									distributor teratas: <span class="angka font-bold text-text">{r.penjual_teratas.broker}</span> {r.penjual_teratas.nama ?? ''}
									<span class="angka font-mono text-neg">({besar(r.penjual_teratas.net_nilai)})</span>
								</p>
							{/if}
						</li>
					{/each}
				</ul>

				{#each bagian.data.catatan ?? [] as c}
					<p class="mt-2 text-11 text-text-3">• {c}</p>
				{/each}
				{#if bagian.data.galat?.length}
					<p class="mt-1 text-11 text-neg">gagal: {bagian.data.galat.join(', ')}</p>
				{/if}
				<p class="mt-2 flex flex-wrap items-center gap-2 text-11 text-text-3">
					<span>
						diperiksa {bagian.data.diperiksa?.join(', ') ?? '—'} (batas {bagian.data.maks_ticker ?? '—'} ticker
						per siklus — disiplin kuota Arjum)
					</span>
					<FreshnessBadge
						status={bagian.fakta.status}
						age_s={bagian.fakta.age_s}
						ttl_s={bagian.fakta.ttl_s}
						source={bagian.fakta.source}
					/>
				</p>
			{/if}
		</Block>
	{:else if sub === 'batas'}
		<Block judul="Batas Metodologi &amp; Batasan Analisis" deskripsi="Hal yang bisa &amp; tidak bisa diukur dari data broker summary">
			<div class="space-y-3">
				<div class="rounded-card border border-line bg-surface p-3 space-y-1.5">
					<h3 class="text-13 font-bold text-text">1. Penutupan Kode Broker Intraday oleh BEI</h3>
					<p class="text-12 text-text-2">
						Sejak 6 Desember 2021, Bursa Efek Indonesia resmi meniadakan penayangan kode broker secara real-time selama sesi perdagangan berlangsung. Data broker summary baru tersedia setelah jam pasar ditutup (End of Day). Segala keputusan intraday berbasis "pergerakan bandar live" di running trade adalah asumsi, bukan fakta order book langsung.
					</p>
				</div>

				<div class="rounded-card border border-line bg-surface p-3 space-y-1.5">
					<h3 class="text-13 font-bold text-text">2. Disiplin Kuota Arjum</h3>
					<p class="text-12 text-text-2">
						Pengambilan data dibatasi ketat maksimum 20 ticker per siklus. Sistem memilih emiten dengan likuiditas dan volatilitas signifikan dari screener Arjum untuk menghindari penghamburan kuota API berbayar.
					</p>
				</div>

				<div class="rounded-card border border-line bg-surface p-3 space-y-1.5">
					<h3 class="text-13 font-bold text-text">3. Keterbatasan Inferensi Bandarmologi</h3>
					<p class="text-12 text-text-2">
						Satu institusi atau bandar dapat menggunakan puluhan rekening efek dari berbagai sekuritas (multi-account/multi-broker), melakukan crossing di pasar negosiasi, atau menggunakan algoritma iceberg/TWAP untuk menyamarkan jejak akumulasi/distribusi. Skor di sini adalah heuristik pola permukaan, bukan jaminan arah masa depan.
					</p>
				</div>
			</div>
		</Block>
	{/if}
</div>
