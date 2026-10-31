<script lang="ts">
	// Akun MT5: satu terminal = satu akun. Panel ini memisahkan akun Reaper (demo)
	// dari akun lain (mis. cent HSFX) supaya telemetri tidak saling menimpa.
	import { onMount } from 'svelte';
	import { urlApi } from '$lib/api/client';
	import KurvaEkuitas from '$lib/components/KurvaEkuitas.svelte';

	interface Akun {
		account: string;
		broker?: string;
		primary?: boolean;
		connected?: boolean;
		seconds_ago?: number;
		balance?: number | null;
		equity?: number | null;
		positions?: number;
		pending?: number;
	}
	interface Posisi {
		ticket?: number;
		symbol?: string;
		side?: string;
		volume?: number;
		open_price?: number;
		current_price?: number;
		pnl_usd?: number;
	}
	interface Status {
		account?: string;
		balance?: number | null;
		equity?: number | null;
		floating_pnl?: number | null;
		positions?: Posisi[];
		pending_orders?: unknown[];
		connected?: boolean;
		seconds_ago?: number;
	}
	interface Deal {
		ticket?: string;
		iso?: string;
		symbol?: string;
		side?: string;
		pnl_usd?: string;
		account?: string;
	}
	interface Perf {
		deret?: { t?: string; equity?: number | null }[];
		markers?: { t?: string; ticket?: string; symbol?: string; net_usd?: number | null }[];
		drawdown_max_pct?: number | null;
		n_titik?: number;
	}

	let akun = $state<Akun[]>([]);
	let pilih = $state<string>('');
	let status = $state<Status | null>(null);
	let perf = $state<Perf | null>(null);
	let deals = $state<Deal[]>([]);
	let galat = $state<string | null>(null);
	let memuat = $state(true);

	async function ambil<T>(jalur: string): Promise<T | null> {
		try {
			const r = await fetch(urlApi(jalur), { credentials: 'include' });
			const isi = await r.json().catch(() => null);
			if (!r.ok) {
				const p = isi?.detail?.message ?? isi?.error?.message ?? isi?.detail;
				galat = typeof p === 'string' ? p : `HTTP ${r.status}`;
				return null;
			}
			return isi as T;
		} catch (e) {
			galat = e instanceof Error ? e.message : 'gagal menghubungi API';
			return null;
		}
	}

	async function pilihAkun(nama: string) {
		pilih = nama;
		status = await ambil<Status>(
			`/api/v1/tencent/mt5/status?account=${encodeURIComponent(nama)}`
		);
		perf = await ambil<Perf>(
			`/api/v1/journal/performance?market=forex&account=${encodeURIComponent(nama)}`
		);
	}

	onMount(async () => {
		galat = null;
		const daftar = await ambil<{ accounts?: Akun[] }>('/api/v1/tencent/mt5/accounts');
		akun = daftar?.accounts ?? [];
		const perdana = akun.find((a) => a.primary)?.account ?? akun[0]?.account ?? '';
		if (perdana) await pilihAkun(perdana);
		const trades = await ambil<{ closed?: Deal[] }>('/api/v1/journal/trades?market=forex');
		deals = trades?.closed ?? [];
		memuat = false;
	});

	function rp(v?: number | null) {
		return v == null ? '—' : `$${v.toFixed(2)}`;
	}
	function umur(detik?: number) {
		if (detik == null) return '—';
		return detik < 60 ? `${detik}s` : `${Math.round(detik / 60)} mnt`;
	}
	const akunUtama = $derived(akun.find((a) => a.primary)?.account ?? '');
	const dealAkun = $derived(
		deals
			.filter((d) => {
				const acc = d.account && d.account !== 'unknown' ? d.account : akunUtama;
				return acc === pilih;
			})
			.slice(0, 10)
	);
</script>

