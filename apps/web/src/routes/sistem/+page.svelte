<script lang="ts">
	// Sistem & AI: sub-nav 7 bagian. Bagian yang belum punya endpoint menampilkan EmptyState
	// jujur (bukan angka/teks karangan).
	import {
		ackAlert,
		applyProposal,
		getAiConsole,
		getAlerts,
		getAku,
		getAreas,
		getArea,
		getAreaFakta,
		getKesegaran,
		getKesehatan,
		getMetrikTeks,
		getProposals,
		rollbackProposal
	} from '$lib/api/client';
	import type {
		LlmConsole,
		AlertsPayload,
		Me,
		AreasPayload,
		Health,
		FreshnessPayload,
		Proposal
	} from '$lib/api/types';
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { live } from '$lib/api/live.svelte';
	import { AREAS } from '$lib/nav';
	import { teksNilai, umurDetik, waktuWIB } from '$lib/format';
	import Block from '$lib/components/Block.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import SubNav from '$lib/components/SubNav.svelte';
	import DataTable from '$lib/components/DataTable.svelte';
	import EventFeed from '$lib/components/EventFeed.svelte';
	import ProposalCard from '$lib/components/ProposalCard.svelte';

const area = AREAS.find((a) => a.kunci === 'sistem')!;
// URL = satu-satunya sumber kebenaran (SSOT), sama seperti AreaView & riset
// (10 Okt 2026). Dulu `sub` disimpan sebagai $state dengan efek sinkron satu arah
// tanpa cabang else, sehingga Back ke URL tanpa `?sub=` membuat tab macet di nilai
// sebelumnya — URL dan isi saling tak cocok. Turunan ini menghapus kelas bug itu.
const sub = $derived.by(() => {
	const s = page.url.searchParams.get('sub');
	if (s && area.anak.some((a) => a.slug === s)) return s;
	return 'layanan';
});

