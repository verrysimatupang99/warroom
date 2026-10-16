<script lang="ts">
	// Cabang tampilan pasar Crypto (SMC).
	// Dipindah dari AreaView.svelte (Level 1 normalisasi). Isi & perilaku tidak berubah.
	//
	// Hanya memuat JudulBagian per-sub; penjelasan panjang (metode SMC, cara baca
	// kolom) sengaja tetap di AreaView karena ia bagian dari blok bersama per-sub,
	// bukan cabang per-pasar.
	import JudulBagian from './JudulBagian.svelte';

	interface Props {
		sub: string;
	}
	let { sub }: Props = $props();
</script>

{#if sub === 'cockpit' || !sub}
	<JudulBagian nomor="1" judul="Ringkasan" tujuan="Uang, risiko, dan sinyal teratas — keadaan hari ini dalam satu pandangan" ikon="◎" />
{:else if sub === 'setup'}
	<JudulBagian nomor="2" judul="Setup Kandidat" tujuan="Daftar lengkap kandidat + alasan lolos/gagal per aturan (kolom 'skor gate')" ikon="◈" />
{:else if sub === 'ukur'}
	<JudulBagian nomor="3" judul="Ukur (validasi)" tujuan="Apakah aturan gate punya nilai? Lolos vs ditolak, dihitung setelah kejadian" ikon="⚖" />
{:else if sub === 'eksekusi'}
	<JudulBagian nomor="4" judul="Eksekusi & Ledger" tujuan="Yang benar-benar terjadi: posisi terbuka, fill, hasil per trade" ikon="⇄" />
{/if}
