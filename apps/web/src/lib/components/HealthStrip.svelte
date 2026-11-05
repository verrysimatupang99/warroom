<script lang="ts">
	// Strip kesehatan sistem: DB, worker, dan jumlah fakta basi dalam satu baris.
	//
	// Kenapa ada: tanpa ini, Home menampilkan "tidak ada sinyal" untuk DUA keadaan
	// yang sangat berbeda — pasar memang sepi, atau worker mati. Angka yang tidak
	// bisa dibedakan adalah angka yang menyesatkan.
	//
	// Komponen ini TIDAK memanggil API sendiri: halaman sudah mengambil
	// /api/v1/ready, dan satu fetch per halaman lebih jujur daripada dua yang bisa
	// saling menyimpang.
	import type { Readiness } from '$lib/api/types';

	interface Props {
		/** Jawaban /api/v1/ready; null = belum terbaca. */
		kesiapan?: Readiness | null;
		/** true bila permintaan gagal — ditampilkan terbuka, bukan hijau. */
		gagal?: boolean;
	}
	let { kesiapan = null, gagal = false }: Props = $props();

	const worker = $derived(kesiapan?.checks?.worker_heartbeats?.status ?? 'unknown');
	const basi = $derived(kesiapan?.freshness?.count ?? null);

	// Nada hanya menyatakan apa yang benar-benar dilaporkan API. Tanpa laporan,
	// hasilnya "tidak diketahui" — bukan hijau.
	const nadaDb: 'ok' | 'gagal' | 'tak' = $derived(
		gagal ? 'tak' : kesiapan ? (kesiapan.db ? 'ok' : 'gagal') : 'tak'
	);
	const nadaWorker: 'ok' | 'gagal' | 'tak' = $derived(
		gagal ? 'tak' : worker === 'ok' ? 'ok' : worker === 'stale' ? 'gagal' : 'tak'
	);
	const nadaBasi: 'ok' | 'gagal' | 'tak' = $derived(
		gagal || basi == null ? 'tak' : basi > 0 ? 'gagal' : 'ok'
	);

	const kelas = {
		ok: 'text-pos border-pos/40 bg-pos/10',
		gagal: 'text-neg border-neg/40 bg-neg/10',
		tak: 'text-text-3 border-line bg-surface-2'
	} as const;
</script>

<div class="label-mikro flex flex-wrap items-center gap-1.5" data-testid="health-strip">
	<span class="text-text-3">Sistem</span>
	<span
		class="inline-flex items-center gap-1 rounded-control border px-1.5 py-0.5 {kelas[nadaDb]}"
		title="database: {nadaDb === 'ok'
			? 'terjangkau'
			: nadaDb === 'gagal'
				? 'tidak terjangkau'
				: 'belum dilaporkan'}"
		data-nada={nadaDb}
	>
		db {nadaDb === 'ok' ? 'ok' : nadaDb === 'gagal' ? 'gagal' : 'n/a'}
	</span>
	<span
		class="inline-flex items-center gap-1 rounded-control border px-1.5 py-0.5 {kelas[nadaWorker]}"
		title="heartbeat worker: {worker}"
		data-nada={nadaWorker}
	>
		worker {worker === 'ok' ? 'ok' : worker === 'stale' ? 'basi' : 'n/a'}
	</span>
	<span
		class="inline-flex items-center gap-1 rounded-control border px-1.5 py-0.5 {kelas[nadaBasi]}"
		title="fakta yang melewati TTL-nya (dari /api/v1/ready)"
		data-nada={nadaBasi}
	>
		{basi == null ? 'fakta basi n/a' : `${basi} fakta basi`}
	</span>
	{#if gagal}
		<span class="text-neg">status sistem tidak terbaca</span>
	{/if}
</div>
