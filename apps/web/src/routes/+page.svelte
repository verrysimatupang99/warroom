<script lang="ts">
	// Home — Cockpit sinyal lintas pasar (gaya A+B, 5 Okt 2026).
	//
	// Tata letak: strip ringkasan di atas (B), lalu kartu sinyal terbaik per pasar bertumpuk
	// (A). Aturan yang dipegang halaman ini:
	// - Angka yang belum lewat split beku WAJIB tampil sebagai klaim eksplorasi, bukan edge.
	// - Pasar tanpa sinyal tetap tampil dengan alasannya; skor "—", bukan 0.
	import { getAlerts, getKesegaran, getKesehatan, getSinyalPerPasar } from '$lib/api/client';
	import type { AlertsPayload, Kesehatan, KesegaranPayload, SinyalPayload } from '$lib/api/types';
	import { live } from '$lib/api/live.svelte';
	import { umurDetik } from '$lib/format';
	import KartuSinyalPasar from '$lib/components/KartuSinyalPasar.svelte';
	import ErrorState from '$lib/components/ErrorState.svelte';
	import Skeleton from '$lib/components/Skeleton.svelte';

	let sinyal = $state<SinyalPayload | null>(null);
	let kesegaran = $state<KesegaranPayload | null>(null);
	let sehat = $state<Kesehatan | null>(null);
	let alerts = $state<AlertsPayload | null>(null);
	let galat = $state<string | null>(null);
	let memuat = $state(true);

	async function muat() {
		const [s, k, h, al] = await Promise.allSettled([
			getSinyalPerPasar(),
			getKesegaran(),
			getKesehatan(),
			getAlerts()
		]);
		if (s.status === 'fulfilled') {
			sinyal = s.value;
			galat = null;
		} else {
			galat = s.reason instanceof Error ? s.reason.message : String(s.reason);
		}
		if (k.status === 'fulfilled') kesegaran = k.value;
		if (h.status === 'fulfilled') sehat = h.value;
		if (al.status === 'fulfilled') alerts = al.value;
		memuat = false;
	}

	$effect(() => {
		void muat();
		const t = setInterval(() => void muat(), 15000);
		return () => clearInterval(t);
	});

	const daftar = $derived(sinyal?.sinyal ?? []);

	// Strip ringkasan (gaya B) — semuanya dihitung dari data yang benar-benar ada.
	const ringkas = $derived([
		{ n: daftar.length, t: 'Pasar dipantau', w: 'var(--text)' },
		{ n: daftar.filter((r) => r.ada).length, t: 'Ada sinyal', w: 'var(--accent)' },
		{
			n: daftar.filter((r) => r.ada && r.terverifikasi).length,
			t: 'Terverifikasi',
			w: 'var(--warn)'
		},
		{
			n: (kesegaran?.facts ?? []).filter((f) => f.status === 'basi').length,
			t: 'Fakta basi',
			w: 'var(--warn)'
		},
		{
			n: sehat?.status ?? '—',
			t: 'Layanan',
			w: sehat?.status === 'ok' ? 'var(--accent)' : 'var(--warn)'
		}
	]);

	// Sorotan (gaya B): sinyal berskor tertinggi yang benar-benar ada.
	const sorotan = $derived(
		daftar
			.filter((r) => r.ada && r.skor != null)
			.slice()
			.sort((a, b) => (b.skor ?? 0) - (a.skor ?? 0))[0] ?? null
	);
</script>

<svelte:head><title>Home — War Room</title></svelte:head>

