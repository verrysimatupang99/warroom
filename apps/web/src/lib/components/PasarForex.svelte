<script lang="ts">
	// Cabang tampilan pasar Forex & Komoditas.
	// Dipindah dari AreaView.svelte (Level 1 normalisasi). Isi & perilaku tidak berubah.
	import JudulBagian from './JudulBagian.svelte';

	interface Props {
		sub: string;
	}
	let { sub }: Props = $props();
</script>

{#if sub === 'struktur' || !sub}
	<JudulBagian nomor="1" judul="Struktur" tujuan="Pandangan harga emas (XAU/USD) + sinyal & titik masuk dari jurnal mesin" ikon="◈" />
{:else if sub === 'sesi'}
	<JudulBagian nomor="2" judul="Sesi" tujuan="Kapan tiap bursa buka/tutup + ramai-tidaknya tiap jam sesi" ikon="◷" />
{:else if sub === 'kalender'}
	<JudulBagian nomor="3" judul="Kalender" tujuan="Agenda berita besar + hitung mundur: apakah aman masuk posisi sekarang" ikon="⌗" />
{:else if sub === 'demo'}
	<JudulBagian nomor="4" judul="Keterbatasan & Demo" tujuan="Apa yang belum ada (akun broker, biaya) — dinyatakan terbuka" ikon="⚠" />
{/if}
