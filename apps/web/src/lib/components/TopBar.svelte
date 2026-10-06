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
	import { jamWIB } from '$lib/format';
	import { live } from '$lib/api/live.svelte';
	import { getAlerts, getKesegaran } from '$lib/api/client';

	let jam = $state(jamWIB());
	$effect(() => {
		const t = setInterval(() => (jam = jamWIB()), 1000);
		return () => clearInterval(t);
	});

	let total = $state<number | null>(null);
	let basi = $state<number | null>(null);
	let alert = $state<number | null>(null);

	async function muat() {
		const [k, a] = await Promise.allSettled([getKesegaran(), getAlerts()]);
		if (k.status === 'fulfilled') {
			total = k.value.count;
			basi = k.value.facts.filter((x) => x.status === 'basi').length;
		}
		if (a.status === 'fulfilled') alert = a.value.terbuka;
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
</script>

<header class="topbar" data-testid="topbar">
	<div class="kiri">
		<span class="merek">War<span>Room</span></span>
		<span class="mode">PAPER</span>
	</div>

	<div class="kanan">
		<span class="stat" title={live.pesan ?? 'status aliran'}>
			<span class="titik {nadaLive}" aria-hidden="true"></span>
			{live.status}
		</span>

		{#if segar !== null}
			<span class="stat" title={`${segar}/${total} fakta segar`}>
				fakta <b class="angka">{segar}/{total}</b>
				{#if basi}<span class="basi angka">· {basi} basi</span>{/if}
			</span>
		{/if}

		{#if alert !== null && alert > 0}
			<a class="stat perhatian" href="/sistem?sub=event" title="alert terbuka">
				⚠ <b class="angka">{alert}</b> alert
			</a>
		{/if}

		<span class="stat angka" aria-label="jam WIB">{jam} <span class="wib">WIB</span></span>

		<a class="stat" href="/sistem?sub=event" aria-label="Notifikasi & kejadian" title="Kejadian">
			🔔
		</a>
	</div>
</header>

<style>
	.topbar {
		position: sticky;
		top: 0;
		z-index: 30;
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.75rem;
		padding: 0.5rem 0.85rem;
		background: color-mix(in srgb, var(--color-bg) 88%, transparent);
		backdrop-filter: blur(8px);
		border-bottom: 1px solid var(--color-line);
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
	}
	.mode {
		font-size: var(--text-10);
		font-weight: 700;
		letter-spacing: 0.1em;
		padding: 0.1rem 0.45rem;
		border: 1px solid var(--color-accent);
		color: var(--color-accent);
		border-radius: 999px;
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
	.titik.baik {
		background: var(--color-pos);
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
	@media (max-width: 640px) {
		.kanan .stat:nth-child(2) {
			display: none;
		}
	}
</style>
