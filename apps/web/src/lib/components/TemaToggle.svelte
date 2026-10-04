<script lang="ts">
	// Pengalih tema: "gelap" (mode data) <-> "terang" (mode editorial).
	//
	// Kenapa ada: dua referensi yang diminta pemilik bertolak belakang — yang satu gelap dan
	// padat data, yang satu terang dan lapang. Satu tema tidak bisa menjadi keduanya, jadi
	// keduanya dibuat sungguhan dan bisa dipilih.
	//
	// Tema disimpan di localStorage dan diterapkan ke `data-tema` pada <html>. Skrip di
	// app.html sudah menerapkannya sebelum cat pertama, jadi tidak ada kedipan tema salah.
	import { onMount } from 'svelte';

	let tema = $state<'gelap' | 'terang'>('gelap');

	onMount(() => {
		const t = document.documentElement.dataset.tema;
		if (t === 'terang' || t === 'gelap') tema = t;
	});

	function ganti() {
		tema = tema === 'gelap' ? 'terang' : 'gelap';
		document.documentElement.dataset.tema = tema;
		try {
			localStorage.setItem('warroom-tema', tema);
		} catch {
			/* localStorage diblokir: tema tetap berganti untuk sesi ini */
		}
	}
</script>

<button
	type="button"
	class="target-44 transisi flex items-center gap-2 rounded-control border border-line px-2 py-1 text-12 text-text-2 hover:border-accent-2 hover:text-text"
	onclick={ganti}
	aria-label={tema === 'gelap' ? 'Ganti ke tema terang' : 'Ganti ke tema gelap'}
	title={tema === 'gelap' ? 'Mode data (gelap)' : 'Mode editorial (terang)'}
>
	<span aria-hidden="true">{tema === 'gelap' ? '◐' : '◑'}</span>
	<span class="hidden sm:inline">{tema === 'gelap' ? 'Gelap' : 'Terang'}</span>
</button>
