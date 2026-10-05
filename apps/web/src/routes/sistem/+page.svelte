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
		getKesegaran,
		getKesehatan,
		getMetrikTeks,
		getProposals,
		rollbackProposal
	} from '$lib/api/client';
	import type {
		AiConsole,
		AlertsPayload,
		Aku,
		AreasPayload,
		Kesehatan,
		KesegaranPayload,
		Proposal
	} from '$lib/api/types';
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { live } from '$lib/api/live.svelte';
	import { AREAS } from '$lib/nav';
	import { teksNilai, umurDetik, waktuWIB } from '$lib/format';
	import Block from '$lib/components/Block.svelte';
	import SubNav from '$lib/components/SubNav.svelte';
	import DataTable from '$lib/components/DataTable.svelte';
	import EventFeed from '$lib/components/EventFeed.svelte';
	import ProposalCard from '$lib/components/ProposalCard.svelte';

	const area = AREAS.find((a) => a.kunci === 'sistem')!;
	let sub = $state(page.url.searchParams.get('sub') ?? 'layanan');

	$effect(() => {
		const s = page.url.searchParams.get('sub');
		if (s && area.anak.some((a) => a.slug === s)) {
			sub = s;
		}
	});

	function pilihSub(s: string) {
		sub = s;
		if (typeof window !== 'undefined') {
			void goto(`?sub=${s}`, { replaceState: true, keepFocus: true, noScroll: true });
		}
	}

	let areas = $state<AreasPayload | null>(null);
	let kesegaran = $state<KesegaranPayload | null>(null);
	let sehat = $state<Kesehatan | null>(null);
	let metrik = $state<string | null>(null);
	let galatMetrik = $state<string | null>(null);
	let aiKonsol = $state<AiConsole | null>(null);
	let alerts = $state<AlertsPayload | null>(null);
	let aku = $state<Aku | null>(null);
	let proposals = $state<Proposal[] | null>(null);
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
	<div>
		<h1 class="text-19 text-text">Sistem &amp; AI</h1>
		<p class="text-12 text-text-3">Unit lintas host, kesegaran, biaya, event, AI, kebijakan, audit.</p>
	</div>

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
		<Block judul="Area" memuat={memuat && !areas}>
			<DataTable
				kolom={[
					{ kunci: 'area', label: 'area' },
					{ kunci: 'fakta', label: 'fakta', numerik: true },
					{ kunci: 'hilang', label: 'hilang', numerik: true },
					{ kunci: 'basi', label: 'basi', numerik: true }
				]}
				baris={(areas?.areas ?? []).map((a) => ({
					area: a.area,
					fakta: a.fakta,
					hilang: a.hilang,
					basi: a.basi
				}))}
				cari="cari area…"
				ekspor="sistem-area.csv"
			/>
		</Block>
	{:else if sub === 'kesegaran'}
		<Block
			judul="Matriks kesegaran"
			deskripsi={`${kesegaran?.count ?? 0} fakta · dicek ${kesegaran ? waktuWIB(kesegaran.checked_at) : '—'}`}
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
			judul="Kesehatan provider"
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
			deskripsi="Kesehatan provider, latensi, biaya, fallback"
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