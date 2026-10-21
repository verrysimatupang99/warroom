<script lang="ts">
	// TopBar — rombak total (6 Okt 2026), bahasa "Algentis gelap".
	//
	// Yang berubah dari versi lama:
	//   - TemaToggle DIHAPUS (permintaan pemilik: gelap saja). Dua tema = dua sistem
	//     yang harus dijaga; satu tema = satu kebenaran.
	//   - MoneyStrip besar di header diganti satu baris status padat: mode, kesegaran,
	//     biaya/kejadian, waktu. Angka uang detail pindah ke halaman tempat ia berarti.
	//   - Kerapatan naik (padding 8px, teks 12px) sesuai panduan data-dense.
	//   - Aksen tunggal: mint. Status buruk = merah, perhatian = kuning.
	import { jamWIB, umurDetik } from '$lib/format';
	import { live } from '$lib/api/live.svelte';
	import { getAlerts, getKesegaran, getLiveArming } from '$lib/api/client';
	import type { LiveArming } from '$lib/api/types';

	let jam = $state(jamWIB());
	$effect(() => {
		const t = setInterval(() => (jam = jamWIB()), 1000);
		return () => clearInterval(t);
	});

	let total = $state<number | null>(null);
	/** Mode eksekusi dari API (`/api/v1/live/arming`) — SATU-SATUNYA sumber badge mode.
	 *  null = belum tahu/gagal fetch → badge disembunyikan (jujur, bukan dikarang). */
	let arming = $state<LiveArming | null>(null);
	/** Fact basi + sebabnya — QA putaran 2: "status basi perlu dijelaskan dengan
	 *  sumber dan timestamp yang lebih langsung", bukan hanya jumlah di header. */
	let basiDaftar = $state<{ kind: string; key: string; umur_s: number | null; ttl_s: number | null; sumber: string }[]>([]);
	let basiTerbuka = $state(false);
	let basi = $state<number | null>(null);
	let alert = $state<number | null>(null);

	async function muat() {
		const [k, a, m] = await Promise.allSettled([getKesegaran(), getAlerts(), getLiveArming()]);
		if (k.status === 'fulfilled') {
			total = k.value.count;
			const b = k.value.facts.filter((x) => x.status === 'basi');
			basi = b.length;
			basiDaftar = b.map((x) => ({
				kind: x.kind,
				key: x.key,
				umur_s: x.age_s ?? null,
				ttl_s: x.ttl_s ?? null,
				sumber: String(x.source ?? '')
			}));
		}
		if (a.status === 'fulfilled') alert = a.value.terbuka;
		if (m.status === 'fulfilled') arming = m.value;
	}
	$effect(() => {
		void muat();
		const t = setInterval(() => void muat(), 15000);
		return () => clearInterval(t);
	});

	const segar = $derived(total === null ? null : total - (basi ?? 0));
	const nadaLive = $derived(
		live.status === 'live' ? 'baik' : live.status === 'polling' ? 'perhatian' : 'buruk'
	);
	import Ikon from './Ikon.svelte';
</script>