function pilihSub(s: string) {
	// replaceState:true — ganti tab tak menumpuk riwayat; Back selalu keluar halaman,
	// seragam dengan AreaView & riset.
	if (typeof window !== 'undefined') {
		void goto(`?sub=${s}`, { replaceState: true, keepFocus: true, noScroll: true });
	}
}

	let areas = $state<AreasPayload | null>(null);
	let kesegaran = $state<FreshnessPayload | null>(null);
	let sehat = $state<Health | null>(null);
	let metrik = $state<string | null>(null);
	let galatMetrik = $state<string | null>(null);
	let aiKonsol = $state<LlmConsole | null>(null);
	let alerts = $state<AlertsPayload | null>(null);
	let aku = $state<Me | null>(null);
	let proposals = $state<Proposal[] | null>(null);
	// Fact `lpagent` (kind sendiri) — dari /api/v1/areas/sistem. Telemetri pool
	// Solana/Meteora via LP Agent Open API; tanpa kunci isinya jujur 'menunggu-kunci'.
	let lpagent = $state<Record<string, any> | null>(null);
	// Fact `paper20/dompet` — diterbitkan siklus ops/paper20_cycle.py tiap 15 menit.
	// Angka NYATA dompet uji $20 (equity, posisi terbuka); kosong = pesan 'menunggu'.
	let paper20 = $state<Record<string, any> | null>(null);
	// Feed AXYNODE — sumber publik (funding perp seluruh simbol + FNG), per jam.
	let axynode = $state<Record<string, any> | null>(null);
	let aksiGalat = $state<string | null>(null);
	let memuat = $state(true);

	async function muat() {
		const [a, k, h, c, al, ak, pr] = await Promise.allSettled([
			getAreas(),
			getKesegaran(),
			getKesehatan(),
			getAiConsole(),
			getAlerts(),
			getAku(),
			getProposals()
		]);
		if (a.status === 'fulfilled') areas = a.value;
		if (k.status === 'fulfilled') kesegaran = k.value;
		if (h.status === 'fulfilled') sehat = h.value;
		if (c.status === 'fulfilled') aiKonsol = c.value;
		if (al.status === 'fulfilled') alerts = al.value;
		if (ak.status === 'fulfilled') aku = ak.value;
		if (pr.status === 'fulfilled') proposals = pr.value.proposals;
		// Fact lpagent datang lewat area 'sistem' (kind `lpagent`). Gagal → tetap null,
		// halaman menampilkan 'belum ada fakta', bukan mengarang daftar pool.
		let sys;
		try {
			sys = await getAreaFakta('sistem');
		} catch {
			sys = null;
		}
		try {
			const f = (sys?.facts ?? []).find((x: any) => x.key === 'pools');
			lpagent = f ? (f.value as Record<string, any>) : null;
			const p = (sys?.facts ?? []).find(
				(x: any) => x.kind === 'paper20' && x.key === 'dompet'
			);
			paper20 = p ? (p.value as Record<string, any>) : null;
			const ax = (sys?.facts ?? []).find((x: any) => x.kind === 'axynode' && x.key === 'ringkas');
			axynode = ax ? (ax.value as Record<string, any>) : null;
		} catch {
			lpagent = null;
			paper20 = null;
		}
		try {
			metrik = await getMetrikTeks();
			galatMetrik = null;
		} catch (e) {
			galatMetrik = e instanceof Error ? e.message : String(e);
		}
		memuat = false;
	}

	$effect(() => {
		void muat();
		const t = setInterval(() => void muat(), 15000);
		return () => clearInterval(t);
	});

	// /metrics Prometheus → baris tabel. Baris tak terurai diabaikan (jujur, bukan tebakan).
	const barisMetrik = $derived.by(() => {
		if (!metrik) return [];
		const out: { nama: string; label: string; nilai: string }[] = [];
		for (const baris of metrik.split('\n')) {
			if (!baris || baris.startsWith('#')) continue;
			const m = baris.match(/^([a-zA-Z_:][a-zA-Z0-9_:]*)(\{[^}]*\})?\s+(.+?)\s*$/);
			if (m) out.push({ nama: m[1], label: m[2] ?? '', nilai: m[3] });
		}
		return out;
	});
	const barisLlm = $derived(barisMetrik.filter((m) => m.nama.includes('llm')));
	const barisBiaya = $derived(
		barisMetrik.filter((m) => /quota|biaya|cost|token|arjum|llm/.test(m.nama))
	);
	const barisAudit = $derived(
		(kesegaran?.facts ?? []).map((f) => ({
			kind: f.kind,
			key: f.key,
			sumber: f.source,
			umur: umurDetik(f.age_s),
			status: f.status
		}))
	);
</script>

