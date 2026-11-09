<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { AREAS, SLUG_LAMA } from '$lib/nav';
	import { urlApi } from '$lib/api/client';
	import MarketShell from '$lib/components/MarketShell.svelte';
	import ServerTencentView from '$lib/components/ServerTencentView.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import Skeleton from '$lib/components/Skeleton.svelte';
	import InfraHealth from '$lib/components/InfraHealth.svelte';

	const area = AREAS.find((a) => a.kunci === 'sistem')!;
	const sub = $derived.by(() => {
		const s = page.url.searchParams.get('sub') ?? 'layanan';
		return SLUG_LAMA[s] ?? s;
	});

	interface Unit { unit?: string; aktif?: string; sub?: string; aktif_sejak?: string }
	interface Berkas { berkas?: string; umur_s?: number; basi?: boolean }
	interface Status { unit_total?: number; unit_sehat?: number; unit?: Unit[]; berkas?: Berkas[]; waktu?: string }

	let status = $state<Status | null>(null);
	let galatStatus = $state<string | null>(null);
	let memuat = $state(true);

	// Status infra lintas mesin (snapshot dari cyber1)
	let infra = $state<Record<string, unknown> | null>(null);
	let galatInfra = $state<string | null>(null);
	let memuatInfra = $state(true);

	let kejadian = $state<Record<string, unknown>[]>([]);
	let galatEvent = $state<string | null>(null);
	let params = $state<Record<string, unknown> | null>(null);

	// Endpoint params membalas {params: [{nama, nilai, batas, scope, catatan, terkunci}]}.
	// Bentuk ini dulu dicetak mentah sebagai JSON; sekarang dibaca sebagai tabel.
	interface Param {
		nama: string;
		nilai: number | string;
		batas?: [number, number];
		scope?: string;
		terkunci?: boolean;
		catatan?: string;
	}

	const daftarParam = $derived<Param[]>(
		Array.isArray((params as { params?: Param[] } | null)?.params)
			? ((params as { params: Param[] }).params ?? [])
			: []
	);
	const jumlahTerkunci = $derived(daftarParam.filter((p) => p.terkunci).length);
	let latensi = $state<{ jalur: string; ms: number; status: number }[]>([]);

	// Waktu respons diukur dari browser ke API, apa adanya. Angka ini yang dirasakan
	// pengguna, bukan angka internal server.
	const UKUR = [
		'/api/v1/health',
		'/api/v1/pasar/ringkas',
		'/api/v1/journal/stats?market=all',
		'/api/v1/sistem/status',
		'/api/v1/kalender/makro?dampak=tinggi&batas=5'
	];

	async function ukurLatensi() {
		const hasil: { jalur: string; ms: number; status: number }[] = [];
		for (const jalur of UKUR) {
			const t0 = performance.now();
			try {
				const r = await fetch(urlApi(jalur), { credentials: 'include' });
				await r.json().catch(() => null);
				hasil.push({ jalur, ms: Math.round(performance.now() - t0), status: r.status });
			} catch {
				hasil.push({ jalur, ms: Math.round(performance.now() - t0), status: 0 });
			}
		}
		latensi = hasil;
	}

	async function ambil<T>(jalur: string): Promise<T | null> {
		try {
			const r = await fetch(urlApi(jalur), { credentials: 'include' });
			const isi = await r.json().catch(() => null);
			if (!r.ok) return null;
			return isi as T;
		} catch {
			return null;
		}
	}

	async function ambilInfra() {
		memuatInfra = true;
		const d = await ambil<Record<string, unknown>>('/api/v1/infra/health');
		if (d) {
			infra = d;
			galatInfra = null;
		} else {
			galatInfra = 'Endpoint infra tidak menjawab.';
		}
		memuatInfra = false;
	}

	onMount(async () => {
		const s = await ambil<Status>('/api/v1/sistem/status');
		if (s) status = s;
		else galatStatus = 'Endpoint status layanan tidak menjawab.';
		const ev = await ambil<{ events?: unknown[]; items?: unknown[] }>('/api/v1/events?limit=12');
		// Endpoint mengembalikan { events: [...] }; jaga juga bentuk list langsung.
		const arr = Array.isArray(ev) ? (ev as unknown[]) : (ev?.events ?? ev?.items ?? []);
		kejadian = (arr as Record<string, unknown>[]).slice(0, 12);
		if (!kejadian.length) galatEvent = 'Belum ada kejadian terekam.';
		params = await ambil<Record<string, unknown>>('/api/v1/params');
		laya = await ambil<LayaPengaturan>('/api/v1/pengaturan/laya');
		void ukurLatensi();
		void ambilInfra();
		memuat = false;
	});

	interface LayaPengaturan {
	aktif?: boolean;
	systemd_timer?: boolean;
	catatan?: string;
	}

	let laya = $state<LayaPengaturan | null>(null);
	let layaPesan = $state<string | null>(null);
	let layaSibuk = $state(false);

	async function toggleLaya() {
		if (layaSibuk) return;
		layaSibuk = true;
		layaPesan = null;
		try {
			const r = await fetch(urlApi('/api/v1/pengaturan/laya'), {
				method: 'POST',
				credentials: 'include',
				headers: { 'content-type': 'application/json' },
				body: JSON.stringify({ aktif: !(laya?.aktif ?? false) })
			});
			const isi = await r.json().catch(() => null);
			if (!r.ok) {
				layaPesan = (isi?.detail as string) ?? `HTTP ${r.status} — hanya owner yang boleh mengubah.`;
			} else {
				laya = { aktif: !!isi?.aktif, systemd_timer: !!isi?.systemd_timer, catatan: laya?.catatan };
				layaPesan = isi?.systemd_ok
					? 'Tersimpan + timer systemd diperbarui.'
					: `Tersimpan, tetapi timer systemd gagal: ${isi?.systemd_detail ?? '?'} — hubungi operator.`;
			}
		} catch (e) {
			layaPesan = e instanceof Error ? e.message : 'gagal menghubungi API';
		}
		layaSibuk = false;
	}
