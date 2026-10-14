<script lang="ts">
	// DatasetExplorer (P4-T3): katalog dataset Polymarket dari fakta `poly.dataset/recorder`
	// + cakupan baca `poly.akses/cakupan`. Semua angka apa adanya dari fakta; direktori yang
	// tidak terbaca tampil sebagai statusnya (mis. `tidak-izin`), bukan nol.
	// Unduh sampel belum diekspos: butuh allowlist baca di sisi host (checklist go/no-go C4).
	import type { Fact } from '$lib/api/types';
	import EmptyState from './EmptyState.svelte';

	interface Props {
		recorder: Fact | null;
		cakupan: Fact | null;
	}
	let { recorder, cakupan }: Props = $props();

	interface EntriDataset {
		nama: string;
		path: string;
		files: number | null;
		bytes: number | null;
		status: string;
	}

	const entri = $derived.by((): EntriDataset[] => {
		const v = recorder?.value;
		if (v == null || typeof v !== 'object') return [];
		return Object.entries(v as Record<string, unknown>)
			.filter(([, d]) => d != null && typeof d === 'object')
			.map(([nama, d]) => {
				const o = d as Record<string, unknown>;
				return {
					nama,
					path: typeof o.path === 'string' ? o.path : '—',
					files: typeof o.files === 'number' ? o.files : null,
					bytes: typeof o.bytes === 'number' ? o.bytes : null,
					status: typeof o.status === 'string' ? o.status : '—'
				};
			});
	});

	const totalFiles = $derived(
		entri.reduce((a, e) => a + (e.files ?? 0), 0) || (entri.length ? null : null)
	);
	const totalBytes = $derived(entri.reduce((a, e) => a + (e.bytes ?? 0), 0));

	// Byte → satuan besar (GB/MB/KB) tanpa angka karangan; pembulatan 2 desimal.
	function ukuran(n: number | null): string {
		if (n == null) return '—';
		const satuan = ['B', 'KB', 'MB', 'GB', 'TB'];
		let i = 0;
		let x = n;
		while (x >= 1024 && i < satuan.length - 1) {
			x /= 1024;
			i += 1;
		}
		return `${x.toLocaleString('id-ID', { maximumFractionDigits: 2 })} ${satuan[i]}`;
	}

	const cakupanBaris = $derived.by((): { nama: string; nilai: string }[] => {
		const v = cakupan?.value;
		if (v == null || typeof v !== 'object') return [];
		return Object.entries(v as Record<string, unknown>).map(([k, val]) => ({
			nama: k,
			nilai: typeof val === 'string' ? val : String(val)
		}));
	});

	function nadaCakupan(nilai: string): string {
		if (nilai === 'ok') return 'text-pos border-pos/40 bg-pos/10';
		if (nilai.includes('izin')) return 'text-warn border-warn/40 bg-warn/10';
		return 'text-text-3 border-line bg-surface-2';
	}
</script>

<div data-testid="dataset-explorer">
	{#if !recorder && !cakupan}
		<EmptyState
			judul="Katalog dataset belum ada"
			pesan="Fact poly.dataset/recorder dan poly.akses/cakupan belum diterbitkan job poly-sync."
		/>
	{:else}
		<div class="grid gap-2 sm:grid-cols-3">
			<div>
				<span class="label-mikro block">direktori</span>
				<span class="angka text-15 text-text">{entri.length}</span>
			</div>
			<div>
				<span class="label-mikro block">total berkas</span>
				<span class="angka text-15 text-text">{totalFiles?.toLocaleString('id-ID') ?? '—'}</span>
			</div>
			<div>
				<span class="label-mikro block">total ukuran</span>
				<span class="angka text-15 text-text">{ukuran(entri.length ? totalBytes : null)}</span>
			</div>
		</div>

		{#if entri.length}
			<table class="mt-3 w-full text-left text-12" data-testid="dataset-tabel">
				<thead>
					<tr class="label-mikro text-text-3">
						<th class="py-1 font-normal">direktori</th>
						<th class="py-1 font-normal">path</th>
						<th class="py-1 text-right font-normal">berkas</th>
						<th class="py-1 text-right font-normal">ukuran</th>
						<th class="py-1 font-normal">status</th>
					</tr>
				</thead>
				<tbody>
					{#each entri as e (e.nama)}
						<tr class="border-t border-line">
							<td class="angka py-1 text-text">{e.nama}</td>
							<td class="angka py-1 text-text-3">{e.path}</td>
							<td class="angka py-1 text-right text-text-2">
								{e.files?.toLocaleString('id-ID') ?? '—'}
							</td>
							<td class="angka py-1 text-right text-text-2">{ukuran(e.bytes)}</td>
							<td class="py-1">
								<span class="label-mikro rounded-control border px-2 py-0.5 {nadaCakupan(e.status)}"
									>{e.status}</span
								>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		{/if}

		{#if cakupanBaris.length}
			<p class="label-mikro mt-3 mb-1">cakupan baca</p>
			<p class="flex flex-wrap gap-2">
				{#each cakupanBaris as c (c.nama)}
					<span class="label-mikro rounded-control border px-2 py-0.5 {nadaCakupan(c.nilai)}">
						{c.nama} <span class="angka">{c.nilai}</span>
					</span>
				{/each}
			</p>
		{/if}

		<p class="mt-3 text-11 text-text-3">
			Unduh sampel belum diekspos — butuh allowlist baca di sisi host (lihat checklist go/no-go C4).
			{recorder
				? `Diperbarui ${new Date(recorder.observed_at).toLocaleString('id-ID', { timeZone: 'Asia/Jakarta' })} WIB.`
				: ''}
		</p>
	{/if}
</div>
