<script lang="ts">
	import StandbyPasar from '$lib/components/StandbyPasar.svelte';
</script>

<svelte:head><title>GMGN | War Room</title></svelte:head>

<StandbyPasar
	nama="GMGN"
	ringkas="Radar meme coin Solana dan pemantauan DEX. Dinonaktifkan sementara."
	alasan="Radar GMGN (sniper token, Pump.fun, lonjakan volume on-chain) dinonaktifkan agar resource komputasi dan perhatian trading terpusat pada Forex dan Gold. Risiko market ini juga paling tinggi, jadi butuh modal dan batas risiko terpisah."
	syarat={[
		'Akses API GMGN atau RPC Solana yang stabil dari server',
		'Filter anti-rug dan anti-honeypot yang teruji',
		'Batas modal terpisah, tidak mencampur dengan akun forex',
		'Gate B lulus untuk satu strategi, dengan biaya on-chain dihitung'
	]}
	terakhir={null}
/>
