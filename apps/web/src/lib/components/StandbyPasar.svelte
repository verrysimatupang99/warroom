<script lang="ts">
	// Halaman untuk market yang belum aktif.
	// Menjelaskan status, alasan, dan syarat aktif. Tidak menampilkan angka kosong
	// atau tombol yang tidak melakukan apa pun.
	import PageHeader from './PageHeader.svelte';

	interface Props {
		nama: string;
		ringkas: string;
		alasan: string;
		syarat: string[];
		terakhir?: string | null;
	}
	let { nama, ringkas, alasan, syarat, terakhir = null }: Props = $props();
</script>

<div class="space-y-4">
	<PageHeader
		eyebrow={`War Room · ${nama}`}
		title={`${nama} standby`}
		tag="STANDBY"
		description={ringkas}
		terverifikasi={false}
		alasan="Market ini belum punya sumber data aktif, jadi tidak ada angka yang bisa ditampilkan."
	/>

	<section class="rounded-card border border-line bg-surface p-4">
		<h2 class="text-13 font-bold text-text">Kenapa belum aktif</h2>
		<p class="mt-1 text-12 leading-relaxed text-text-2">{alasan}</p>
		{#if terakhir}
			<p class="mt-2 text-11 font-mono text-text-3">Data terakhir: {terakhir}</p>
		{/if}
	</section>

	<section class="rounded-card border border-line bg-surface p-4">
		<h2 class="text-13 font-bold text-text">Syarat supaya bisa dibuka</h2>
		<ul class="mt-2 space-y-1.5">
			{#each syarat as s, i (i)}
				<li class="flex gap-2 text-12 text-text-2">
					<span class="font-mono text-text-3">{i + 1}.</span>
					<span>{s}</span>
				</li>
			{/each}
		</ul>
	</section>

	<p class="text-11 text-text-3">
		Market lain yang sudah aktif: <a class="text-accent underline" href="/forex">Forex</a> ·
		<a class="text-accent underline" href="/crypto">Crypto</a> ·
		<a class="text-accent underline" href="/jurnal">Jurnal</a>
	</p>
</div>
