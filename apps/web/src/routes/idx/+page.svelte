<script lang="ts">
	import StandbyPasar from '$lib/components/StandbyPasar.svelte';
</script>

<svelte:head><title>IDX | War Room</title></svelte:head>

<StandbyPasar
	nama="IDX"
	ringkas="Saham Indonesia, foreign flow, dan bandarmologi. Dalam mode standby."
	alasan="Scanner IDX, ledger sinyal, dan akses database read-only sebelumnya berjalan di node luar yang sudah tidak aktif. War Room tidak menghitung ulang angka IDX sendiri, jadi tanpa sumber itu halaman ini tidak punya data yang bisa dipercaya."
	syarat={[
		'Feed harga saham IDX yang bisa diakses langsung dari server',
		'Sumber foreign flow dan broker summary',
		'Scanner bandarmologi dijalankan ulang di server ini atau diganti sumber resmi',
		'Satu aturan lulus Gate B sebelum dipakai untuk paper'
	]}
	terakhir={null}
/>
