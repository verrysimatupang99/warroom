<script lang="ts">
	// Ringkas — "apa yang berubah & apa yang perlu keputusan". Tiap blok menangani
	// memuat/galat/kosong; angka hanya dari API.
	import { getAlerts, getArea, getAreas, getKesegaran, getKesehatan } from '$lib/api/client';
	import type {
		AlertsPayload,
		AreaPayload,
		Fakta,
		AreasPayload,
		Kesehatan,
		KesegaranPayload
	} from '$lib/api/types';
	import { live } from '$lib/api/live.svelte';
	import { teksNilai, umurDetik, waktuWIB } from '$lib/format';
	import Block from '$lib/components/Block.svelte';
	import DataTable from '$lib/components/DataTable.svelte';
	import EventFeed from '$lib/components/EventFeed.svelte';
	import FreshnessBadge from '$lib/components/FreshnessBadge.svelte';

	let areas = $state<AreasPayload | null>(null);
	let kesegaran = $state<KesegaranPayload | null>(null);
	let sehat = $state<Kesehatan | null>(null);
	let galatAreas = $state<string | null>(null);
	let galatKesegaran = $state<string | null>(null);
	let galatSehat = $state<string | null>(null);
	let alerts = $state<AlertsPayload | null>(null);
	let kripto = $state<AreaPayload | null>(null);
	let galatKripto = $state<string | null>(null);
	let memuat = $state(true);

	async function muat() {
		const [a, k, h, al, kr] = await Promise.allSettled([
			getAreas(),
			getKesegaran(),
			getKesehatan(),
			getAlerts(),
			getArea('crypto')
		]);
		if (a.status === 'fulfilled') {
			areas = a.value;
			galatAreas = null;
		} else galatAreas = (a.reason as Error)?.message ?? String(a.reason);
		if (k.status === 'fulfilled') {
			kesegaran = k.value;
			galatKesegaran = null;
		} else galatKesegaran = (k.reason as Error)?.message ?? String(k.reason);
		if (h.status === 'fulfilled') {
			sehat = h.value;
			galatSehat = null;
		} else galatSehat = (h.reason as Error)?.message ?? String(h.reason);
		if (al.status === 'fulfilled') alerts = al.value;
		if (kr.status === 'fulfilled') {
			kripto = kr.value;
			galatKripto = null;
		} else galatKripto = (kr.reason as Error)?.message ?? String(kr.reason);
		memuat = false;
	}

	/** Sinyal = fakta ber-kind `signal`. Nilai bisa datang sebagai objek atau teks JSON. */
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

	const sinyal = $derived(
		(kripto?.facts ?? [])
			.filter((f: Fakta) => f.kind === 'signal')
			.map((f: Fakta) => ({ f, v: nilaiObj(f.value) ?? {} }))
	);
	const labelSinyal = $derived(
		(sinyal[0]?.v?.label as string | undefined) ??
			'kandidat belum-terbukti — gate statistik belum lolos'
	);

	$effect(() => {
		void muat();
		const t = setInterval(() => void muat(), 15000);
		return () => clearInterval(t);
	});

	const barisMesin = $derived(
		(areas?.areas ?? []).map((a) => ({
			area: a.area,
			fakta: a.fakta,
			hilang: a.hilang,
			basi: a.basi,
			terakhir: a.observed_at_terakhir ? waktuWIB(a.observed_at_terakhir) : '—'
		}))
	);
	const barisSegar = $derived(
		(kesegaran?.facts ?? []).map((f) => ({
			kind: f.kind,
			key: f.key,
			sumber: f.source,
			umur: umurDetik(f.age_s),
			ttl: umurDetik(f.ttl_s),
			status: f.status
		}))
	);
</script>

