<script lang="ts">
	// Cabang tampilan pasar Polymarket.
	//
	// Dipindah dari AreaView.svelte (Level 1 normalisasi): AreaView kini hanya
	// merakit, tidak lagi memuat markup per-pasar. Isi dan perilaku TIDAK berubah —
	// setiap pasar menerima konteks yang sama, jadi bedanya hanya di data, bukan
	// di bentuk komponen.
	//
	// Subs: setup-b (Arm B, yang dipakai) · btc-5m (alternatif) · riset · arsip · live
	import JudulBagian from './JudulBagian.svelte';

	interface Props {
		sub: string;
	}
	let { sub }: Props = $props();
</script>

{#if sub === 'setup-b' || !sub}
	<JudulBagian nomor="1" judul="Favorit 0,70–0,95 (Arm B)" tujuan="Satu-satunya arm yang dipakai: beli outcome favorit yang harganya 0,70–0,95 (menang kecil, sering benar)" ikon="◎" />
{:else if sub === 'btc-5m'}
	<JudulBagian nomor="2" judul="BTC 5m (Alternatif)" tujuan="Strategi BTC 5 menit up/down dari skill PolyBTC Momentum — dijalankan terpisah dari arm D favorit" ikon="⚡" />
{:else if sub === 'riset'}
	<JudulBagian nomor="3" judul="Riset" tujuan="Dataset beku + parity/drift + katalog replay — bahan bukti, bukan keputusan" ikon="⌕" />
{:else if sub === 'arsip'}
	<JudulBagian nomor="4" judul="Arm Lain (Beku)" tujuan="A momentum, C fade, D favorit: disimpan sebagai bukti, bukan dasar keputusan" ikon="❄" />
{:else if sub === 'live'}
	<JudulBagian nomor="5" judul="Live" tujuan="Jalur uang nyata: status arming 3-way (belum aktif)" ikon="⚡" />
{/if}