</script>

<svelte:head><title>Sistem | War Room</title></svelte:head>

<MarketShell
	{area}
	aktif={sub}
	judul="Sistem"
	deskripsi="Status layanan, sumber data, kejadian, dan kebijakan yang berlaku. Satu tempat untuk menjawab: apa yang hidup, dari mana angkanya, dan apa batasnya."
	sumber="sistem/status + freshness + events"
>
	{#if sub === 'layanan'}
		{#if memuat}
			<Skeleton baris={4} tinggi={44} />
		{:else if !status}
			<EmptyState judul="Status tidak tersedia" pesan={galatStatus ?? 'Tidak ada jawaban.'} />
		{:else}
			<div class="space-y-4">
t	<TradingPanel />
				<InfraHealth data={infra} galat={galatInfra} memuat={memuatInfra} onreload={() => void ambilInfra()} />
				<section class="grid gap-3 sm:grid-cols-3">
					<div class="rounded-card border border-line bg-surface p-4">
						<div class="label-mikro font-mono text-text-3">UNIT SEHAT</div>
						<div class="mt-1 font-mono text-17 font-bold text-text">
							{status.unit_sehat ?? 0}<span class="text-13 text-text-3">/{status.unit_total ?? 0}</span>
						</div>
					</div>
					<div class="rounded-card border border-line bg-surface p-4">
						<div class="label-mikro font-mono text-text-3">BERKAS BASI</div>
						<div class="mt-1 font-mono text-17 font-bold text-text">
							{(status.berkas ?? []).filter((b) => b.basi).length}
							<span class="text-13 text-text-3">/{(status.berkas ?? []).length}</span>
						</div>
					</div>
					<div class="rounded-card border border-line bg-surface p-4">
						<div class="label-mikro font-mono text-text-3">DIPERBARUI</div>
						<div class="mt-1 font-mono text-12 text-text">{status.waktu ?? '—'}</div>
					</div>
				</section>

				<section class="rounded-card border border-line bg-surface p-4">
					<div class="flex flex-wrap items-center justify-between gap-2">
						<h2 class="text-13 font-bold text-text">Waktu respons</h2>
						<button
							type="button"
							class="min-h-[44px] rounded-control border border-line px-2.5 font-mono text-11 text-text-3 hover:border-accent hover:text-accent"
							onclick={() => void ukurLatensi()}
						>
							Ukur ulang
						</button>
					</div>
					{#if latensi.length === 0}
						<p class="mt-2 text-11 text-text-3">Mengukur…</p>
					{:else}
						<ul class="mt-2 divide-y divide-line-soft">
							{#each latensi as l (l.jalur)}
								<li class="flex items-center justify-between gap-3 py-1.5 text-11">
									<span class="truncate font-mono text-text-3">{l.jalur}</span>
									<span class="shrink-0 font-mono" class:text-pos={l.status === 200 && l.ms < 400}
										class:text-neg={l.status !== 200 || l.ms >= 400}>
										{l.ms} ms · {l.status}
									</span>
								</li>
							{/each}
						</ul>
						<p class="mt-2 text-11 text-text-3">
							Diukur dari browser ke API. Hijau berarti di bawah 400 ms dan status 200.
						</p>
					{/if}
				</section>

				<section class="rounded-card border border-line bg-surface p-4">
					<h2 class="text-13 font-bold text-text">Unit</h2>
					<div class="mt-2 overflow-x-auto">
						<table class="w-full text-11 text-left">
							<thead class="border-b border-line text-10 text-text-3">
								<tr><th class="px-2 py-1.5">Unit</th><th class="px-2 py-1.5">Status</th><th class="px-2 py-1.5">Sub</th></tr>
							</thead>
							<tbody class="divide-y divide-line-soft">
								{#each status.unit ?? [] as u (u.unit)}
									<tr>
										<td class="px-2 py-1.5 font-mono text-text">{u.unit}</td>
										<td class="px-2 py-1.5 font-mono" class:text-pos={u.aktif === 'active'} class:text-neg={u.aktif !== 'active'}>{u.aktif ?? '—'}</td>
										<td class="px-2 py-1.5 font-mono text-text-3">{u.sub ?? '—'}</td>
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				</section>
			</div>
		{/if}
	{:else if sub === 'data'}
		<ServerTencentView />
	{:else if sub === 'event'}
		<section class="rounded-card border border-line bg-surface p-4">
			<div class="flex flex-wrap items-center justify-between gap-2">
				<h2 class="text-13 font-bold text-text">Kejadian terakhir</h2>
				<span class="font-mono text-11 text-text-3">{kejadian.length} baris</span>
			</div>
			{#if kejadian.length === 0}
				<EmptyState judul="Belum ada kejadian" pesan={galatEvent ?? 'Umpan kejadian kosong.'} ringkas={true} />
			{:else}
				<div class="mt-2 overflow-x-auto">
					<table class="w-full text-11 text-left">
						<thead class="border-b border-line text-10 text-text-3">
							<tr>
								<th class="px-2 py-1.5">Waktu</th>
								<th class="px-2 py-1.5">Jenis</th>
								<th class="px-2 py-1.5">Aktor</th>
								<th class="px-2 py-1.5">Tingkat</th>
								<th class="px-2 py-1.5">Rincian</th>
							</tr>
						</thead>
						<tbody class="divide-y divide-line-soft">
							{#each kejadian as k, i (i)}
								<tr class="hover:bg-surface-2/60">
									<td class="px-2 py-1.5 font-mono text-text-3">
										{String(k.created_at ?? '').slice(0, 19)}
									</td>
									<td class="px-2 py-1.5 font-mono text-text">{String(k.type ?? '—')}</td>
									<td class="px-2 py-1.5 text-text-2">{String(k.actor ?? '—')}</td>
									<td
										class="px-2 py-1.5 font-mono"
										class:text-neg={String(k.severity) === 'error' || String(k.severity) === 'warn'}
										class:text-text-3={String(k.severity) !== 'error' && String(k.severity) !== 'warn'}
									>
										{String(k.severity ?? 'info')}
									</td>
									<td class="px-2 py-1.5 text-text-2">
										{String((k.payload as Record<string, unknown>)?.detail ?? (k.payload as Record<string, unknown>)?.job ?? '—').slice(0, 90)}
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{/if}
		</section>
	{:else if sub === 'kebijakan'}
		<div class="space-y-3">
			<section class="rounded-card border border-line bg-surface p-4">
				<h2 class="text-13 font-bold text-text">Gate yang berlaku</h2>
				<ol class="mt-2 space-y-2 text-12 text-text-2">
					<li><strong class="text-text">Gate A, permukaan.</strong> Unit gagal 0, tidak ada tab kosong, sumber data jelas.</li>
					<li><strong class="text-text">Gate B, bukti.</strong> 100 trade, PF di atas 1,25 setelah biaya, DD di bawah 12%.</li>
					<li><strong class="text-text">Gate C, uang kecil.</strong> Modal $10 sampai $20, batas rugi harian 2%, rekonsiliasi nol.</li>
				</ol>
			</section>
			<section class="rounded-card border border-line bg-surface p-4">
				<h2 class="text-13 font-bold text-text">Parameter aktif</h2>
				{#if daftarParam.length > 0}
					<div class="mt-2 overflow-x-auto">
						<table class="w-full text-11 text-left">
							<thead class="border-b border-line text-10 text-text-3">
								<tr>
									<th class="px-2 py-1.5">Nama</th>
									<th class="px-2 py-1.5 text-right">Nilai</th>
									<th class="px-2 py-1.5 text-right">Batas</th>
									<th class="px-2 py-1.5">Scope</th>
									<th class="px-2 py-1.5">Catatan</th>
								</tr>
							</thead>
							<tbody class="divide-y divide-line-soft">
								{#each daftarParam as p (p.nama)}
									<tr class="hover:bg-surface-2/60">
										<td class="px-2 py-1.5 font-mono text-text">{p.nama}</td>
										<td class="px-2 py-1.5 text-right font-mono text-text">{p.nilai}</td>
										<td class="px-2 py-1.5 text-right font-mono text-text-3">
											{p.batas ? `${p.batas[0]}–${p.batas[1]}` : '—'}
										</td>
										<td class="px-2 py-1.5 font-mono text-text-3">{p.scope ?? '—'}</td>
										<td class="px-2 py-1.5 text-text-3">{p.catatan ?? ''}</td>
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
					<p class="mt-2 text-11 text-text-3">
						{jumlahTerkunci > 0 ? `${jumlahTerkunci} parameter terkunci.` : 'Tidak ada parameter yang terkunci.'}
					</p>
				{:else}
					<EmptyState judul="Parameter tidak terbaca" pesan="Endpoint params tidak mengembalikan data." ringkas={true} />
				{/if}
			</section>
		</div>
	{:else if sub === 'pengaturan'}
		<div class="space-y-3">
			<section class="rounded-card border border-line bg-surface p-4">
				<h2 class="text-13 font-bold text-text">Laya AI</h2>
				<p class="mt-2 text-12 text-text-2">
					Penilai AI untuk forex (verdict + timer tiap 60 detik). Saat ini
					<strong class="text-text">nonaktif</strong> — angka forex dihitung murni dari
					telemetri MT5 + rumus lokal. Menyalakannya mengaktifkan kembali endpoint
					verdict dan timer verdict.
				</p>
				<div class="mt-3 flex flex-wrap items-center gap-3">
					<span
						class="rounded px-2 py-0.5 text-10 font-mono font-bold border {laya?.aktif
							? 'bg-pos/15 text-pos border-pos/30'
							: 'bg-surface-2 text-text-3 border-line'}"
					>
						{laya == null ? 'MEMUAT…' : laya.aktif ? 'AKTIF' : 'NONAKTIF'}
					</span>
					<span class="text-11 font-mono text-text-3">
						timer systemd: {laya == null ? '…' : laya.systemd_timer ? 'jalan' : 'mati'}
					</span>
					<button
						class="rounded-control border border-line bg-surface-2 px-3 py-2 text-12 font-bold text-text disabled:opacity-50"
						disabled={layaSibuk}
						onclick={() => void toggleLaya()}
					>
						{layaSibuk ? 'Menyimpan…' : laya?.aktif ? 'Nonaktifkan' : 'Aktifkan'}
					</button>
				</div>
				{#if layaPesan}
					<p class="mt-2 text-12 text-text-2">{layaPesan}</p>
				{/if}
				{#if laya?.catatan}
					<p class="mt-1 text-11 text-text-3">{laya.catatan}</p>
				{/if}
			</section>
		</div>
	{:else if sub === 'vault'}
		<section class="rounded-card border border-line bg-surface p-4">
			<h2 class="text-13 font-bold text-text">Vault Kredensial</h2>
			<p class="mt-2 text-12 text-text-2">
				Simpan endpoint + API key platform manapun (Binance, Bybit, OKX, dan lainnya).
				Vault hanya menyimpan — salin-tempel manual, tidak ada auto-login.
				Polymarket tidak didukung.
			</p>
			<p class="mt-3">
				<a class="text-12 font-bold underline text-text" href="/vault">Buka Vault Kredensial →</a>
			</p>
		</section>
	{:else}
		<p class="text-12 text-text-3">Tab tidak dikenal: {sub}</p>
	{/if}
</MarketShell>
