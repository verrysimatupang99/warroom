<script lang="ts">
	import StandbyPasar from '$lib/components/StandbyPasar.svelte';
</script>

<svelte:head><title>Polymarket | War Room</title></svelte:head>

<StandbyPasar
	nama="Polymarket"
	ringkas="Prediksi pasar biner (BTC 5m) dan arbitrase odds. Modulnya ditangguhkan sementara."
	alasan="CLOB, arbitrase odds biner, dan hedging event makro ditangguhkan agar komputasi dan perhatian trading terpusat pada eksekusi Gold dan Forex. Paper arm-nya juga sudah dihentikan karena hasil mirror menunjukkan rugi bersih setelah biaya taker."
	syarat={[
		'Sumber orderbook CLOB yang stabil dan bisa diakses dari server ini',
		'Model biaya taker dimasukkan ke backtest, bukan hanya harga mid',
		'Satu strategi lulus Gate B (PF di atas 1,25 setelah biaya, minimal 100 trade)',
		'Modal uji terpisah dari jalur forex supaya risiko tidak tercampur'
	]}
	terakhir="Arm B terakhir berjalan 28 Okt 2026, hasil -6,40%"
/>
