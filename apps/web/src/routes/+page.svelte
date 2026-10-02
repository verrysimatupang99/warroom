<script lang="ts">
	// Ringkas — "apa yang berubah & apa yang perlu keputusan". Tiap blok menangani
	// memuat/galat/kosong; angka hanya dari API.
	import { getAreas, getKesegaran, getKesehatan } from '$lib/api/client';
	import type { AreasPayload, Kesehatan, KesegaranPayload } from '$lib/api/types';
	import { live } from '$lib/api/live.svelte';
	import { teksNilai, umurDetik, waktuWIB } from '$lib/format';
	import Block from '$lib/components/Block.svelte';
	import DataTable from '$lib/components/DataTable.svelte';
	import EventFeed from '$lib/components/EventFeed.svelte';

	let areas = $state<AreasPayload | null>(null);
	let kesegaran = $state<KesegaranPayload | null>(null);
	let sehat = $state<Kesehatan | null>(null);
	let galatAreas = $state<string | null>(null);
	let galatKesegaran = $state<string | null>(null);
	let galatSehat = $state<string | null>(null);
	let memuat = $state(true);

	async function muat() {
		const [a, k, h] = await Promise.allSettled([getAreas(), getKesegaran(), getKesehatan()]);
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
		memuat = false;
	}

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