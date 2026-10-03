<script lang="ts">
	// Halaman area generik (5 area data): sub-nav + blok per fakta + tabel fakta + feed kejadian
	// + gate bila datanya ada. Semua blok punya state kosong/basi/error lewat <Block>.
	import { AREAS } from '$lib/nav';
	import { page } from '$app/state';
	import { live } from '$lib/api/live.svelte';
	import { teksNilai, umurDetik } from '$lib/format';
	import AreaLoader from './AreaLoader.svelte';
	import Block from './Block.svelte';
	import SubNav from './SubNav.svelte';
	import NilaiFakta from './NilaiFakta.svelte';
	import DataTable from './DataTable.svelte';
	import EventFeed from './EventFeed.svelte';
	import GateBlok from './GateBlok.svelte';
	import DatasetExplorer from './DatasetExplorer.svelte';

	interface Props {
		kunci: string;
	}
	let { kunci }: Props = $props();

	const area = $derived(AREAS.find((a) => a.kunci === kunci)!);
	let sub = $state(page.url.searchParams.get('sub') ?? area.anak[0]?.slug ?? '');
	const anak = $derived(area.anak.find((a) => a.slug === sub) ?? area.anak[0] ?? null);

	const topikArea: Record<string, string[]> = {
		crypto: ['signal.', 'verdict.', 'trade.', 'gate.', 'llm.'],
		idx: ['signal.', 'alert.'],
		forex: ['signal.', 'alert.'],
		polymarket: ['verdict.', 'gate.', 'trade.', 'alert.'],
		gmgn: ['signal.', 'trade.', 'alert.']
	};

	// Gate ditampilkan untuk area yang keputusannya memang lewat gate.
	const tampilGate = $derived(['polymarket', 'crypto', 'idx'].includes(kunci));

	const kolomFakta = [
		{ kunci: 'kunci', label: 'kunci' },
		{ kunci: 'nilai', label: 'nilai' },
		{ kunci: 'sumber', label: 'sumber' },
		{ kunci: 'umur', label: 'umur' },
		{ kunci: 'status', label: 'status' }
	];
</script>

<div class="space-y-3">
	<div>
		<h1 class="text-19 text-text">{area.label}</h1>
		<p class="text-12 text-text-3">Satu layar = satu keputusan; detail masuk drawer.</p>
	</div>

	{#if anak}
		<SubNav {area} aktif={sub} onpilih={(s) => (sub = s)} />
	{/if}

	<AreaLoader area={kunci}>
		{#snippet children(data)}
			{@const faktaTerpilih = anak && anak.kunci.length
				? data.facts.filter((f) => anak.kunci.includes(f.key))
				: data.facts}
			{@const datasetRecorder =
				data.facts.find((f) => f.kind === 'poly.dataset' && f.key === 'recorder') ?? null}
			{@const datasetCakupan =
				data.facts.find((f) => f.kind === 'poly.akses' && f.key === 'cakupan') ?? null}
			{@const barisFakta = data.facts.map((f) => ({
				kunci: f.key,
				nilai: teksNilai(f.value).slice(0, 100),
				sumber: f.source,
				umur: umurDetik(f.age_s),
				status: f.status
			}))}

			{#if anak}
				<p class="text-12 text-text-3">{anak.label} — {anak.catatan}</p>
			{/if}

			{#if data.kunci_hilang && data.kunci_hilang.length}
				<Block
					judul="Kunci belum ada"
					deskripsi="Area ini menunggu fakta yang belum pernah dipublikasikan."
				>
					<p class="angka text-13 text-text-2">
						{kunci} → kunci_hilang: {data.kunci_hilang.join(', ')}
					</p>
				</Block>
			{/if}

			{#if kunci === 'polymarket' && sub === 'dataset'}
				<Block
					judul="Katalog dataset"
					deskripsi="poly.dataset/recorder + poly.akses/cakupan — angka apa adanya dari job poly-sync"
					sumber={datasetRecorder?.source ?? null}
					age_s={datasetRecorder?.age_s ?? null}
					status={datasetRecorder?.status ?? null}
				>
					<DatasetExplorer recorder={datasetRecorder} cakupan={datasetCakupan} />
				</Block>
			{/if}

			{#if faktaTerpilih.length === 0}
				<Block judul={`Blok ${anak?.label ?? area.label}`} kosong
					kosongPesan="Belum ada fakta untuk sub ini. Tampilkan —, bukan 0." />
			{:else}
				{#each faktaTerpilih as f (f.key)}
					<Block judul={f.key} deskripsi={`kind ${f.kind}`} sumber={f.source} age_s={f.age_s} status={f.status}>
						<NilaiFakta fakta={f} />
					</Block>
				{/each}
			{/if}

			{#if tampilGate}
				<Block
					judul="Gate"
					deskripsi="Keputusan lolos hanya bila batas bawah CI > BE (ADR-003)."
				>
					<GateBlok {data} />
				</Block>
			{/if}

			<Block judul="Fakta area" deskripsi={`${data.facts.length} fakta · sumber & umur ditampilkan apa adanya`}>
				<DataTable
					kolom={kolomFakta}
					baris={barisFakta}
					cari="cari kunci/nilai/sumber…"
					ekspor={`${kunci}-fakta.csv`}
				/>
			</Block>

			<Block judul="Kejadian" deskripsi="Aliran SSE; bila putus otomatis fallback polling 15 dtk.">
				<EventFeed
					kejadian={live.berdasarkanTopik(topikArea[kunci] ?? [])}
					memuat={live.status === 'menyambung'}
					galat={live.pesan}
				/>
			</Block>
		{/snippet}
	</AreaLoader>
</div>