<script lang="ts">
	// LP — Positions vs Candidates.
	//
	// Halaman ini menjawab tepat satu pertanyaan yang tidak bisa dijawab klaim LP di media sosial:
	// "posisi LP saya lebih baik daripada cuma memegang tokennya?" (impermanent loss).
	//
	// Pemisahan WAJIB dan sengaja:
	//   POSISI   = uang yang betul-betul diparkir, dengan harga masuk & keluar tercatat.
	//              Hanya dari sini `LP vs hold` bisa dihitung.
	//   KANDIDAT = hasil pencarian pool (data pool saja). Belum ada uang. Tidak boleh
	//              ditampilkan seolah hasil.
	//
	// Yang TIDAK kami klaim: fee APR nyata (butuh fee tier + porsi posisi di dalam range) dan
	// USD apa pun kalau harga belum lengkap. Itu ditulis apa adanya, bukan ditebak.
	import { getArea } from '$lib/api/client';
	import type { AreaPayload, Fakta } from '$lib/api/types';
	import Block from '$lib/components/Block.svelte';
	import FreshnessBadge from '$lib/components/FreshnessBadge.svelte';

	interface Posisi {
		pool?: string;
		pasangan?: string;
		dex?: string;
		label_pool?: string;
		umur_jam?: number;
		hitung?: {
			status?: string;
			unit?: string;
			kenaikan_base_pct?: number;
			kenaikan_quote_pct?: number;
			imnbal?: number;
			imbal_hasil_tertimbang_pct?: number;
			imbal_hasil_hold_pct?: number;
			il_vs_hold_pct?: number;
			return_lp_pct?: number;
			return_hold_pct?: number;
			lp_vs_hold_usd?: number;
			menang?: string;
			jumlah_kedua_kaki_naik?: boolean;
			catatan?: string[];
		};
	}

	interface Kandidat {
		pair?: string;
		alamat?: string;
		dex?: string;
		rantai?: string;
		label_pool?: string;
		liq_usd?: number | null;
		vol_24h?: number | null;
		turnover_24h?: number | null;
		chg_h24?: number | null;
		umur_jam?: number | null;
		kualitas?: string;
		catatan?: string[];
	}

	interface BagianLp {
		jumlah?: number;
		terbuka?: number;
		tertutup?: number;
		posisi_terbuka?: Posisi[];
		riwayat?: Posisi[];
		kandidat?: Kandidat[];
		catatan?: string[];
	}

	let payload = $state<AreaPayload | null>(null);
	let galat = $state<string | null>(null);
	let memuat = $state(true);

	async function muat() {
		try {
			// Kunci `bagian` tersedia di area crypto (snapshot produksi).
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

	const faktaBagian = $derived((payload?.facts ?? []).filter((f: Fakta) => f.kind === 'bagian'));

	const lp = $derived.by(() => {
		for (const f of [...faktaBagian].reverse()) {
			const v = nilaiObj(f.value);
			const b = v?.['lp'] ?? (v?.['bagian'] as Record<string, unknown> | undefined)?.['lp'];
			if (b && typeof b === 'object') return { data: b as BagianLp, fakta: f };
		}
		return null;
	});

	const usd = (n?: number | null) =>
		n == null ? '—' : `$${n.toLocaleString('id-ID', { maximumFractionDigits: 0 })}`;
	const pct = (n?: number | null) => (n == null ? '—' : `${n > 0 ? '+' : ''}${n.toFixed(2)}%`);

	function kelasKualitas(k?: string): string {
		if (k === 'layak-ditinjau') return 'text-pos';
		if (k === 'pool-mati' || k === 'tipis') return 'text-neg';
		return 'text-text-3';
	}
</script>

<svelte:head>
	<title>LP — War Room</title>
</svelte:head>

<div class="space-y-3">
	<header class="flex flex-wrap items-baseline justify-between gap-2">
		<h1 class="text-16 text-text">Liquidity Provider</h1>
		<p class="text-11 text-text-3">
			Hanya <span class="angka">LP vs hold</span> yang bisa membuktikan LP menguntungkan — dan itu
			butuh harga masuk <em>dan</em> keluar posisi.
		</p>
	</header>

	{#if galat}
		<p class="rounded border border-neg/40 p-2 text-12 text-neg">Gagal memuat: {galat}</p>
	{/if}

	<Block
		judul="Posisi LP (uang nyata)"
		deskripsi="Yang betul-betul diparkir & dicatat — hanya dari sini IL vs hold bisa dihitung"
		memuat={memuat}
	>
		{#if !lp}
			<p class="text-12 text-text-3">Belum ada fakta <span class="angka">bagian.lp</span>.</p>
		{:else if (lp.data.jumlah ?? 0) === 0}
			<p class="text-13 text-text-2">
				<span class="angka">0 posisi</span> — belum ada uang yang diparkir di LP.
			</p>
			<p class="mt-1 text-11 text-text-3">
				Ini bukan kegagalan: mengukur dulu sebelum menyetor. Untuk mencatat posisi nyata, catat
				<b>kedua kaki</b> (jumlah token + jumlah quote) saat masuk dan saat keluar — tanpa itu,
				semua angka LP tetap <span class="angka">belum diketahui</span>.
			</p>
		{:else}
			<ul class="space-y-2">
				{#each lp.data.posisi_terbuka ?? [] as p (p.pool)}
					<li class="rounded border border-line p-2">
						<div class="flex flex-wrap items-baseline gap-2">
							<span class="angka text-13 text-text">{p.pasangan ?? '—'}</span>
							<span class="text-11 text-text-3">{p.dex ?? '—'} {p.label_pool ?? ''}</span>
							<span class="text-10 text-text-3">terbuka {p.umur_jam ?? 0} jam</span>
						</div>
						<p class="text-11 text-text-3">
							menunggu ditutup — IL vs hold baru bisa dihitung setelah keluar
						</p>
					</li>
				{/each}
			</ul>

			{#each lp.data.riwayat ?? [] as p (p.pool + String(p.umur_jam))}
				{@const h = p.hitung ?? {}}
				<div class="mt-2 rounded border border-line p-2">
					<div class="flex flex-wrap items-baseline gap-2">
						<span class="angka text-13 text-text">{p.pasangan ?? '—'}</span>
						<span class="text-11 text-text-3">{p.dex ?? '—'}</span>
						{#if h.menang}
							<span
								class="angka text-12 {h.menang === 'LP'
									? 'text-pos'
									: h.menang === 'hold'
										? 'text-neg'
										: 'text-text-3'}"
							>
								{h.menang === 'LP' ? 'LP menang' : h.menang === 'hold' ? 'hold lebih untung' : 'seri'}
							</span>
						{/if}
					</div>
					<p class="angka mt-1 text-12 text-text-2">
						kaki base {pct(h.kenaikan_base_pct)} · kaki quote {pct(h.kenaikan_quote_pct)}
						{#if h.jumlah_kedua_kaki_naik}
							<span class="text-pos">· kedua kaki naik (fee masuk)</span>
						{/if}
					</p>
					{#if h.il_vs_hold_pct != null}
						<p class="angka text-12 text-text-2">
							imbal hasil tertimbang {pct(h.imbal_hasil_tertimbang_pct)} vs hold {pct(
								h.imbal_hasil_hold_pct
							)}
							→ <b class={h.il_vs_hold_pct < 0 ? 'text-neg' : 'text-pos'}>{pct(h.il_vs_hold_pct)}</b>
							<span class="text-11 text-text-3">(selisih LP vs hold)</span>
						</p>
					{/if}
					{#if h.return_lp_pct != null}
						<p class="angka text-12 text-text-2">
							nilai USD: masuk {usd(h.return_lp_pct != null ? undefined : undefined)} · LP {pct(
								h.return_lp_pct
							)} vs hold {pct(h.return_hold_pct)} → {h.lp_vs_hold_usd != null
								? `$${h.lp_vs_hold_usd.toFixed(2)}`
								: '—'}
						</p>
					{/if}
					{#each h.catatan ?? [] as c}
						<p class="text-11 text-text-3">· {c}</p>
					{/each}
				</div>
			{/each}
		{/if}
	</Block>

	<Block
		judul="Kandidat pool"
		deskripsi="Hasil pencarian — BELUM ada uang di sini; diurutkan berdasarkan volume, bukan likuiditas"
		memuat={memuat}
	>
		{#if !lp || (lp.data.kandidat ?? []).length === 0}
			<p class="text-12 text-text-3">Tidak ada kandidat (pencarian opsional — posisi tetap tampil).</p>
		{:else}
			<ul class="space-y-2">
				{#each lp.data.kandidat ?? [] as k (k.pair + String(k.alamat ?? k.pair))}
					<li class="rounded border border-line p-2">
						<div class="flex flex-wrap items-baseline gap-2">
							<span class="angka text-13 text-text">{k.pair}</span>
							<span class="text-11 text-text-3">{k.dex} {k.label_pool ?? ''} · {k.rantai}</span>
							<span class="angka text-12 {kelasKualitas(k.kualitas)}">{k.kualitas}</span>
						</div>
						<p class="angka text-12 text-text-2">
							volume 24j {usd(k.vol_24h)} · likuiditas {usd(k.liq_usd)} · turnover {k.turnover_24h ??
								'—'}×
							{#if k.chg_h24 != null}· harga 24j {pct(k.chg_h24)}{/if}
						</p>
						{#each k.catatan ?? [] as c}
							<p class="text-11 text-text-3">· {c}</p>
						{/each}
					</li>
				{/each}
			</ul>
		{/if}
		{#if lp}
			{#each lp.data.catatan ?? [] as c}
				<p class="mt-2 text-11 text-text-3">· {c}</p>
			{/each}
			<p class="mt-1 flex items-center gap-2 text-11 text-text-3">
				sumber <span class="angka">{lp.fakta.source}</span>
				<FreshnessBadge
					status={lp.fakta.status}
					age_s={lp.fakta.age_s}
					ttl_s={lp.fakta.ttl_s}
					source={lp.fakta.source}
				/>
			</p>
		{/if}
	</Block>
</div>
