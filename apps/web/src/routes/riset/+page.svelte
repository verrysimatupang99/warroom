<script lang="ts">
	import { page } from '$app/state';
	import { AREAS, SLUG_LAMA } from '$lib/nav';
	import MarketShell from '$lib/components/MarketShell.svelte';
	import QuantStrategyCard from '$lib/components/QuantStrategyCard.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';

	const area = AREAS.find((a) => a.kunci === 'riset')!;
	const sub = $derived.by(() => {
		const s = page.url.searchParams.get('sub') ?? 'kinerja';
		return SLUG_LAMA[s] ?? s;
	});
</script>

<svelte:head><title>Riset | War Room</title></svelte:head>

<MarketShell
	{area}
	aktif={sub}
	judul="Riset"
	deskripsi="Hasil uji strategi. Setiap angka wajib disertai jumlah trade dan periode, karena PF dari sampel kecil tidak berarti."
	sumber="pasar/quant-backtest"
>
	{#if sub === 'kinerja'}
		<QuantStrategyCard filter="all" />
	{:else if sub === 'bukti'}
		<div class="space-y-3">
			<QuantStrategyCard filter="forex" />
			<p class="text-11 text-text-3">
				Bukti per market aktif. Laporan lengkap tersimpan di repo laptop; angka di halaman ini
				adalah ringkasan yang disimpan server.
			</p>
		</div>
	{:else if sub === 'leaderboard'}
		<EmptyState
			judul="Papan peringkat belum aktif"
			pesan="Peringkat butuh minimal dua strategi yang lulus Gate B dengan biaya nyata. Sekarang belum ada yang lulus, jadi papan peringkat akan menampilkan satu baris saja."
			langkah="Selesaikan Gate B untuk satu strategi lebih dulu."
		/>
	{:else if sub === 'kalender'}
		<EmptyState
			judul="Kalender makro belum punya sumber"
			pesan="Server tidak punya feed kalender ekonomi otomatis. Menampilkan tanggal dari ingatan akan berisiko salah, jadi blok ini dibiarkan kosong."
			langkah="Tambahkan feed kalender bila ingin blok ini hidup."
		/>
	{:else}
		<QuantStrategyCard filter="all" />
	{/if}
</MarketShell>
