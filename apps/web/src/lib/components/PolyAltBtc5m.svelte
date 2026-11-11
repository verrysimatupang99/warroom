<script lang="ts">
	// Alternatif BTC 5m (skill PolyBTC Momentum, 0xgetz/polymarket-btc-5m).
	//
	// Ditampilkan sebagai ALTERNATIF pasar Polymarket — bukan bagian arm D favorit
	// yang sudah dipakai. Semua angka berasal dari fakta `poly.alt/btc-5m` yang dibaca
	// job `polybtc-sync` dari keluaran skill; tidak ada angka yang dihitung di UI.
	import HonestyTag from './HonestyTag.svelte';

	interface Sesi {
		profil?: string | null;
		live?: boolean;
		mode?: string | null;
		mulai?: string | null;
		poll_sec?: number | null;
		batas_menit?: number | null;
	}
	interface Terakhir {
		slug?: string | null;
		detik_tersisa?: number | null;
		btc_move_usd?: number | null;
		up_ask?: number | null;
		dn_ask?: number | null;
		spread?: number | null;
		lolos?: boolean;
		alasan?: string[];
	}
	interface Obs {
		n_snapshot?: number;
		preflight_go?: number;
		terakhir?: Terakhir | null;
		alasan?: string | null;
	}

	interface Fakta {
		source?: string | null;
		age_s?: number | null;
		status?: string | null;
	}

	interface Props {
		nilai: Record<string, any> | null;
		fakta?: Fakta | null;
	}
	let { nilai, fakta = null }: Props = $props();

	const terverifikasi = $derived(fakta?.status === 'segar' ? true : null);

	const tersedia = $derived(Boolean(nilai?.tersedia));
	const sesi = $derived((nilai?.sesi ?? {}) as Sesi);
	const obs = $derived((nilai?.observasi ?? {}) as Obs);
	const terakhir = $derived((obs?.terakhir ?? null) as Terakhir | null);
	const jalan = $derived(Boolean(nilai?.jalan));
	const catatan = $derived((nilai?.catatan ?? []) as string[]);

	const usia = (s?: number | null): string =>
		s == null || !Number.isFinite(s) ? '—' : s < 60 ? `${Math.round(s)} dtk` : `${(s / 60).toFixed(1)} mnt`;
	const usd = (n?: number | null): string =>
		n == null || !Number.isFinite(n) ? '—' : `$${n.toFixed(2)}`;
	// Skill memakai sentinel besar (mis. 99) saat sisi tidak punya harga sama sekali —
	// itu BUKAN spread 99%. Menampilkannya sebagai persen akan menyesatkan, jadi
	// ditampilkan sebagai "tidak ada harga" sesuai artinya.
	const spread = (n?: number | null): string =>
		n == null || !Number.isFinite(n) ? '—' : n >= 1 ? 'tidak ada harga' : `${(n * 100).toFixed(2)}%`;
</script>

{#if !tersedia}
	<div class="rounded-card border border-line bg-surface p-3">
		<p class="text-12 text-warn">
			Skill PolyBTC Momentum tidak ditemukan di box ini
			{nilai?.alasan ? `(${nilai.alasan})` : ''}, tidak ada angka yang ditampilkan.
		</p>
	</div>
{:else}
	<div class="space-y-3">
		<!-- Ringkasan keadaan sesi: mode + profil, apa adanya. -->
		<div class="rounded-card border border-line bg-surface p-3">
			<div class="flex flex-wrap items-center gap-2">
				<span class="rounded px-1.5 py-0.5 text-10 font-bold border border-accent/40 bg-accent/10 text-accent">
					{sesi.mode ?? '—'}
				</span>
				<span class="text-11 text-text-3">profil {sesi.profil ?? '—'}</span>
				<span class="text-11 {jalan ? 'text-pos' : 'text-text-3'}">
					{jalan ? '● sesi berjalan' : '○ sesi berhenti'}
				</span>
				<HonestyTag
					terverifikasi={terverifikasi}
					sumber={fakta?.source ?? null}
					alasan="dibaca dari runtime skill, bukan dihitung di UI"
				/>
			</div>
			{#if catatan.length}
				<ul class="mt-2 space-y-0.5">
					{#each catatan as c}
						<li class="text-11 text-text-3">· {c}</li>
					{/each}
				</ul>
			{/if}
		</div>

		<!-- Snapshot pasar terakhir: bukti jalur data hidup. -->
		<div class="rounded-card border border-line bg-surface p-3">
			<h3 class="text-13 font-medium text-text">Snapshot pasar terakhir</h3>
			{#if terakhir}
				<div class="mt-2 grid grid-cols-2 gap-x-4 gap-y-1.5 text-12 sm:grid-cols-4">
					<div>
						<div class="label-mikro text-text-3">market</div>
						<div class="font-mono text-11 text-text">{terakhir.slug ?? '—'}</div>
					</div>
					<div>
						<div class="label-mikro text-text-3">sisa waktu</div>
						<div class="font-mono text-text">{usia(terakhir.detik_tersisa)}</div>
					</div>
					<div>
						<div class="label-mikro text-text-3">gerak BTC 5m</div>
						<div class="font-mono text-text">{usd(terakhir.btc_move_usd)}</div>
					</div>
					<div>
						<div class="label-mikro text-text-3">spread</div>
						<div class="font-mono text-text">{spread(terakhir.spread)}</div>
					</div>
					<div>
						<div class="label-mikro text-text-3">ask UP</div>
						<div class="font-mono text-text">{terakhir.up_ask ?? '—'}</div>
					</div>
					<div>
						<div class="label-mikro text-text-3">ask DOWN</div>
						<div class="font-mono text-text">{terakhir.dn_ask ?? '—'}</div>
					</div>
					<div>
						<div class="label-mikro text-text-3">preflight</div>
						<div class="font-bold {terakhir.lolos ? 'text-pos' : 'text-text-3'}">
							{terakhir.lolos ? 'GO' : 'TIDAK'}
						</div>
					</div>
					<div>
						<div class="label-mikro text-text-3">snapshot</div>
						<div class="font-mono text-text">{obs.n_snapshot ?? 0} · go {obs.preflight_go ?? 0}</div>
					</div>
				</div>
				{#if terakhir.alasan?.length}
					<p class="mt-2 text-11 text-text-3">
						Alasan terakhir: {terakhir.alasan.join(' · ')}
					</p>
				{/if}
			{:else}
				<p class="mt-2 text-12 text-text-3">
					{obs.alasan ?? 'Belum ada snapshot, skill belum pernah dijalankan di sini.'}
				</p>
			{/if}
		</div>

		<!-- Penjelasan singkat: apa ini dan apa yang TIDAK boleh disimpulkan. -->
		<div class="rounded-card border border-line-soft bg-surface-2 p-3">
			<p class="text-11 text-text-2">
				<b>Apa ini:</b> strategi BTC 5 menit up/down (momentum ke penutupan) dari skill
				<b>PolyBTC Momentum</b>, dijalankan sebagai alternatif, terpisah dari arm D favorit.
			</p>
			<p class="mt-1 text-11 text-text-3">
				<b>Yang tidak boleh disimpulkan:</b> belum ada bukti uang nyata. Jalur ini masih
				dry-run, order sungguhan butuh engine eksekusi eksternal yang belum dipasang.
				Angka di atas menggambarkan perilaku mesin, bukan hasil.
			</p>
		</div>
	</div>
{/if}
