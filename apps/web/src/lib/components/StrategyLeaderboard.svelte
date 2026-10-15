<script lang="ts">
	import { angka } from '$lib/format';
	import type { LeaderboardPayload, LeaderboardStrategy, SetupLifecycleStatus, RekonsiliasiStatus } from '$lib/api/types';
	import EmptyState from './EmptyState.svelte';
	import ErrorState from './ErrorState.svelte';

	// Backward-compatibility dengan tipe terdahulu
	export type StrategyItem = LeaderboardStrategy | {
		rank: number;
		id: string;
		nama: string;
		venue: string;
		tipe: 'PAPER' | 'LIVE' | 'SIGNAL-ONLY' | 'RESEARCH';
		winrate_pct: number | null;
		total_r: number | null;
		expectancy_r: number | null;
		n_samples: number;
		max_dd_r: number | null;
		status: 'UNGGUL' | 'PENGUJIAN' | 'FLAG_EXIT' | 'MONITOR' | 'AKTIF' | 'BENCHED' | 'HALTED';
		status_detail?: string;
		friksi_est_pct?: number | null;
	};

	interface Props {
		strategies?: StrategyItem[];
		payload?: LeaderboardPayload | null;
		memuat?: boolean;
		galat?: string | null;
		onulang?: (() => void) | null;
	}

	let {
		strategies = [],
		payload = null,
		memuat = false,
		galat = null,
		onulang = null
	}: Props = $props();

	let filterPasar = $state<string>('semua');
	let filterStatus = $state<string>('semua');
	let urutan = $state<'rank' | 'expectancy' | 'winrate' | 'ekuitas'>('rank');
	let detailTerbuka = $state<string | null>(null);

	// Normalisasi baris strategi agar seragam untuk data baru maupun lama
	const daftar = $derived.by(() => {
		const sumber = payload?.strategi ?? (strategies as LeaderboardStrategy[]);
		return sumber.map((s, idx) => {
			const id = s.id || `strat-${idx + 1}`;
			const rank = typeof s.rank === 'number' ? s.rank : idx + 1;
			const pasar = ('pasar' in s && s.pasar) ? s.pasar : 'crypto';
			const ekuitas = 'ekuitas' in s ? s.ekuitas : null;
			const total_fee = 'total_fee' in s ? s.total_fee : null;
			
			// Petakan status operasional
			let statusOp: 'AKTIF' | 'BENCHED' | 'HALTED' = 'AKTIF';
			if ('status_operasional' in s && s.status_operasional) {
				statusOp = s.status_operasional;
			} else if ('status' in s) {
				if (s.status === 'FLAG_EXIT') statusOp = 'HALTED';
				else if (s.status === 'MONITOR' || s.status === 'PENGUJIAN') statusOp = 'BENCHED';
				else statusOp = 'AKTIF';
			}

			// Petakan status setup
			const setupStatus: SetupLifecycleStatus | null = ('setup_status' in s && s.setup_status)
				? s.setup_status
				: (s.setup_terakhir?.status ?? null);

			// Petakan rekonsiliasi
			const rekon = ('rekonsiliasi' in s && s.rekonsiliasi) ? s.rekonsiliasi : {
				status: 'BELUM_DIVERIFIKASI' as RekonsiliasiStatus,
				saldo: ekuitas,
				modal_awal: s.modal_awal ?? null,
				realized_pnl: null,
				total_fee: total_fee,
				selisih: null,
				catatan: null
			};

			return {
				...s,
				id,
				rank,
				pasar,
				ekuitas,
				total_fee,
				status_operasional: statusOp,
				setup_status: setupStatus,
				rekonsiliasi: rekon
			};
		});
	});

	// Filter dan pengurutan responsif
	const baris = $derived.by(() => {
		let hasil = [...daftar];
		if (filterPasar !== 'semua') {
			hasil = hasil.filter((x) => x.pasar === filterPasar);
		}
		if (filterStatus !== 'semua') {
			hasil = hasil.filter((x) => x.status_operasional.toLowerCase() === filterStatus.toLowerCase());
		}
		if (urutan === 'expectancy') {
			hasil.sort((a, b) => (b.expectancy_r ?? -999) - (a.expectancy_r ?? -999));
		} else if (urutan === 'winrate') {
			hasil.sort((a, b) => (b.winrate_pct ?? -1) - (a.winrate_pct ?? -1));
		} else if (urutan === 'ekuitas') {
			hasil.sort((a, b) => (b.ekuitas ?? -999) - (a.ekuitas ?? -999));
		} else {
			hasil.sort((a, b) => a.rank - b.rank);
		}
		return hasil;
	});

	function toggleDetail(id: string) {
		detailTerbuka = detailTerbuka === id ? null : id;
	}

	function badgeSetupClass(st: SetupLifecycleStatus | null): string {
		switch (st) {
			case 'RUNNING': return 'bg-accent/15 text-accent border-accent/30';
			case 'IN_AREA': return 'bg-warn/15 text-warn border-warn/30';
			case 'TP': return 'bg-pos/20 text-pos border-pos/30';
			case 'SL': return 'bg-neg/20 text-neg border-neg/30';
			case 'WAITING': return 'bg-surface-2 text-text-3 border-line';
			default: return 'bg-surface text-text-3 border-line';
		}
	}

	function badgeRekonClass(st: RekonsiliasiStatus): string {
		switch (st) {
			case 'SEIMBANG': return 'bg-pos/15 text-pos border-pos/30';
			case 'SELISIH': return 'bg-neg/15 text-neg border-neg/30';
			default: return 'bg-surface text-text-3 border-line';
		}
	}

	function badgeOperasionalClass(st: 'AKTIF' | 'BENCHED' | 'HALTED'): string {
		switch (st) {
			case 'AKTIF': return 'bg-pos/15 text-pos border-pos/30';
			case 'BENCHED': return 'bg-warn/15 text-warn border-warn/30';
			case 'HALTED': return 'bg-neg/15 text-neg border-neg/30';
		}
	}
