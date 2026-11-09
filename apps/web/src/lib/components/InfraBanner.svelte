<script lang="ts">
	/**
	 * InfraBanner.svelte — pita peringatan global, tampil di SEMUA halaman bila
	 * infra lintas mesin bermasalah atau snapshotnya basi.
	 *
	 * Sengaja tidak tampil saat semua sehat: pita permanen hanya jadi noise dan
	 * lama-lama diabaikan. Yang tidak dilaporkan tidak dianggap hijau.
	 */
	import { onMount } from 'svelte';
	import { urlApi } from '$lib/api/client';

	interface Snapshot {
		tersedia?: boolean;
		umur_s?: number | null;
		memoh_runtime?: Record<string, unknown>;
		mt5?: Record<string, string>;
		instabox_watchdog?: Record<string, unknown>;
	}

	let snap = $state<Snapshot | null>(null);
	let gagal = $state(false);

	onMount(() => {
		let hidup = true;
		fetch(urlApi('/api/v1/infra/health'), { credentials: 'include' })
			.then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
			.then((d) => {
				if (hidup) snap = d as Snapshot;
			})
			.catch(() => {
				if (hidup) gagal = true;
			});
		return () => {
			hidup = false;
		};
	});

	const masalah = $derived.by(() => {
		if (gagal || !snap || snap.tersedia === false) return [];
		const out: string[] = [];
		const m = snap.memoh_runtime ?? {};
		if (m.active !== 'active') out.push('Memoh runtime mati');
		for (const [nama, nilai] of Object.entries(snap.mt5 ?? {})) {
			if (nilai !== 'up') out.push(`MT5 ${nama} mati`);
		}
		if ((snap.instabox_watchdog ?? {}).timer !== 'active') out.push('watchdog instabox mati');
		if (typeof snap.umur_s === 'number' && snap.umur_s > 1800) {
			out.push(`snapshot basi (${Math.round(snap.umur_s / 60)} menit)`);
		}
		return out;
	});
</script>

{#if masalah.length}
	<div
		class="mb-3 flex flex-wrap items-center gap-2 rounded-control border border-warn/40 bg-warn/10 px-3 py-2 font-mono text-11 text-warn"
		role="status"
		data-testid="infra-banner"
	>
		<span class="font-bold">INFRA</span>
		<span class="text-text">{masalah.join(' · ')}</span>
		<a class="ml-auto underline hover:text-accent" href="/sistem?sub=layanan">Lihat sistem</a>
	</div>
{/if}