<div class="ruang">
	<header class="kepala">
		<div>
			<h1>Sinyal per pasar</h1>
			<p>
				Satu sinyal terbaik tiap pasar dari konfigurasi terukur. Status verifikasi selalu
				ditampilkan — angka yang belum lewat split beku adalah klaim eksplorasi, bukan edge.
			</p>
		</div>
		<div class="status">
			<span class="pil-mikro">
				<span class="titik" style="--w:{live.status === 'live' ? 'var(--pos)' : 'var(--warn)'}"></span>
				SSE {live.status}
			</span>
			<span class="pil-mikro">DB {sehat?.db ? 'ok' : '—'}</span>
			{#if kesegaran?.checked_at}
				<span class="pil-mikro">kesegaran {umurDetik(kesegaran.facts?.[0]?.age_s ?? null)}</span>
			{/if}
		</div>
	</header>

	{#if alerts && alerts.terbuka > 0}
		<div class="banner" data-testid="alert-banner">
			<span>⚠</span>
			<span><b class="angka">{alerts.terbuka}</b> alert butuh perhatian</span>
			<a href="/sistem">Buka Sistem →</a>
		</div>
	{/if}

	{#if galat}
		<ErrorState pesan={galat} onulang={() => void muat()} />
	{:else if memuat}
		<Skeleton tinggi={84} />
		<Skeleton tinggi={150} />
		<Skeleton tinggi={150} />
	{:else}
		<!-- Strip ringkasan (B) -->
		<section class="strip" aria-label="Ringkasan">
			{#each ringkas as r (r.t)}
				<div class="chip">
					<b class="angka" style="--w:{r.w}">{r.n}</b>
					<span class="label-mikro">{r.t}</span>
				</div>
			{/each}
		</section>

		<!-- Sorotan (B): satu keputusan jelas saat pertama buka -->
		{#if sorotan}
			<section class="sorotan" aria-label="Sinyal terkuat">
				<span class="label-mikro">Sinyal terkuat saat ini · {sorotan.label}</span>
				<div class="baris">
					<span class="subjek angka">{sorotan.subjek ?? '—'}</span>
					{#if sorotan.arah}<span class="arah">{sorotan.arah}</span>{/if}
					{#if sorotan.skor != null}<span class="skor-besar angka">{sorotan.skor}</span>{/if}
				</div>
				<p class="alasan">{sorotan.alasan}</p>
				{#if !sorotan.terverifikasi}
					<p class="jujur" role="note">{sorotan.catatan_kejujuran}</p>
				{/if}
			</section>
		{/if}

		<!-- Kartu per pasar (A) -->
		<section class="daftar" aria-label="Sinyal tiap pasar">
			{#each daftar as s (s.pasar)}
				<KartuSinyalPasar {s} utama={s.pasar === sorotan?.pasar} />
			{/each}
		</section>

		{#if daftar.length > 0 && !sinyal?.ada}
			<p class="catatan">
				Belum ada pasar yang menghasilkan sinyal. Tiap kartu menyebutkan alasannya — sengaja
				tidak diisi angka 0 supaya tidak terlihat seperti data.
			</p>
		{/if}
	{/if}
</div>

<style>
	.ruang {
		display: flex;
		flex-direction: column;
		gap: 16px;
	}
	.kepala {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 16px;
		flex-wrap: wrap;
	}
	h1 {
		font-family: var(--font-display);
		font-size: 22px;
		margin: 0 0 4px;
	}
	.kepala p {
		margin: 0;
		font-size: 12px;
		color: var(--text-3);
		max-width: 64ch;
	}
	.status {
		display: flex;
		gap: 6px;
		flex-wrap: wrap;
	}
	.pil-mikro {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		font-family: var(--font-mono);
		font-size: 10px;
		color: var(--text-3);
		border: 1px solid var(--line);
		border-radius: var(--radius-pil);
		padding: 3px 9px;
	}
	.titik {
		width: 6px;
		height: 6px;
		border-radius: 50%;
		background: var(--w);
	}
	.banner {
		display: flex;
		align-items: center;
		gap: 10px;
		font-size: 12px;
		color: var(--text-2);
		background: color-mix(in srgb, var(--warn) 10%, transparent);
		border: 1px solid color-mix(in srgb, var(--warn) 40%, transparent);
		border-radius: var(--radius-card);
		padding: 10px 14px;
	}
	.banner a {
		margin-left: auto;
		color: var(--warn);
	}
	.strip {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(118px, 1fr));
		gap: 8px;
	}
	.chip {
		background: var(--surface);
		border: 1px solid var(--line-soft);
		border-radius: var(--radius-card);
		padding: 10px 12px;
		display: flex;
		flex-direction: column;
		gap: 2px;
	}
	.chip b {
		font-size: 18px;
		font-weight: 700;
		color: var(--w, var(--text));
	}
	.sorotan {
		background: linear-gradient(160deg, var(--surface-2), var(--surface));
		border: 1px solid color-mix(in srgb, var(--accent) 35%, transparent);
		border-radius: var(--radius-card);
		padding: 16px;
	}
	.baris {
		display: flex;
		align-items: baseline;
		gap: 10px;
		flex-wrap: wrap;
		margin-top: 6px;
	}
	.subjek {
		font-size: 28px;
		font-weight: 700;
		letter-spacing: -0.02em;
	}
	.arah {
		font-family: var(--font-mono);
		font-size: 12px;
		padding: 2px 8px;
		border-radius: 6px;
		color: var(--accent);
		background: color-mix(in srgb, var(--accent) 14%, transparent);
		border: 1px solid color-mix(in srgb, var(--accent) 30%, transparent);
	}
	.skor-besar {
		font-size: 22px;
		font-weight: 700;
		color: var(--accent);
		margin-left: auto;
	}
	.alasan {
		margin: 10px 0 0;
		font-size: 12px;
		color: var(--text-2);
	}
	.daftar {
		display: flex;
		flex-direction: column;
		gap: 12px;
	}
	.jujur {
		margin: 10px 0 0;
		font-size: 11px;
		color: var(--warn);
		background: color-mix(in srgb, var(--warn) 8%, transparent);
		border-left: 2px solid var(--warn);
		padding: 6px 10px;
		border-radius: 0 6px 6px 0;
	}
	.catatan {
		font-size: 12px;
		color: var(--text-3);
		margin: 0;
	}
</style>