<div class="space-y-4">
	<!-- Kepala halaman: eyebrow mono + judul + honesty-tag status db -->
	<PageHeader
		eyebrow="OPERASI / SISTEM"
		title="Sistem & AI"
		terverifikasi={sehat ? sehat.db : null}
		sumber={sehat ? '/api/v1/health' : null}
		alasan="health tidak terbaca"
		description="Unit lintas host, kesegaran, biaya, event, AI, kebijakan, audit."
	/>

	<SubNav {area} aktif={sub} onpilih={pilihSub} />

	{#if sub === 'layanan'}
		<Block judul="Layanan" deskripsi="/api/v1/health + registry area" memuat={memuat && !sehat}>
			<div class="angka grid gap-2 text-13 sm:grid-cols-2 lg:grid-cols-4">
				<p><span class="label-mikro block">status</span>{sehat?.status ?? '—'}</p>
				<p><span class="label-mikro block">db</span>{sehat ? (sehat.db ? 'ok' : 'gagal') : '—'}</p>
				<p><span class="label-mikro block">waktu</span>{sehat ? waktuWIB(sehat.time) : '—'}</p>
				<p><span class="label-mikro block">pengguna</span>{sehat?.user ?? '—'}</p>
			</div>
		</Block>
		<!-- Populasi tabel Area = fakta snapshot yang DIPAKAI tiap area (kunci dipakai
		     beberapa area terhitung ganda; fakta signal kind lain tidak masuk). Populasi
		     header/segar-total-basi ada di tab Kesegaran. Temuan QA 15 Okt. -->
		<p class="mb-2 text-11 text-text-3">
			Tabel ini = fakta snapshot yang <b>dipakai tiap area</b> (satu kunci bisa dipakai
			beberapa area terhitung ganda; fakta <span class="angka">signal</span> kind lain tidak
			masuk). Populasi header (segar/total/basi) ada di tab Kesegaran.
		</p>
		<Block judul="Area" memuat={memuat && !areas}>
			<DataTable
				kolom={[
					{ kunci: 'area', label: 'area' },
					{ kunci: 'fakta', label: 'fakta', numerik: true },
					{ kunci: 'hilang', label: 'hilang', numerik: true },
					{ kunci: 'basi', label: 'basi', numerik: true },
					{ kunci: 'source_state', label: 'sumber' }
				]}
				baris={(areas?.areas ?? []).map((a) => ({
					area: a.area,
					fakta: a.fakta,
					hilang: a.hilang,
					basi: a.basi,
					source_state: a.source_state
				}))}
				cari="cari area…"
				ekspor="sistem-area.csv"
			/>
		</Block>
	{:else if sub === 'mesin'}
		<!-- Mesin = sumber data PIHAK KETIGA (bukan berkas lokal). Saat ini LP Agent
		     (telemetri pool Solana/Meteora). Fact `lpagent` diterbitkan job
		     `lpagent-sync`; tanpa kunci isinya jujur 'menunggu-kunci' — halaman ini
		     menampilkan apa adanya, tidak pernah mengarang daftar pool. -->
		{#if paper20}
			<!-- Dompet uji $20 (crypto) — angka NYATA dari ledger siklus paper20.
			     Antislop R-17/R-27: hanya angka nyata, dan jika kosong pesannya
			     "menunggu sinyal" bareng tindakan berikutnya, bukan "tidak ada data". -->
			<Block
				judul="Dompet uji $20 · crypto"
				deskripsi={`siklus 15 menit · diperiksa ${paper20.updated ?? '—'} WIB`}
				memuat={memuat && !paper20}
			>
				<div class="grid grid-cols-3 gap-2 text-12">
					<div class="rounded border border-line bg-surface p-2">
						<span class="text-10 uppercase text-text-3">Equity</span>
						<div class="angka text-15 font-bold">${paper20.equity_usd ?? '—'}</div>
					</div>
					<div class="rounded border border-line bg-surface p-2">
						<span class="text-10 uppercase text-text-3">Posisi terbuka</span>
						<div class="angka text-15 font-bold">{paper20.n_posisi ?? 0}</div>
					</div>
					<div class="rounded border border-line bg-surface p-2">
						<span class="text-10 uppercase text-text-3">Verdict</span>
						<div class="angka text-15 font-bold">{paper20.jumlah_verdict ?? 0}</div>
					</div>
				</div>
				{#if paper20.posisi?.length}
					<div class="mt-2 space-y-1">
						{#each paper20.posisi as p}
							<div class="flex justify-between rounded border border-line-soft bg-surface px-2 py-1 font-mono text-11">
								<span class="text-text">{p.pair} {p.arah ?? ''}</span>
								<span class="angka text-text-3">entry {p.entry} · SL {p.sl} · ${p.size_usd}</span>
							</div>
						{/each}
					</div>
				{:else}
					<p class="mt-2 text-11 text-text-3">
						0 posisi — mesin menunggu sinyal yang lolos gerbang struktur + risiko
						(jarak SL vs ATR masih penolak terbanyak). Verifikasi manual:
						<code class="font-mono">lt paper list --venue crypto</code>
					</p>
				{/if}
				<p class="mt-2 text-10 text-text-3">diperiksa {paper20.updated ?? '—'} WIB</p>
				</Block>
				{/if}
				{#if axynode}
				<!-- Feed pasar eksternal AXYNODE — sumber publik (fapi Binance funding+perp,
				alternative.me FNG) tanpa kunci; siklus ops/axynode_sinkron.py per jam. -->
				<Block
				judul="AXYNODE · pasar eksternal (funding &amp; FNG)"
				deskripsi={axynode.sumber ? axynode.sumber.join(' · ') : 'sumber publik'}
				memuat={memuat && !axynode}
				>
				<div class="grid grid-cols-3 gap-2 text-12">
					<div class="rounded border border-line bg-surface p-2">
						<span class="block text-10 uppercase text-text-3">Fear &amp; Greed</span>
						<span class="angka text-15 font-bold" class:text-warn={axynode.data?.fng?.nilai < 40} class:text-pos={axynode.data?.fng?.nilai > 60}>
							{axynode.data?.fng?.nilai ?? '—'} {axynode.data?.fng?.label ?? ''}
						</span>
					</div>
					<div class="rounded border border-line bg-surface p-2">
						<span class="block text-10 uppercase text-text-3">Rata funding</span>
						<span class="angka text-15 font-bold">
							{axynode.data?.funding?.rata_semua != null ? `${axynode.data.funding.rata_semua}%` : '—'}
						</span>
					</div>
					<div class="rounded border border-line bg-surface p-2">
						<span class="block text-10 uppercase text-text-3">Simbol perp likuid</span>
						<span class="angka text-15 font-bold">{axynode.data?.funding?.jumlah_simbol ?? '—'}</span>
					</div>
				</div>
				{#if axynode.data?.funding?.ekstrem?.length}
					<div class="mt-2 space-y-1">
						{#each axynode.data.funding.ekstrem.slice(0, 5) as f}
							<div class="flex justify-between rounded border border-line-soft bg-surface px-2 py-1 font-mono text-11">
								<span class="text-text">{f.simbol}</span>
								<span class={f.funding_pct > 0 ? 'angka text-pos' : 'angka text-neg'}>
									{f.funding_pct > 0 ? '+' : ''}{f.funding_pct}%
								</span>
							</div>
						{/each}
					</div>
				{/if}
				<p class="mt-2 text-10 text-text-3">diperiksa {axynode.updated ?? '—'} UTC · sumber publik tanpa kunci</p>
				</Block>
				{/if}
				{#if lpagent}
			<Block
				judul="LP Agent · likuiditas Solana (Meteora)"
				deskripsi={lpagent.sumber ?? 'LP Agent Open API'}
				memuat={memuat && !lpagent}
			>
				<div
					class="rounded-card border p-3 {lpagent.tersedia ? 'border-line' : 'border-warn/40 bg-warn/5'}"
				>
					<div class="flex flex-wrap items-center gap-2">
						<span
							class="rounded border px-1.5 py-0.5 text-10 font-bold {lpagent.tersedia
								? 'border-pos/40 bg-pos/10 text-pos'
								: 'border-warn/40 bg-warn/10 text-warn'}"
						>
							{lpagent.tersedia ? 'AKTIF' : 'MENUNGGU KUNCI'}
						</span>
						<span class="font-mono text-11 text-text-3">{lpagent.status}</span>
						{#if lpagent.tersedia}
							<span class="angka text-11 text-text-2">{lpagent.n ?? 0} pool</span>
						{/if}
					</div>
					{#if !lpagent.tersedia}
						<p class="mt-2 text-12 text-text-2">
							Belum ada data pool — <b>dan itu jujur</b>, bukan nol yang menyamar sebagai
							"tidak ada peluang". Sebabnya:
						</p>
						<p class="mt-1 text-11 text-text-3">{lpagent.sebab}</p>
					{/if}
					<div class="mt-2 grid grid-cols-2 gap-2 text-11 sm:grid-cols-4">
						<div>
							<span class="label-mikro block">sumber</span>
							<span class="text-text-2">API pihak ketiga</span>
						</div>
						<div>
							<span class="label-mikro block">base url</span>
							<span class="font-mono text-10 text-text-3">{lpagent.base_url ?? '—'}</span>
						</div>
						<div>
							<span class="label-mikro block">jalur uang</span>
							<span class="text-neg">terkunci</span>
						</div>
						<div>
							<span class="label-mikro block">snapshot</span>
							<span class="text-text-2">{lpagent.frekuensi_snapshot ?? 'tiap 30 menit'}</span>
						</div>
					</div>
					<p class="mt-2 text-10 text-text-3">
						Baca-saja (endpoint GET). Jalur bangun transaksi (zap-in/zap-out, Jito) <b>TIDAK
						dipanggil</b> — gerbang live tetap <span class="angka">armed=false</span>. Ini telemetri
						pool, bukan sinyal beli.
					</p>
				</div>
				{#if lpagent.tersedia && (lpagent.pools ?? []).length > 0}
					<DataTable
						kolom={[
							{ kunci: 'token0', label: 'token0' },
							{ kunci: 'token1', label: 'token1' },
							{ kunci: 'protocol', label: 'protokol' },
							{ kunci: 'tvl', label: 'tvl', numerik: true },
							{ kunci: 'vol_24h', label: 'vol 24j', numerik: true },
							{ kunci: 'fee_24h', label: 'fee 24j', numerik: true },
							{ kunci: 'organic_score', label: 'organik', numerik: true },
							{ kunci: 'bin_step', label: 'bin step', numerik: true }
						]}
						baris={lpagent.pools.map((p: any) => ({
							token0: p.token0 ?? '—',
							token1: p.token1 ?? '—',
							protocol: p.protocol ?? '—',
							tvl: p.tvl ?? '—',
							vol_24h: p.vol_24h ?? '—',
							fee_24h: p.fee_24h ?? '—',
							organic_score: p.organic_score ?? '—',
							bin_step: p.bin_step ?? '—'
						}))}
						cari="cari pool…"
						ekspor="sistem-lpagent.csv"
						padat
					/>
				{/if}
			</Block>
		{:else}
			<Block judul="LP Agent · likuiditas Solana (Meteora)" memuat={memuat}>
				<p class="text-13 text-text-2">
					Belum ada fakta <span class="angka">lpagent</span>. Job
					<span class="angka">lpagent-sync</span> menerbitkannya tiap 30 menit — halaman ini
					tidak mengarang data pool.
				</p>
			</Block>
		{/if}
	{:else if sub === 'kesegaran'}
		<Block
			judul="Matriks kesegaran"
			deskripsi={`${kesegaran?.count ?? 0} fakta — semua kind, sumber angka header · dicek ${kesegaran ? waktuWIB(kesegaran.checked_at) : '—'}`}
			memuat={memuat && !kesegaran}
			kosong={!!kesegaran && kesegaran.facts.length === 0}
			kosongPesan="Belum ada fakta."
		>
			<DataTable
				kolom={[
					{ kunci: 'kind', label: 'kind' },
					{ kunci: 'key', label: 'kunci' },
					{ kunci: 'sumber', label: 'sumber' },
					{ kunci: 'umur', label: 'umur' },
					{ kunci: 'ttl', label: 'ttl' },
					{ kunci: 'status', label: 'status' }
				]}
				baris={(kesegaran?.facts ?? []).map((f) => ({
					kind: f.kind,
					key: f.key,
					sumber: f.source,
					umur: umurDetik(f.age_s),
					ttl: umurDetik(f.ttl_s),
					status: f.status
				}))}
				cari="cari kunci…"
				ekspor="sistem-kesegaran.csv"
			/>
		</Block>
	{:else if sub === 'biaya'}
		<Block
			judul="Biaya &amp; kuota"
			deskripsi="Angka dari /metrics; metrik yang tidak ada tidak ditampilkan"
			memuat={memuat && !metrik}
			galat={galatMetrik}
			kosong={barisBiaya.length === 0}
			kosongPesan="Tidak ada metrik biaya/kuota di /metrics saat ini."
		>
			<DataTable
				kolom={[
					{ kunci: 'nama', label: 'metrik' },
					{ kunci: 'label', label: 'label' },
					{ kunci: 'nilai', label: 'nilai' }
				]}
				baris={barisBiaya}
				cari="cari metrik…"
				ekspor="sistem-biaya.csv"
				padat
			/>
		</Block>
	{:else if sub === 'event'}
		<Block
			judul="Alert"
			deskripsi="Terbuka sampai di-ack; transport kosong tidak pernah diklaim terkirim"
			memuat={memuat && !alerts}
			kosong={!alerts || alerts.alerts.length === 0}
			kosongPesan="Tidak ada alert tercatat."
		>
			{#if alerts}
				<p class="mb-2 text-12 text-text-3">
					transport
					<span class="angka">{alerts.transport.terkonfigurasi ? alerts.transport.nama : 'belum diatur'}</span>
					· terbuka <span class="angka">{alerts.terbuka}</span>
					{#if aksiGalat}<span class="text-neg"> · {aksiGalat}</span>{/if}
				</p>
				<DataTable
					kolom={[
						{ kunci: 'id', label: '#' },
						{ kunci: 'severity', label: 'tingkat' },
						{ kunci: 'subject', label: 'subjek' },
						{ kunci: 'aksi', label: 'aksi disarankan' },
						{ kunci: 'umur', label: 'umur' },
						{ kunci: 'percobaan', label: 'percobaan' },
						{ kunci: 'status', label: 'status' }
					]}
					baris={alerts.alerts.map((a) => ({
						id: a.id,
						severity: a.severity,
						subject: a.subject,
						aksi: a.suggested_action || '—',
						umur: umurDetik((Date.now() - Date.parse(a.created_at)) / 1000),
						percobaan: a.percobaan,
						status: a.ack_at
							? 'ack'
							: a.snooze_until
								? `tunda s/d ${waktuWIB(a.snooze_until)}`
								: a.percobaan === 0
									? 'terbuka'
									: a.terakhir_ok
										? 'terkirim — belum di-ack'
										: a.percobaan >= 3
											? `macet — ${a.kesalahan_terakhir ?? 'kirim dihentikan'}`
											: `gagal terakhir: ${a.kesalahan_terakhir ?? '—'}`
					}))}
					cari="cari alert…"
					ekspor="sistem-alert.csv"
					padat
				/>
				{#if aku && (aku.role === 'operator' || aku.role === 'owner')}
					<div class="mt-2 flex flex-wrap gap-2">
						{#each alerts.alerts.filter((a) => !a.ack_at).slice(0, 5) as a (a.id)}
							<span class="label-mikro">#{a.id}</span>
							<button
								class="rounded-control border border-line px-2 py-0.5 text-11 text-text-2"
								onclick={async () => {
									try {
										await ackAlert(a.id, 0);
										aksiGalat = null;
									} catch (e) {
										aksiGalat = e instanceof Error ? e.message : String(e);
									}
									await muat();
								}}>ack</button
							>
							<button
								class="rounded-control border border-line px-2 py-0.5 text-11 text-text-2"
								onclick={async () => {
									try {
										await ackAlert(a.id, 3600);
										aksiGalat = null;
									} catch (e) {
										aksiGalat = e instanceof Error ? e.message : String(e);
									}
									await muat();
								}}>tunda 1j</button
							>
						{/each}
					</div>
				{/if}
			{/if}
		</Block>
		<Block judul="Event log" deskripsi="SSE; gagal → polling 15 dtk">
			<EventFeed kejadian={live.kejadian} memuat={live.status === 'menyambung'} galat={live.pesan} />
		</Block>
	{:else if sub === 'ai'}
		<Block
			judul="Health provider"
			deskripsi="Dari llm_calls — provider mana yang gagal, kode apa, seberapa lambat"
			memuat={memuat && !aiKonsol}
			kosong={!aiKonsol || aiKonsol.per_provider.length === 0}
			kosongPesan="Belum ada panggilan LLM tercatat di llm_calls."
		>
			{#if aiKonsol}
				<p class="mb-2 text-12 text-text-3">
					<span class="angka">{aiKonsol.total_panggilan}</span> panggilan · fallback
					<span class="angka"
						>{aiKonsol.fallback_rate != null
							? `${(aiKonsol.fallback_rate * 100).toFixed(1)}%`
							: 'n/a'}</span
					> · biaya <span class="angka">${aiKonsol.biaya_usd.toFixed(2)}</span> —
					{aiKonsol.catatan}
				</p>
				<DataTable
					kolom={[
						{ kunci: 'provider', label: 'provider' },
						{ kunci: 'n', label: 'n' },
						{ kunci: 'ok', label: 'ok' },
						{ kunci: 'ok_rate', label: 'ok rate' },
						{ kunci: 'gagal', label: 'gagal' },
						{ kunci: 'fallback', label: 'fallback' },
						{ kunci: 'p95_ms', label: 'p95 ms' },
						{ kunci: 'error_terakhir', label: 'error terakhir' }
					]}
					baris={aiKonsol.per_provider.map((p) => ({
						provider: p.provider,
						n: p.n,
						ok: p.ok,
						ok_rate: p.ok_rate != null ? `${(p.ok_rate * 100).toFixed(1)}%` : 'n/a',
						gagal: p.gagal,
						fallback: p.fallback,
						p95_ms: p.p95_ms != null ? Math.round(p.p95_ms) : 'n/a',
						error_terakhir: p.error_terakhir ?? '—'
					}))}
					cari="cari provider…"
					ekspor="sistem-provider.csv"
					padat
				/>
			{/if}
		</Block>
		<Block
			judul="LLMConsole"
			deskripsi="Health provider, latensi, biaya, fallback"
			memuat={memuat && !metrik}
			galat={galatMetrik}
			kosong={barisLlm.length === 0}
			kosongPesan="Belum ada metrik llm_* di /metrics; endpoint services/llm belum diekspos API ini."
		>
			<DataTable
				kolom={[
					{ kunci: 'nama', label: 'metrik' },
					{ kunci: 'label', label: 'label' },
					{ kunci: 'nilai', label: 'nilai' }
				]}
				baris={barisLlm}
				cari="cari metrik llm…"
				ekspor="sistem-llm.csv"
				padat
			/>
		</Block>
	{:else if sub === 'kebijakan'}
		<Block
			judul="Usulan parameter (otonomi berbatas)"
			deskripsi="Dari tabel proposals — learner mengusul, gate/owner memutuskan; rollback mengembalikan nilai sebelumnya"
			memuat={memuat && !proposals}
			galat={aksiGalat}
			kosong={!!proposals && proposals.length === 0}
			kosongPesan="Belum ada usulan parameter tercatat."
		>
			<ProposalCard
				{proposals}
				memuat={memuat}
				peran={aku?.role ?? null}
				onexec={async (id, aksi) => {
					try {
						if (aksi === 'apply') await applyProposal(id);
						else await rollbackProposal(id);
						aksiGalat = null;
					} catch (e) {
						aksiGalat = e instanceof Error ? e.message : String(e);
					}
					await muat();
				}}
			/>
		</Block>
		<Block judul="Kebijakan" deskripsi="agent-policy.json — tier, red lines, gate">
			<p class="text-13 text-text-2">
				— belum ada endpoint API untuk membaca <span class="angka">agent-policy.json</span> pada
				P2. Halaman ini sengaja tidak mengarang isi kebijakan.
			</p>
		</Block>
	{:else if sub === 'audit'}
		<Block judul="Audit" deskripsi="Jejak perubahan parameter &amp; konfigurasi">
			<EventFeed
				kejadian={live.berdasarkanTopik(['param.', 'policy.', 'proposal.'])}
				memuat={live.status === 'menyambung'}
				galat={live.pesan}
			/>
		</Block>
	{/if}
</div>