<div class="space-y-3">
	<div>
		<h1 class="text-19 text-text">Ringkas</h1>
		<p class="text-12 text-text-3">Apa yang berubah &amp; apa yang perlu keputusan.</p>
	</div>

	{#if alerts && alerts.terbuka > 0}
		<div
			class="rounded-card border border-warn/40 bg-warn/10 px-3 py-2 text-12 text-text-2"
			data-testid="alert-banner"
		>
			<span class="angka text-warn">{alerts.terbuka}</span> alert belum ditangani ·
			{#if alerts.transport.terkonfigurasi}
				transport <span class="angka">{alerts.transport.nama}</span>
			{:else}
				transport <span class="angka">belum diatur</span> — alert hanya tersimpan di DB,
				belum terkirim ke mana pun (lihat <span class="angka">ops/notifier.env.example</span>)
			{/if}
			· <a class="text-accent-2 underline" href="/sistem">buka Sistem</a>
		</div>
	{/if}

	<Block
		judul="Sinyal atau diam"
		deskripsi="Hanya setup yang lulus SEMUA gate yang terbit — sisanya diam, dan itu disengaja"
		memuat={memuat && !kripto}
		galat={galatKripto}
	>
		{#if sinyal.length === 0}
			<p class="text-13 text-text-2">
				<span class="angka text-accent-2">diam</span> — tidak ada setup yang lulus semua gate dalam
				jendela terakhir.
			</p>
			<p class="mt-1 text-12 text-text-3">
				Diam bukan kegagalan: memaksa sinyal saat tidak ada setup adalah cara kehilangan uang.
				Setiap sinyal yang terbit membawa entry, SL struktural, TP, dan alasan.
			</p>
		{:else}
			<ul class="space-y-2">
				{#each sinyal as s (s.f.key + String(s.v.diambil ?? s.f.fact_id))}
					<li class="rounded border border-line p-2">
						<div class="flex flex-wrap items-baseline gap-2">
							<span class="angka text-13 text-text">{s.f.key}</span>
							<span class="angka {s.v.arah === 'LONG' ? 'text-pos' : 'text-neg'}"
								>{s.v.arah}</span
							>
							<span class="text-11 text-text-3">tier {s.v.tier ?? '—'}</span>
						</div>
						<p class="angka text-12 text-text-2">
							entry {s.v.entry ?? '—'} · SL {s.v.sl ?? '—'} · TP1 {s.v.tp1 ?? '—'}{#if s.v.risk_pct != null}
								· risiko {s.v.risk_pct}%{/if}
						</p>
						{#if s.v.aturan_gagal && (s.v.aturan_gagal as string[]).length}
							<p class="text-11 text-text-3">
								aturan belum lulus: {(s.v.aturan_gagal as string[]).join(', ')}
							</p>
						{/if}
						<p class="mt-1 flex flex-wrap items-center gap-2 text-11 text-text-3">
							<span>sumber <span class="angka">{s.f.source}</span></span>
							<FreshnessBadge
								status={s.f.status}
								age_s={s.f.age_s}
								ttl_s={s.f.ttl_s}
								source={s.f.source}
							/>
						</p>
					</li>
				{/each}
			</ul>
		{/if}
		<p class="mt-2 text-11 text-text-3">
			<span class="angka">{labelSinyal}</span> ·
			<a class="text-accent-2 underline" href="/bukti">bukti &amp; batas kami</a>
		</p>
	</Block>

	<Block judul="Status layanan" deskripsi="Dari /api/v1/health" memuat={memuat && !sehat} galat={galatSehat}>
		<div class="angka grid gap-2 text-13 sm:grid-cols-2 lg:grid-cols-4">
			<p><span class="label-mikro block">status</span>{sehat?.status ?? '—'}</p>
			<p><span class="label-mikro block">db</span>{sehat ? (sehat.db ? 'ok' : 'gagal') : '—'}</p>
			<p><span class="label-mikro block">waktu server</span>{sehat ? waktuWIB(sehat.time) : '—'}</p>
			<p><span class="label-mikro block">pengguna</span>{sehat?.user ?? '—'}</p>
		</div>
	</Block>

	<Block
		judul="Peta mesin"
		deskripsi="Jumlah fakta, kunci hilang, dan yang basi per area"
		memuat={memuat && !areas}
		galat={galatAreas}
		kosong={!!areas && areas.areas.length === 0}
		kosongPesan="Registry area kosong."
	>
		<DataTable
			kolom={[
				{ kunci: 'area', label: 'area' },
				{ kunci: 'fakta', label: 'fakta', numerik: true },
				{ kunci: 'hilang', label: 'hilang', numerik: true },
				{ kunci: 'basi', label: 'basi', numerik: true },
				{ kunci: 'terakhir', label: 'terakhir' }
			]}
			baris={barisMesin}
			cari="cari area…"
			ekspor="ringkas-peta-mesin.csv"
		/>
	</Block>

	<Block
		judul="Kesegaran"
		deskripsi={`${kesegaran?.count ?? 0} fakta · dicek ${kesegaran ? waktuWIB(kesegaran.checked_at) : '—'}`}
		memuat={memuat && !kesegaran}
		galat={galatKesegaran}
		kosong={!!kesegaran && kesegaran.facts.length === 0}
		kosongPesan="Belum ada fakta yang dipublikasikan."
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
			baris={barisSegar}
			cari="cari kunci/sumber…"
			ekspor="ringkas-kesegaran.csv"
		/>
	</Block>

	<Block
		judul="Antrean keputusan"
		deskripsi="Alert & usulan parameter dari event log"
	>
		<EventFeed
			kejadian={live.berdasarkanTopik(['alert.', 'proposal.', 'param.'])}
			memuat={live.status === 'menyambung'}
			galat={live.pesan}
			prefiksAwal={['alert']}
		/>
	</Block>

	<Block judul="Timeline" deskripsi="20+ kejadian terbaru (SSE, tanpa reload)">
		<EventFeed kejadian={live.kejadian} memuat={live.status === 'menyambung'} galat={live.pesan} />
	</Block>
</div>