</script>

<div class="permukaan-2 rounded-card border border-line p-3" data-testid="strategy-leaderboard">
	<div class="mb-3 flex flex-wrap items-center justify-between gap-2 border-b border-line-soft pb-2">
		<div>
			<div class="flex items-center gap-2">
				<h3 class="text-14 font-bold text-text">Papan Peringkat Strategi</h3>
				<span class="rounded bg-accent/10 px-2 py-0.5 text-10 font-bold uppercase text-accent border border-accent/20">
					Leaderboard
				</span>
				{#if payload?.rekonsiliasi_global}
					<span
						class="rounded px-2 py-0.5 text-10 font-mono font-bold border {payload.rekonsiliasi_global.seimbang ? 'bg-pos/15 text-pos border-pos/30' : 'bg-neg/15 text-neg border-neg/30'}"
						title="Status rekonsiliasi seluruh buku ledger strategi"
					>
						{payload.rekonsiliasi_global.seimbang ? 'REKON SEIMBANG' : `SELISIH $${angka(payload.rekonsiliasi_global.total_selisih)}`}
					</span>
				{/if}
			</div>
			<p class="text-11 text-text-3 mt-0.5">
				Perbandingan performa strategi kuantitatif multi-pasar berbasis risk-adjusted return dan bukti ledger terukur
			</p>
		</div>
		<div class="flex items-center gap-2">
			<span class="text-11 font-mono text-text-3">
				{daftar.length} strategi terdata
			</span>
			{#if payload?.diperbarui_pada}
				<span class="text-10 font-mono text-text-3">· sinkron</span>
			{/if}
		</div>
	</div>

	<!-- Kontrol Filter & Urutan -->
	<div class="mb-3 flex flex-wrap items-center justify-between gap-2 text-11">
		<div class="flex flex-wrap items-center gap-1.5">
			<span class="text-text-3 font-mono text-10 uppercase">Pasar:</span>
			{#each ['semua', 'crypto', 'polymarket', 'idx', 'forex', 'gmgn'] as p}
				<button
					type="button"
					class="rounded-control px-2 py-1 uppercase text-10 font-bold border transition-colors {filterPasar === p ? 'bg-accent/15 text-accent border-accent/40' : 'bg-surface text-text-3 border-line hover:border-line-soft hover:text-text-2'}"
					onclick={() => (filterPasar = p)}
				>
					{p}
				</button>
			{/each}
		</div>

		<div class="flex flex-wrap items-center gap-2">
			<div class="flex items-center gap-1">
				<span class="text-text-3 font-mono text-10 uppercase">Status:</span>
				{#each ['semua', 'aktif', 'benched', 'halted'] as st}
					<button
						type="button"
						class="rounded-control px-2 py-1 uppercase text-10 font-bold border transition-colors {filterStatus === st ? 'bg-accent/15 text-accent border-accent/40' : 'bg-surface text-text-3 border-line hover:border-line-soft hover:text-text-2'}"
						onclick={() => (filterStatus = st)}
					>
						{st}
					</button>
				{/each}
			</div>

			<div class="flex items-center gap-1">
				<label for="urut-select" class="text-text-3 font-mono text-10 uppercase">Urut:</label>
				<select
					id="urut-select"
					bind:value={urutan}
					class="rounded-control bg-surface border border-line px-2 py-1 text-10 font-mono text-text focus:border-accent focus:outline-none"
				>
					<option value="rank">Peringkat</option>
					<option value="expectancy">Expectancy R</option>
					<option value="winrate">Win Rate</option>
					<option value="ekuitas">Ekuitas</option>
				</select>
			</div>
		</div>
	</div>

	<!-- Status Penanganan Galat & Memuat -->
	{#if galat}
		<div class="mb-3">
			<ErrorState pesan={galat} {onulang} />
		</div>
	{:else if memuat}
		<div class="py-8 text-center text-12 text-text-3 font-mono">
			Memuat data leaderboard strategi...
		</div>
	{:else if baris.length === 0}
		<EmptyState
			judul="Belum ada data strategi yang memenuhi kriteria"
			pesan="Papan peringkat ini hanya menampilkan strategi dengan bukti terukur dari ledger nyata tanpa data buatan. Sumber tak terbaca ditandai apa adanya."
			{onulang}
		/>
	{:else}
		<div class="overflow-x-auto -mx-3 px-3">
			<div class="space-y-2 min-w-[760px]">
			{#each baris as s (s.id)}
				{@const terbuka = detailTerbuka === s.id}
				<div class="rounded-card border border-line-soft bg-surface transition-colors hover:border-line">
					<!-- Baris Utama Ringkas -->
					<div class="flex items-center justify-between gap-3 p-2.5">
						<!-- Peringkat & Identitas Strategi -->
						<div class="flex items-center gap-2.5 min-w-[220px]">
							<div class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full font-mono text-11 font-bold {s.rank === 1 ? 'bg-accent/15 text-accent border border-accent/30' : s.rank === 2 ? 'bg-warn/15 text-warn border border-warn/30' : s.rank === 3 ? 'bg-surface-2 text-text border border-line' : 'bg-surface text-text-3 border border-line'}">
								#{s.rank}
							</div>
							<div>
								<div class="flex items-center gap-1.5">
									<button
										type="button"
										class="text-left font-bold text-12 text-text hover:text-accent transition-colors"
										onclick={() => toggleDetail(s.id)}
									>
										{s.nama}
									</button>
									<span class="rounded px-1.5 py-0.5 text-10 font-mono font-bold {s.tipe === 'LIVE' ? 'bg-pos/20 text-pos border border-pos/30' : s.tipe === 'PAPER' ? 'bg-accent/15 text-accent border border-accent/30' : 'bg-surface text-text-3 border border-line'}">
										{s.tipe}
									</span>
								</div>
								<div class="flex items-center gap-1.5 text-10 text-text-3 mt-0.5 font-mono">
									<span class="uppercase font-bold text-text-2">{s.pasar}</span>
									<span>·</span>
									<span>{s.venue}</span>
									{#if s.friksi_est_pct != null}
										<span>·</span>
										<span>Friksi ~{s.friksi_est_pct}%</span>
									{/if}
								</div>
							</div>
						</div>

						<!-- Status Setup Lifecycle -->
						<div class="w-28 text-center">
							<span class="text-10 text-text-3 uppercase block mb-0.5">Status Setup</span>
							{#if s.setup_status}
								<span class="inline-block rounded px-2 py-0.5 text-10 font-mono font-bold border {badgeSetupClass(s.setup_status)}">
									{s.setup_status}
								</span>
								{#if s.setup_terakhir?.pair}
									<span class="block text-10 font-mono text-text-3 mt-0.5 truncate max-w-[110px]" title={s.setup_terakhir.pair}>
										{s.setup_terakhir.pair}
									</span>
								{/if}
							{:else}
								<span class="text-11 font-mono text-text-3">—</span>
							{/if}
						</div>

						<!-- Badge Rekonsiliasi Ledger -->
						<div class="w-32 text-center" data-testid="reconciliation-badge">
							<span class="text-10 text-text-3 uppercase block mb-0.5">Rekonsiliasi</span>
							<span
								class="inline-block rounded px-2 py-0.5 text-10 font-mono font-bold border {badgeRekonClass(s.rekonsiliasi.status)}"
								title={s.rekonsiliasi.catatan ?? 'Formula: Saldo = Modal + Realized - Fee'}
							>
								{#if s.rekonsiliasi.status === 'SEIMBANG'}
									SEIMBANG
								{:else if s.rekonsiliasi.status === 'SELISIH'}
									SELISIH {s.rekonsiliasi.selisih != null ? `$${angka(s.rekonsiliasi.selisih)}` : ''}
								{:else}
									BELUM DIVERIFIKASI
								{/if}
							</span>
						</div>

						<!-- Metrik Finansial -->
						<div class="flex items-center gap-3 text-right">
							<div>
								<span class="text-10 text-text-3 uppercase block">Win Rate</span>
								<span class="angka text-11 font-bold {s.winrate_pct != null && s.winrate_pct >= 50 ? 'text-pos' : s.winrate_pct != null ? 'text-warn' : 'text-text-3'}">
									{s.winrate_pct != null ? `${angka(s.winrate_pct, { desimal: 1 })}%` : '—'}
								</span>
							</div>

							<div>
								<span class="text-10 text-text-3 uppercase block">Exp. R</span>
								<span class="angka text-11 font-bold {s.expectancy_r != null && s.expectancy_r >= 0 ? 'text-pos' : s.expectancy_r != null ? 'text-neg' : 'text-text-3'}">
									{s.expectancy_r != null ? `${s.expectancy_r >= 0 ? '+' : ''}${angka(s.expectancy_r)}R` : '—'}
								</span>
							</div>

							<div>
								<span class="text-10 text-text-3 uppercase block">Ekuitas</span>
								<span class="angka text-11 font-bold text-text">
									{s.ekuitas != null ? `$${angka(s.ekuitas)}` : '—'}
								</span>
							</div>

							<div>
								<span class="text-10 text-text-3 uppercase block">Sampel</span>
								<span class="text-11 font-mono text-text-2">
									{s.n_samples} n
								</span>
							</div>

							<!-- Status Operasional Badge -->
							<div class="w-24 text-right">
								<span class="inline-block rounded px-2 py-0.5 text-10 font-bold border {badgeOperasionalClass(s.status_operasional)}">
									{s.status_operasional}
								</span>
							</div>

							<!-- Tombol Detail -->
							<button
								type="button"
								class="rounded-control border border-line bg-surface-2 px-2 py-1 text-10 font-mono text-text-3 hover:text-text hover:border-line-soft transition-colors"
								aria-expanded={terbuka}
								onclick={() => toggleDetail(s.id)}
								title="Rincian rekonsiliasi dan bukti setup"
							>
								{terbuka ? 'Tutup' : 'Rincian'}
							</button>
						</div>
					</div>

					<!-- Panel Rincian Terbuka -->
					{#if terbuka}
						<div class="border-t border-line-soft bg-surface-2/40 p-3 text-11 space-y-2">
							<div class="grid grid-cols-1 md:grid-cols-2 gap-3">
								<!-- Rincian Rekonsiliasi Saldo -->
								<div class="rounded-control border border-line-soft bg-surface p-2.5">
									<div class="flex items-center justify-between border-b border-line-soft pb-1 mb-2">
										<span class="font-bold text-11 text-text uppercase font-mono">Buku Rekonsiliasi</span>
										<span class="text-10 font-mono {s.rekonsiliasi.status === 'SEIMBANG' ? 'text-pos' : s.rekonsiliasi.status === 'SELISIH' ? 'text-neg' : 'text-text-3'}">
											Status: {s.rekonsiliasi.status}
										</span>
									</div>
									<div class="space-y-1 font-mono text-10">
										<div class="flex justify-between">
											<span class="text-text-3">Modal Awal:</span>
											<span class="angka text-text">{s.rekonsiliasi.modal_awal != null ? `$${angka(s.rekonsiliasi.modal_awal)}` : '—'}</span>
										</div>
										<div class="flex justify-between">
											<span class="text-text-3">Realized PnL:</span>
											<span class="angka {s.rekonsiliasi.realized_pnl != null && s.rekonsiliasi.realized_pnl >= 0 ? 'text-pos' : s.rekonsiliasi.realized_pnl != null ? 'text-neg' : 'text-text-3'}">
												{s.rekonsiliasi.realized_pnl != null ? `${s.rekonsiliasi.realized_pnl >= 0 ? '+' : ''}$${angka(s.rekonsiliasi.realized_pnl)}` : '—'}
											</span>
										</div>
										<div class="flex justify-between">
											<span class="text-text-3">Total Fee (0.1%/sisi):</span>
											<span class="angka text-text-2">{s.rekonsiliasi.total_fee != null ? `$${angka(s.rekonsiliasi.total_fee)}` : s.total_fee != null ? `$${angka(s.total_fee)}` : '—'}</span>
										</div>
										<div class="flex justify-between border-t border-line-soft pt-1 font-bold">
											<span class="text-text-2">Saldo Tercatat:</span>
											<span class="angka text-text">{s.rekonsiliasi.saldo != null ? `$${angka(s.rekonsiliasi.saldo)}` : s.ekuitas != null ? `$${angka(s.ekuitas)}` : '—'}</span>
										</div>
										{#if s.rekonsiliasi.selisih != null && s.rekonsiliasi.selisih !== 0}
											<div class="flex justify-between text-neg font-bold">
												<span>Selisih Tidak Seimbang:</span>
												<span class="angka">${angka(s.rekonsiliasi.selisih)}</span>
											</div>
										{/if}
									</div>
									{#if s.rekonsiliasi.catatan}
										<p class="text-10 text-text-3 mt-2 border-t border-line-soft pt-1">
											Catatan: {s.rekonsiliasi.catatan}
										</p>
									{/if}
								</div>

								<!-- Rincian Setup Terakhir & Risiko -->
								<div class="rounded-control border border-line-soft bg-surface p-2.5">
									<div class="flex items-center justify-between border-b border-line-soft pb-1 mb-2">
										<span class="font-bold text-11 text-text uppercase font-mono">Daur Hidup Setup</span>
										{#if s.setup_status}
											<span class="text-10 font-mono font-bold {badgeSetupClass(s.setup_status).split(' ')[1]}">
												{s.setup_status}
											</span>
										{/if}
									</div>
									<div class="space-y-1 font-mono text-10">
										<div class="flex justify-between">
											<span class="text-text-3">Pair / Simbol:</span>
											<span class="text-text">{s.setup_terakhir?.pair ?? '—'}</span>
										</div>
										<div class="flex justify-between">
											<span class="text-text-3">Arah Posisi:</span>
											<span class="text-text">{s.setup_terakhir?.arah ?? '—'}</span>
										</div>
										<div class="flex justify-between">
											<span class="text-text-3">Entry Target:</span>
											<span class="angka text-text">{s.setup_terakhir?.entry != null ? angka(s.setup_terakhir.entry) : '—'}</span>
										</div>
										<div class="flex justify-between">
											<span class="text-text-3">Take Profit (TP):</span>
											<span class="angka text-pos">{s.setup_terakhir?.tp != null ? angka(s.setup_terakhir.tp) : '—'}</span>
										</div>
										<div class="flex justify-between">
											<span class="text-text-3">Stop Loss (SL):</span>
											<span class="angka text-neg">{s.setup_terakhir?.sl != null ? angka(s.setup_terakhir.sl) : '—'}</span>
										</div>
									</div>
									{#if s.alasan_status}
										<div class="mt-2 border-t border-line-soft pt-1 text-10 text-warn">
											Status alasan: {s.alasan_status}
										</div>
									{/if}
								</div>
							</div>
						</div>
					{/if}
				</div>
			{/each}
			</div>
		</div>
	{/if}
</div>
