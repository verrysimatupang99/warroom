<script lang="ts">
	/**
	 * InfraHealth.svelte — status infra lintas mesin (cyber1 · Memoh · MT5 boxes ·
	 * watchdog instabox · bus · War Room).
	 *
	 * Sumber: GET /api/v1/infra/health (snapshot yang didorong dari cyber1).
	 * Prinsip: jangan menyatakan hijau untuk hal yang tidak dilaporkan. Bila
	 * snapshot basi atau tidak ada, UI harus bilang begitu.
	 */
	interface Props {
		data?: Record<string, unknown> | null;
		galat?: string | null;
		memuat?: boolean;
		onreload?: () => void;
	}

	let { data = null, galat = null, memuat = false, onreload }: Props = $props();

	type Nada = 'ok' | 'gagal' | 'tak';
	const kelasNada: Record<Nada, string> = {
		ok: 'text-pos border-pos/40 bg-pos/10',
		gagal: 'text-neg border-neg/40 bg-neg/10',
		tak: 'text-text-3 border-line bg-surface-2'
	};

	const umur = $derived(typeof data?.umur_s === 'number' ? (data.umur_s as number) : null);
	const basi = $derived(umur != null && umur > 1800);

	const memoh = $derived((data?.memoh_runtime ?? {}) as Record<string, unknown>);
	const mt5 = $derived((data?.mt5 ?? {}) as Record<string, string>);
	const wd = $derived((data?.instabox_watchdog ?? {}) as Record<string, unknown>);
	const c1 = $derived((data?.cyber1 ?? {}) as Record<string, unknown>);
	const bus = $derived((data?.bus ?? {}) as Record<string, unknown>);
	const wr = $derived((data?.warroom ?? {}) as Record<string, unknown>);

	const nadaMemoh: Nada = $derived(
		!data ? 'tak' : memoh.active === 'active' && Number(memoh.outbound_conn ?? 0) > 0 ? 'ok' : 'gagal'
	);
	const daftarMt5 = $derived(Object.entries(mt5));
	const nadaMt5 = $derived<Nada>(
		!daftarMt5.length ? 'tak' : daftarMt5.every(([, v]) => v === 'up') ? 'ok' : 'gagal'
	);
	const nadaWd: Nada = $derived(!data ? 'tak' : wd.timer === 'active' ? 'ok' : 'gagal');
	const nadaBus: Nada = $derived(
		!data || typeof bus.last_message_age_sec !== 'number'
			? 'tak'
			: (bus.last_message_age_sec as number) < 3600
				? 'ok'
				: 'gagal'
	);
	const nadaWr: Nada = $derived(!data ? 'tak' : wr.root_http === '200' ? 'ok' : 'gagal');

	function umurTeks(s: number | null): string {
		if (s == null) return 'tidak diketahui';
		if (s < 90) return `${s} detik lalu`;
		if (s < 5400) return `${Math.round(s / 60)} menit lalu`;
		return `${Math.round(s / 3600)} jam lalu`;
	}
</script>

<section class="rounded-card border border-line bg-surface p-4" data-testid="infra-health">
	<div class="flex flex-wrap items-center justify-between gap-2">
		<div>
			<h2 class="text-13 font-bold text-text">Infra lintas mesin</h2>
			<p class="mt-0.5 text-11 text-text-3">
				Didorong dari cyber1 · snapshot {umurTeks(umur)}
				{#if basi}<span class="text-warn"> · data basi</span>{/if}
			</p>
		</div>
		{#if onreload}
			<button
				type="button"
				class="min-h-[44px] rounded-control border border-line px-2.5 font-mono text-11 text-text-3 hover:border-accent hover:text-accent"
				onclick={onreload}
			>
				Muat ulang
			</button>
		{/if}
	</div>

	{#if memuat && !data}
		<p class="mt-3 text-11 text-text-3">Memuat status infra…</p>
	{:else if galat}
		<p class="mt-3 text-11 text-neg">{galat}</p>
	{:else if !data || data.tersedia === false}
		<p class="mt-3 text-11 text-text-3">
			Belum ada snapshot infra. Skrip di cyber1 mengirim tiap 10 menit.
		</p>
	{:else}
		<div class="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
			<div class="rounded-control border px-3 py-2 {kelasNada[nadaMemoh]}">
				<div class="label-mikro font-mono">MEMOH RUNTIME</div>
				<div class="mt-0.5 font-mono text-12">
					{memoh.active ?? '—'} · {memoh.outbound_conn ?? 0} koneksi
				</div>
				<div class="text-10 opacity-80">restart: {memoh.restarts ?? '—'}</div>
			</div>

			<div class="rounded-control border px-3 py-2 {kelasNada[nadaMt5]}">
				<div class="label-mikro font-mono">MT5 TERMINAL</div>
				<div class="mt-0.5 space-y-0.5 font-mono text-11">
					{#each daftarMt5 as [nama, nilai] (nama)}
						<div class="flex items-center justify-between gap-2">
							<span class="truncate">{nama}</span>
							<span class={nilai === 'up' ? 'text-pos' : 'text-neg'}>{nilai}</span>
						</div>
					{:else}
						<span class="text-text-3">tidak dilaporkan</span>
					{/each}
				</div>
			</div>

			<div class="rounded-control border px-3 py-2 {kelasNada[nadaWd]}">
				<div class="label-mikro font-mono">WATCHDOG INSTABOX</div>
				<div class="mt-0.5 font-mono text-12">{wd.timer ?? '—'}</div>
				<div class="text-10 opacity-80">exit terakhir: {wd.last_status ?? '—'}</div>
			</div>

			<div class="rounded-control border px-3 py-2 {kelasNada[nadaBus]}">
				<div class="label-mikro font-mono">BUS AGENT</div>
				<div class="mt-0.5 font-mono text-12">
					{typeof bus.last_message_age_sec === 'number' ? umurTeks(bus.last_message_age_sec as number) : '—'}
				</div>
				<div class="text-10 opacity-80">pesan terakhir</div>
			</div>
		</div>

		<div class="mt-2 grid gap-2 sm:grid-cols-3">
			<div class="rounded-control border border-line bg-surface-2 px-3 py-2">
				<div class="label-mikro font-mono text-text-3">CYBER1 DISK</div>
				<div class="mt-0.5 font-mono text-12 text-text">{c1.disk_pct ?? '—'}%</div>
			</div>
			<div class="rounded-control border border-line bg-surface-2 px-3 py-2">
				<div class="label-mikro font-mono text-text-3">CYBER1 RAM</div>
				<div class="mt-0.5 font-mono text-12 text-text">{c1.mem_available_mb ?? '—'} MB bebas</div>
			</div>
			<div class="rounded-control border px-3 py-2 {kelasNada[nadaWr]}">
				<div class="label-mikro font-mono">WAR ROOM</div>
				<div class="mt-0.5 font-mono text-12">
					root {wr.root_http ?? '—'} · api {wr.api_health_http ?? '—'}
				</div>
			</div>
		</div>
	{/if}
</section>