<header class="topbar" data-testid="topbar">
	<div class="kiri">
		<span class="merek">War<span>Room</span></span>
		{#if arming !== null}
			<span class="mode" title={arming.detail}>{arming.armed ? 'LIVE' : 'PAPER'}</span>
		{/if}
	</div>

	<div class="kanan">
		<span class="stat" title={live.pesan ?? 'status aliran'}>
			<span class="titik {nadaLive}" aria-hidden="true"></span>
			{live.status}
		</span>

		{#if segar !== null}
			<span class="stat" title={`${segar}/${total} fakta segar`}>
				fakta <b class="angka">{segar}/{total}</b>
			</span>
		{/if}
		{#if basi}
			<!-- "basi" tanpa penjelasan membuat pembaca menebak apakah data rusak. Klik =
			     daftar langsung: kunci, umur vs TTL, dan sumbernya. -->
			<button
				type="button"
				class="stat basi angka"
				aria-expanded={basiTerbuka}
				aria-label={`${basi} fakta basi — buka daftar`}
				onclick={() => (basiTerbuka = !basiTerbuka)}
			>
				· {basi} basi
			</button>
		{/if}

		{#if alert !== null && alert > 0}
			<!-- Temuan QA 15 Okt (Low): "alert" saja tidak menyebut status. Angka ini
			     alert TERBUKA (belum di-ack) — tulis eksplisit. -->
			<a class="stat perhatian" href="/sistem?sub=event" title="alert terbuka (belum di-ack)">
				<Ikon nama="peringatan" ukuran={13} /> <b class="angka">{alert}</b> alert terbuka
			</a>
		{/if}

		<span class="stat angka" aria-label="jam WIB">{jam} <span class="wib">WIB</span></span>

		<a class="stat" href="/sistem?sub=event" aria-label="Notifikasi & kejadian" title="EventItem">
			<Ikon nama="lonceng" ukuran={15} />
		</a>
	</div>
</header>
{#if basiTerbuka && basiDaftar.length}
	<!-- Daftar fakta basi (temuan QA putaran 2): kunci, umur vs TTL, dan SUMBERNYA —
	     supaya "6 basi" tidak lagi jadi angka tanpa penjelasan. -->
	<div class="panel-basi" role="dialog" aria-label="Daftar fakta basi">
		<div class="kepala-basi">
			<span><b>{basiDaftar.length}</b> fakta melewati TTL-nya</span>
			<button type="button" class="tutup-basi" onclick={() => (basiTerbuka = false)} aria-label="Tutup daftar fakta basi">✕</button>
		</div>
		<ul>
			{#each basiDaftar as b (b.kind + b.key)}
				<li>
					<span class="font-mono text-11 text-text-2">{b.kind}/{b.key}</span>
					<span class="text-10 text-text-3">
						umur {b.umur_s != null ? umurDetik(b.umur_s) : '—'} · ttl {b.ttl_s != null ? umurDetik(b.ttl_s) : '—'}
						{#if b.sumber}· sumber <span class="font-mono">{b.sumber.split('/').pop()?.slice(0, 40)}</span>{/if}
					</span>
				</li>
			{/each}
		</ul>
		<p class="text-10 text-text-3">
			Basi = fakta belum diperbarui melewati TTL-nya. Untuk kandidat sinyal, yang basi memang
			otomatis disembunyikan dari UI. Untuk mesin yang dibekukan (mis. IDX), fakta lama tetap
			ditampilkan apa adanya dan ditandai HISTORIS di halaman pasarnya.
		</p>
	</div>
{/if}


<style>
	.panel-basi {
		position: fixed; top: 3rem; right: 0.75rem; z-index: 40;
		max-width: 24rem; max-height: 60vh; overflow: auto;
		background: var(--color-surface); border: 1px solid var(--color-line);
		border-radius: var(--radius-card, 0.75rem); padding: 0.75rem 0.85rem;
		/* FLAT (design 16 Okt): tanpa glow. */
	}
	.kepala-basi { display: flex; align-items: center; justify-content: space-between; gap: 0.5rem; margin-bottom: 0.5rem; }
	.tutup-basi { border: 1px solid var(--color-line); border-radius: 0.4rem; padding: 0 0.4rem; color: var(--color-text-3); }
	.panel-basi ul { display: flex; flex-direction: column; gap: 0.4rem; margin: 0; padding: 0; list-style: none; }
	.panel-basi li { display: flex; flex-direction: column; border-top: 1px dashed var(--color-line); padding-top: 0.35rem; }

	.topbar {
		position: sticky;
		top: 0;
		z-index: 30;
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.75rem;
		padding: 0.5rem 1rem;
		background: color-mix(in srgb, var(--color-bg) 84%, transparent);
		/* backdrop-filter blur (glassmorphism) dihapus — FLAT, design 16 Okt. */
		border-bottom: 1px solid var(--color-line);
		/* FLAT: tanpa glassmorphism/glow. */
	}
	.kiri {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		min-width: 0;
	}
	.merek {
		font-family: var(--font-display);
		font-size: var(--text-16);
		font-weight: 700;
		letter-spacing: -0.02em;
	}
	.merek span {
		color: var(--color-accent);
		text-shadow: 0 0 14px color-mix(in srgb, var(--color-accent) 45%, transparent);
	}
	.mode {
		font-size: var(--text-10);
		font-weight: 700;
		letter-spacing: 0.1em;
		padding: 0.1rem 0.45rem;
		border: 1px solid var(--color-accent);
		color: var(--color-accent);
		border-radius: 999px;
		background: color-mix(in srgb, var(--color-accent) 8%, transparent);
	}
	.kanan {
		display: flex;
		align-items: center;
		gap: 0.85rem;
		font-size: var(--text-12);
		color: var(--color-text-2);
	}
	.stat {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
		/* Target sentuh ≥44 px (audit QA 7 Okt: "ikon notifikasi sekitar 15–18 px").
		   Teks tetap kecil; yang dibesarkan adalah area yang bisa ditekan. */
		min-height: 44px;
		padding: 0 0.35rem;
		color: var(--color-text-2);
		text-decoration: none;
		white-space: nowrap;
	}
	.stat b {
		color: var(--color-text);
		font-weight: 600;
	}
	.stat.perhatian {
		color: var(--color-warn);
	}
	.basi {
		color: var(--color-warn);
	}
	.wib {
		color: var(--color-text-3);
		font-size: var(--text-10);
	}
	.titik {
		width: 7px;
		height: 7px;
		border-radius: 50%;
		flex: none;
	}
	/* Antislop R-19: dot menandai state nyata (aliran SSE hidup) — tanpa glow
	   berlebih dan TANPA loop pulse bermakna tidak ada. Pulih otomatis diam. */
	.titik.baik {
		background: var(--color-pos);
		/* Glow mint dihapus — mint khusus nilai TERUKUR (design 16 Okt). */
	}
	.titik.perhatian {
		background: var(--color-warn);
	}
	.titik.buruk {
		background: var(--color-neg);
	}
	.angka {
		font-family: var(--font-mono);
		font-variant-numeric: tabular-nums;
	}
	.stat,
	.merek,
	.mode {
		transition: color 160ms var(--ease-out, ease-out), border-color 160ms var(--ease-out, ease-out);
	}
	.mode:hover { background: color-mix(in srgb, var(--color-accent) 16%, transparent); }
	a.stat:hover {
		color: var(--color-accent);
	}
	@media (max-width: 640px) {
		.kanan .stat:nth-child(2),
		.kanan .stat:nth-child(3),
		.kanan .stat:nth-child(4) {
			display: none;
		}
		.topbar {
			padding: 0.35rem 0.65rem;
		}
	}
</style>