<section class="rounded-card border border-line bg-surface p-4" data-testid="akun-mt5">
	<div class="flex flex-wrap items-start justify-between gap-2">
		<div>
			<h2 class="text-13 font-bold text-text">Akun MT5</h2>
			<p class="mt-0.5 text-11 text-text-3">
				Satu terminal = satu akun. Telemetri dipisah per nomor akun; akun cent tidak
				menimpa akun demo Reaper.
			</p>
		</div>
		<span class="font-mono text-10 text-text-3">{akun.length} akun terdeteksi</span>
	</div>

	{#if memuat}
		<p class="mt-2 text-11 text-text-3">membaca akun…</p>
	{:else if galat}
		<p class="mt-2 text-11 text-text-3">Akun MT5 tidak terbaca: {galat}</p>
	{:else if akun.length === 0}
		<p class="mt-2 text-11 text-text-3">
			Belum ada telemetri akun. EA/bridge harus mengirim ke
			<code class="font-mono text-text-2">POST /api/v1/tencent/mt5/telemetry</code>.
		</p>
	{:else}
		<div class="mt-2 flex flex-wrap gap-2">
			{#each akun as a (a.account)}
				<button
					type="button"
					class="min-h-[44px] rounded-control border px-3 py-2 text-left"
					class:border-accent={pilih === a.account}
					class:bg-surface-2={pilih === a.account}
					class:border-line={pilih !== a.account}
					onclick={() => pilihAkun(a.account)}
				>
					<div class="flex items-center gap-2 font-mono text-11 text-text">
						#{a.account}
						{#if a.primary}<span class="text-10 text-accent">UTAMA</span>{/if}
						<span class:text-pos={a.connected} class:text-text-3={!a.connected} class="text-10">
							{a.connected ? 'live' : 'offline'}
						</span>
					</div>
					<div class="mt-0.5 font-mono text-10 text-text-3">
						{rp(a.balance)} · {a.positions ?? 0} posisi · {umur(a.seconds_ago)}
					</div>
				</button>
			{/each}
		</div>

		{#if status}
			<dl class="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
				<div>
					<dt class="label-mikro font-mono text-text-3">BALANCE</dt>
					<dd class="mt-0.5 font-mono text-14 font-bold text-text">{rp(status.balance)}</dd>
				</div>
				<div>
					<dt class="label-mikro font-mono text-text-3">EQUITY</dt>
					<dd class="mt-0.5 font-mono text-14 font-bold text-text">{rp(status.equity)}</dd>
				</div>
				<div>
					<dt class="label-mikro font-mono text-text-3">FLOATING</dt>
					<dd class="mt-0.5 font-mono text-14 font-bold" class:text-pos={(status.floating_pnl ?? 0) > 0} class:text-neg={(status.floating_pnl ?? 0) < 0}>
						{rp(status.floating_pnl)}
					</dd>
				</div>
				<div>
					<dt class="label-mikro font-mono text-text-3">POSISI</dt>
					<dd class="mt-0.5 font-mono text-14 font-bold text-text">{status.positions?.length ?? 0}</dd>
				</div>
				<div>
					<dt class="label-mikro font-mono text-text-3">TERAKHIR</dt>
					<dd class="mt-0.5 font-mono text-14 font-bold text-text">{umur(status.seconds_ago)}</dd>
				</div>
			</dl>

			{#if status.positions && status.positions.length > 0}
				<div class="mt-3 overflow-x-auto">
					<table class="w-full text-11 text-left">
						<thead class="border-b border-line text-10 text-text-3">
							<tr>
								<th class="px-2 py-1.5">Ticket</th>
								<th class="px-2 py-1.5">Simbol</th>
								<th class="px-2 py-1.5">Arah</th>
								<th class="px-2 py-1.5 text-right">Volume</th>
								<th class="px-2 py-1.5 text-right">Open</th>
								<th class="px-2 py-1.5 text-right">Kini</th>
								<th class="px-2 py-1.5 text-right">PnL</th>
							</tr>
						</thead>
						<tbody class="divide-y divide-line-soft">
							{#each status.positions as p (p.ticket)}
								<tr>
									<td class="px-2 py-1.5 font-mono text-text-3">{p.ticket ?? '—'}</td>
									<td class="px-2 py-1.5 font-mono text-text">{p.symbol ?? '—'}</td>
									<td class="px-2 py-1.5 font-mono" class:text-pos={p.side === 'BUY'} class:text-neg={p.side === 'SELL'}>{p.side ?? '—'}</td>
									<td class="px-2 py-1.5 text-right font-mono text-text-2">{p.volume ?? '—'}</td>
									<td class="px-2 py-1.5 text-right font-mono text-text-2">{p.open_price ?? '—'}</td>
									<td class="px-2 py-1.5 text-right font-mono text-text-2">{p.current_price ?? '—'}</td>
									<td class="px-2 py-1.5 text-right font-mono" class:text-pos={(p.pnl_usd ?? 0) > 0} class:text-neg={(p.pnl_usd ?? 0) < 0}>{rp(p.pnl_usd)}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{/if}

			{#if perf && (perf.n_titik ?? 0) > 0}
				<KurvaEkuitas
					deret={perf.deret ?? []}
					markers={perf.markers ?? []}
					drawdown_pct={perf.drawdown_max_pct}
				/>
			{/if}

			<h3 class="mt-3 text-12 font-bold text-text">Deal tertutup akun ini</h3>
			{#if dealAkun.length === 0}
				<p class="mt-1 text-11 text-text-3">Belum ada deal tertutup yang dilaporkan akun ini.</p>
			{:else}
				<div class="mt-1 flex flex-wrap gap-x-3 gap-y-1 font-mono text-10 text-text-3">
					{#each dealAkun as d, i (i)}
						<span>{d.iso ?? '—'} · {d.symbol ?? '—'} {d.side ?? ''} · {rp(Number(d.pnl_usd))}</span>
					{/each}
				</div>
			{/if}
		{/if}
	{/if}
</section>
